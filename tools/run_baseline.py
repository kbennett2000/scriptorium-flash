#!/usr/bin/env python3
"""Drive one Scriptorium bake end to end and record exactly when things happened.

Scriptorium is not modified and its deployed configuration is not touched. The
bakery pauses at two human review gates; this script watches for each one and
clears it as soon as it opens, recording how long it waited so that human time
can be subtracted from machine time.

Writes a run log that `bake_timing.py` reads for its window and gate figures.

    ./run_baseline.py --gutenberg-id 932 --out runs/pg-932/run.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = "http://localhost:8720"
POLL_S = 1.0

# state -> the endpoint that clears it
GATES = {
    "cast_done": "approve-cast",
    "prompts_draft": "approve",
    "portraits_review": "approve-portraits",
}
TERMINAL = {"published", "failed"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def call(method: str, path: str, body: dict | None = None, timeout: float = 300.0):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"content-type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:400]
        raise SystemExit(f"{method} {path} -> HTTP {e.code}: {detail}") from None


def plate_count(book_id: str) -> int | None:
    """How many plates selection actually chose.

    ``selection.plates`` on the review endpoint is the authoritative list -- it is
    what the selection engine wrote and what the renderer will work from. Returns
    None rather than a wrong number if the shape is not what we expect.
    """
    try:
        review = call("GET", f"/api/admin/books/{book_id}/review", timeout=30)
    except SystemExit:
        return None
    plates = (review.get("selection") or {}).get("plates")
    return len(plates) if isinstance(plates, list) else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gutenberg-id", type=int, required=True)
    ap.add_argument("--title", default="The Fall of the House of Usher")
    ap.add_argument("--author", default="Poe, Edgar Allan")
    ap.add_argument("--style-id", default="oil-painting")
    ap.add_argument("--density-preset", default="lavish")
    ap.add_argument("--images-per-scene", type=int, default=1)
    ap.add_argument("--era", default="1840s American Gothic")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--stop-after-selection",
        action="store_true",
        help="pause at the prompt-review gate and report the plate count without "
        "approving, so an out-of-range selection is caught before any GPU time "
        "is spent on rendering",
    )
    ap.add_argument(
        "--at-prompt-gate",
        help="shell command to run when the prompt gate opens, before it is "
        "cleared. This is where a pre-warm belongs: every render in the bake "
        "happens after this gate, and nothing before it touches a GPU we pay "
        "for, so pre-warming here rather than at the start of the run keeps "
        "warm workers from billing through a text phase that on a full-length "
        "book is twenty minutes long.",
    )
    args = ap.parse_args()

    body = {
        "source": {
            "kind": "gutenberg",
            "gutenberg_id": args.gutenberg_id,
            "title": args.title,
            "author": args.author,
        },
        "bake": {
            "style_id": args.style_id,
            "density_preset": args.density_preset,
            "images_per_scene": args.images_per_scene,
            "era": args.era,
            "portraits_enabled": True,
            "portrait_review": False,
            "title": args.title,
            "author": args.author,
        },
    }

    log: dict = {
        "t_start": now(),
        "t_end": None,
        "book_id": None,
        "request": body,
        "transitions": [],
        "gates": {"cast_s": 0.0, "approve_s": 0.0, "total_s": 0.0},
        "final_state": None,
    }

    def flush() -> None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(log, indent=2) + "\n")

    print(f"[{now()}] creating book (ingest runs inline, this blocks)", flush=True)
    created = call("POST", "/api/admin/books", body)
    book_id = created["book_id"]
    log["book_id"] = book_id
    log["transitions"].append({"at": now(), "state": created.get("state")})
    print(f"[{now()}] book_id={book_id} state={created.get('state')} "
          f"warnings={created.get('warnings')}", flush=True)
    flush()

    call("POST", f"/api/admin/jobs/{book_id}/start")
    print(f"[{now()}] started", flush=True)

    state = None
    gate_opened_at: float | None = None
    gate_name: str | None = None

    while True:
        book = call("GET", f"/api/admin/books/{book_id}", timeout=30)
        new_state = book.get("state")

        if new_state != state:
            state = new_state
            log["transitions"].append({"at": now(), "state": state})
            print(f"[{now()}] -> {state}", flush=True)
            flush()

        if state in TERMINAL:
            break

        if state in GATES and gate_opened_at is None:
            gate_opened_at = time.monotonic()
            gate_name = state

            if state == "prompts_draft":
                # The plate count is selection.plates, and nothing else. An earlier
                # version counted prompt_warnings here, which is the number of pages
                # that drew a *warning* -- on pg-41 that reported 5 against a real
                # count of 10. This gate exists to catch an out-of-range selection
                # before GPU time is spent, so a number that is only sometimes the
                # plate count is worse than no number.
                plates = plate_count(book_id)
                log["plate_count"] = plates
                print(f"[{now()}] prompt gate open"
                      + (f" ({plates} plates)" if plates is not None
                         else " (plate count unavailable)"), flush=True)
                if args.stop_after_selection:
                    print("stopping before render, as asked", flush=True)
                    log["final_state"] = state
                    log["t_end"] = now()
                    flush()
                    return 0

                if args.at_prompt_gate:
                    print(f"[{now()}] running --at-prompt-gate command",
                          flush=True)
                    t0 = time.monotonic()
                    rc = subprocess.call(args.at_prompt_gate, shell=True)
                    log["prompt_gate_hook"] = {
                        "command": args.at_prompt_gate,
                        "returncode": rc,
                        "seconds": round(time.monotonic() - t0, 3),
                    }
                    print(f"[{now()}] hook exited {rc} after "
                          f"{log['prompt_gate_hook']['seconds']:.1f}s",
                          flush=True)
                    flush()
                    if rc != 0:
                        # Renders are about to start and the pre-warm failed.
                        # Do not clear the gate: a cold fleet is a fidelity
                        # problem (every worker's first render is a cold-load
                        # render), not only a slow one.
                        print("hook failed -- leaving the gate closed so no "
                              "render runs against a cold fleet", flush=True)
                        log["final_state"] = state
                        log["t_end"] = now()
                        flush()
                        return 1

            call("POST", f"/api/admin/books/{book_id}/{GATES[state]}")
            waited = time.monotonic() - gate_opened_at
            key = "cast_s" if state == "cast_done" else "approve_s"
            log["gates"][key] = log["gates"].get(key, 0.0) + waited
            log["gates"]["total_s"] = round(
                sum(v for k, v in log["gates"].items() if k.endswith("_s")
                    and k != "total_s"),
                3,
            )
            print(f"[{now()}] cleared {gate_name} gate in {waited:.2f}s", flush=True)
            gate_opened_at = None
            gate_name = None
            flush()

        time.sleep(POLL_S)

    log["final_state"] = state
    log["t_end"] = now()
    flush()

    elapsed = (
        datetime.fromisoformat(log["t_end"]) - datetime.fromisoformat(log["t_start"])
    ).total_seconds()
    print(f"[{now()}] {state} — wall {elapsed / 60:.1f} min, "
          f"gate wait {log['gates']['total_s']:.1f}s", flush=True)
    return 0 if state == "published" else 1


if __name__ == "__main__":
    sys.exit(main())
