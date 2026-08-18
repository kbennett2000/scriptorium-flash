#!/usr/bin/env python3
"""Re-render every cold-load image against a warm worker, before the book ships.

A worker's first render after a model load does not match the renders after it:
842,339 differing pixels (83.3%), reproducible to the pixel on home's card and in
the container alike. Pre-warming is meant to absorb every one of those, and in the
Cycle 4 headline bake it absorbed one worker of three -- two cold-load images went
into the published bundle.

This closes that hole. It finds the images whose `params_echo.model_load_s` is
non-zero and re-renders each through the bakery's own regen route, which
post-publish takes the additive path: a new `…-rN` variant beside the untouched
original, bundle revision bumped, manifest rebuilt. The reader resolves
highest--rN-wins, so it downloads the warm one.

Two things this is careful about:

- **It verifies the replacement is itself warm.** A regen issued against a worker
  that has since spun down is another cold-load render, and would swap one bad
  image for another. Each regen's echo is checked and retried.
- **The seed changes.** The regen route deliberately uses a fresh seed, so the new
  plate is a different picture, not the same picture rendered warm. That is the
  honest description of what this does, and it is the reason to run it before
  anyone has seen the book rather than after.

Ordering matters: this needs the endpoint alive, so it must run BEFORE teardown.

    ./remediate_cold_plates.py --book-id pg-120 --endpoint tw7wlntgpdetsc
    ./remediate_cold_plates.py --book-id pg-120 --endpoint tw7wlntgpdetsc --dry-run
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

DATA_ROOT = Path("/home/kb/scriptorium-data")
BASE = "http://localhost:8720"
REPO = Path(__file__).resolve().parent


def cold_images(book_id: str, data_root: Path) -> list[dict]:
    """Images whose echo says a model was staged to draw them.

    Reads the published bundle when there is one, because that is what ships;
    falls back to the work tree for a bake that has not published.
    """
    for sub in ("library", "work"):
        d = data_root / sub / book_id / "prompts"
        if d.is_dir():
            out = []
            for p in sorted(d.glob("*.json")):
                echo = (json.loads(p.read_text()).get("render") or {}).get("params_echo") or {}
                if echo and float(echo.get("model_load_s") or 0) > 0:
                    out.append({"id": p.stem,
                                "model_load_s": float(echo["model_load_s"]),
                                "render_s": float(echo.get("render_s") or 0)})
            return out
    raise SystemExit(f"no prompts for {book_id}")


def post(path: str, timeout: float = 900.0) -> dict:
    req = urllib.request.Request(BASE + path, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


def warm_one(endpoint: str) -> bool:
    """Put a worker in a resident-model state and confirm it, before regenerating."""
    out = subprocess.run(
        [str(REPO / "prewarm.py"), "--endpoint", endpoint, "--workers", "1"],
        capture_output=True, text=True, timeout=2000,
    )
    sys.stdout.write(out.stdout[-1500:])
    return out.returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--book-id", required=True)
    ap.add_argument("--endpoint", required=True)
    ap.add_argument("--data-root", type=Path, default=DATA_ROOT)
    ap.add_argument("--attempts", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cold = cold_images(args.book_id, args.data_root)
    if not cold:
        print("no cold-load images -- nothing to remediate")
        return 0

    print(f"{len(cold)} cold-load image(s):")
    for c in cold:
        print(f"  {c['id']:<28} model_load {c['model_load_s']:>7.3f}s  "
              f"render {c['render_s']:>7.3f}s")
    if args.dry_run:
        print("\ndry run -- nothing re-rendered")
        return 0

    print("\nwarming a worker before regenerating, so the replacement is not "
          "itself a cold-load render")
    warm_one(args.endpoint)

    results = []
    for c in cold:
        for attempt in range(1, args.attempts + 1):
            t0 = time.monotonic()
            doc = post(f"/api/admin/books/{args.book_id}/plates/{c['id']}/regen")
            echo = (doc.get("render") or {}).get("params_echo") or {}
            load = float(echo.get("model_load_s") or 0)
            print(f"  {c['id']:<28} attempt {attempt}: model_load {load:>7.3f}s  "
                  f"render {float(echo.get('render_s') or 0):>7.3f}s  "
                  f"({time.monotonic() - t0:.1f}s wall)")
            if load == 0:
                results.append({"id": c["id"], "attempts": attempt, "warm": True,
                                "render_s": float(echo.get("render_s") or 0)})
                break
            print("    that replacement was itself cold -- re-warming and retrying")
            warm_one(args.endpoint)
        else:
            results.append({"id": c["id"], "attempts": args.attempts, "warm": False})

    bad = [r for r in results if not r["warm"]]
    print(f"\nremediated {len(results) - len(bad)} of {len(cold)}")
    if bad:
        print("STILL COLD: " + ", ".join(r["id"] for r in bad))
        return 1
    print("every cold-load image has been replaced by a warm render "
          "(new seed, additive -rN variant; the reader resolves highest-rN)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
