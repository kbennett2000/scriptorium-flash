#!/usr/bin/env python3
"""Measure plate renders on a Runpod serverless endpoint against the home baseline.

Protocol, matching what FINDINGS.md needs and nothing more:

1. **One cold request.** The first call to a scaled-to-zero endpoint pays the
   image pull and the ComfyUI boot. That is the number the 17.66 GB image exists
   to be judged on, and it is recorded separately from every later call.
2. **Six warm renders**, to match the home baseline's six. Same plates, same
   seeds, same prompts, read from the same provenance files the home bakery
   wrote -- so the comparison is against identical work, not merely similar work.
3. **A deliberate idle window** afterwards, worker warm and doing nothing, for
   the full `idle_timeout`. Whether that time is billed is the measurement draft
   issue 3 has been waiting for.
4. **Cost reconciled against the balance**, read before and well after. The
   billing-history API returns `[]` for serverless charges that demonstrably
   happened (FINDINGS.md), so the balance is the instrument -- and it lags by
   minutes, so the "after" reading is taken late and re-read until stable.

The renders are also a fidelity check, for free. Home already rendered these
plates; SDXL at a fixed seed is deterministic; so the returned PNG is compared
pixel by pixel against the stored one. `verify_port.py` proved the graph builder
reproduces home locally -- this proves it still holds on Runpod's GPU.

Credentials are never handled here: see tools/runpod_http.py.

    ./render_bench.py --endpoint <id> --tier "RTX A5000 / 3090" --warm 6
    ./render_bench.py --endpoint <id> --dry-run        # show the plan, spend nothing
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import runpod_http as R  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
BOOK = Path.home() / "scriptorium-data" / "work" / "pg-41"
OUT = REPO / "runs" / "runpod-render"

# The nine pg-41 plates, in the order the bakery rendered them. The first is the
# cold-start call; the next six are the warm sample.
PLATES = ["0001", "0003", "0006", "0008", "0011", "0013", "0015", "0018", "0020"]


def balance() -> float:
    out = subprocess.run(["runpodctl", "user"], capture_output=True, text=True).stdout
    return json.loads(out)["clientBalance"]


def settled_balance(reads: int = 8, gap: float = 30.0) -> float:
    """Read until two consecutive reads agree, with a floor on total wait.

    A stable reading is not automatically a settled one -- that mistake is
    recorded in FINDINGS.md -- so this waits `gap` between reads and requires
    agreement, rather than trusting the first quiet read.
    """
    prev = balance()
    for _ in range(reads):
        time.sleep(gap)
        now = balance()
        if now == prev:
            return now
        prev = now
    return prev


def conditioning_for(rec: dict) -> tuple[float | None, float | None]:
    """What Scriptorium sent for this plate, from its own ``derived.depicted``.

    Mirrors ``p7_render.reference_conditioning``: a plate whose frame holds more
    than one person gets a weaker, later identity anchor (0.35 / 0.4) than the
    service default (0.5 / 0.3), because IP-Adapter is global and unmasked and at
    full strength the second figure inherits the anchor's face and clothes.

    Cycle 3's bench did not send these, and the worker had no input for them, so
    every multi-figure plate was compared against a home render it did not match
    by construction. Four of the nine pg-41 plates are multi-figure, and three of
    them were the three highest divergences in that table.
    """
    depicted = ((rec.get("derived") or {}).get("depicted")) or []
    if len(depicted) > 1:
        return 0.35, 0.4
    return None, None


def provenance(plate: str, send_conditioning: bool = True) -> dict:
    """Rebuild the exact request home made for this plate.

    The IP-Adapter reference matters twice over. Seven of the nine pg-41 plates
    conditioned on a character portrait, so omitting it would render a different
    picture (breaking the pixel comparison) *and* skip the IP-Adapter work
    (making the timing flatter than the real workload). The portrait travels in
    the request rather than in the image, which is also what keeps character
    artwork out of the container and the registry.
    """
    rec = json.loads((BOOK / "prompts" / f"{plate}.json").read_text())
    echo = rec["render"]["params_echo"]
    payload = {
        "prompt": rec["wrapped_prompt"],
        "negative": rec["negative_prompt"],
        "seed": echo["seed"],
        "width": echo["width"],
        "height": echo["height"],
    }
    slug = rec["render"].get("reference_slug")
    if slug:
        portrait = BOOK / "images" / "portraits" / f"{slug}.png"
        if not portrait.is_file():
            raise SystemExit(f"plate {plate} needs portrait {portrait}, which is missing")
        payload["reference_png_b64"] = base64.b64encode(portrait.read_bytes()).decode()
        payload["_reference_slug"] = slug  # stripped before sending; for the log
        strength, start = conditioning_for(rec)
        if send_conditioning and strength is not None:
            payload["reference_strength"] = strength
            payload["reference_start"] = start
        # `send_conditioning=False` reproduces the pre-Cycle-4 request exactly, which
        # is the control arm: the worker then falls back to 0.5 / 0.3. Running both
        # arms of the same plate on the same worker is what separates the
        # conditioning gap from the hardware difference.
        payload["_conditioning"] = (
            f"{strength}/{start}" if (send_conditioning and strength is not None)
            else "worker default (0.5/0.3)"
        )
    payload["_figures"] = len(((rec.get("derived") or {}).get("depicted")) or [])
    return payload


def submit(endpoint: str, payload: dict, timeout_s: float) -> tuple[dict, float]:
    """POST /run, then poll /status until terminal. Returns (job, wall_seconds).

    /run rather than /runsync: runsync gives up at 60 s and a cold start behind a
    17.66 GB image pull will not fit in that.
    """
    t0 = time.monotonic()
    started = R.post(f"https://api.runpod.ai/v2/{endpoint}/run", {"input": payload}, timeout=120)
    if started.status != 200:
        return {"status": "SUBMIT_FAILED", "http": started.status, "body": started.body[:400]}, \
               time.monotonic() - t0

    job_id = started.json.get("id")
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        st = R.get(f"https://api.runpod.ai/v2/{endpoint}/status/{job_id}", timeout=60)
        if st.status == 200:
            body = st.json
            if body.get("status") in ("COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"):
                return body, time.monotonic() - t0
        time.sleep(1.0)
    return {"status": "CLIENT_TIMEOUT", "id": job_id}, time.monotonic() - t0


def compare_to_home(plate: str, png_b64: str) -> dict:
    """Pixel-compare the returned plate against the one home already rendered."""
    home = BOOK / "images" / "plates" / f"{plate}.png"
    if not home.is_file():
        return {"compared": False, "why": "no home plate on disk"}
    try:
        from PIL import Image, ImageChops
    except ImportError:
        return {"compared": False, "why": "Pillow not installed"}

    import io

    got = Image.open(io.BytesIO(base64.b64decode(png_b64))).convert("RGB")
    want = Image.open(home).convert("RGB")
    if got.size != want.size:
        return {"compared": True, "identical": False, "why": f"{got.size} != {want.size}"}
    diff = ImageChops.difference(got, want)
    bbox = diff.getbbox()
    if bbox is None:
        return {"compared": True, "identical": True, "differing_pixels": 0, "max_abs": 0}
    hist = diff.convert("L").histogram()
    differing = sum(hist[1:])
    return {
        "compared": True,
        "identical": False,
        "differing_pixels": differing,
        "total_pixels": got.size[0] * got.size[1],
        "max_abs": max(i for i, c in enumerate(hist) if c),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--endpoint", required=True, help="serverless endpoint id")
    ap.add_argument("--tier", required=True, help="label for FINDINGS.md, e.g. 'AMPERE_24'")
    ap.add_argument("--warm", type=int, default=6, help="warm renders after the cold one")
    ap.add_argument("--idle-window", type=float, default=90.0,
                    help="seconds to sit warm and idle afterwards, doing nothing")
    ap.add_argument("--cold-timeout", type=float, default=1800.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--comparison-set", action="store_true",
                    help="the Cycle 4 task 1 set: 0001/0003 isolate the interpreter, "
                         "0008/0013 run both conditioning arms to split the two causes")
    args = ap.parse_args()

    # Each row is (plate, send_conditioning). The default pass is the Cycle 3
    # protocol with conditioning now sent, so it is comparable to home's own work.
    if args.comparison_set:
        # Six rows chosen to separate two causes with one image (Cycle 4, task 1).
        # 0001 has no IP-Adapter at all and 0003 is single-figure, so both isolate
        # the interpreter change. 0008 and 0013 run BOTH arms: without conditioning
        # is the Cycle 3 replay, with it is the request home actually made. If the
        # multi-figure plates fall only in the "with" arm, conditioning is proved as
        # the second cause and silicon keeps the remainder.
        rows = [("0001", True), ("0003", True),
                ("0008", False), ("0008", True),
                ("0013", False), ("0013", True)]
    else:
        rows = [(p, True) for p in PLATES[: args.warm + 1]]

    if args.dry_run:
        print(f"endpoint {args.endpoint}  tier {args.tier}")
        print(f"cold: {rows[0][0]}   then: {', '.join(p for p, _ in rows[1:])}")
        for plate, send in rows:
            pr = provenance(plate, send)
            ref = pr.get("_reference_slug")
            kb = len(pr.get("reference_png_b64", "")) // 1024
            print(f"  {plate}: seed {pr['seed']:>10}  {pr['width']}x{pr['height']}  "
                  f"figures {pr.get('_figures', 0)}  ref {ref or '-':<12} ({kb} KB b64)  "
                  f"cond {pr.get('_conditioning', 'n/a')}")
        print("\ndry run, nothing submitted")
        return 0

    run_dir = OUT / f"{args.tier.replace('/', '_').replace(' ', '')}-{args.endpoint}"
    run_dir.mkdir(parents=True, exist_ok=True)

    b_before = balance()
    t_start = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    print(f"tier              {args.tier}")
    print(f"endpoint          {args.endpoint}")
    print(f"clientBalance     ${b_before:.10f}")
    print(f"started           {t_start}\n")

    results = []
    for i, (plate, send_conditioning) in enumerate(rows):
        kind = "COLD" if i == 0 else "warm"
        pr = provenance(plate, send_conditioning)
        # Everything underscore-prefixed is for the log, never for the wire.
        meta = {k: pr.pop(k) for k in list(pr) if k.startswith("_")}
        ref_slug = meta.get("_reference_slug")
        job, wall = submit(args.endpoint, pr,
                           args.cold_timeout if i == 0 else 600.0)

        rec = {
            "plate": plate,
            "kind": kind,
            "reference_slug": ref_slug,
            "figures_depicted": meta.get("_figures", 0),
            "conditioning": meta.get("_conditioning", "n/a"),
            "conditioning_sent": bool(send_conditioning),
            "wall_s": round(wall, 3),
            "status": job.get("status"),
            "delayTime_ms": job.get("delayTime"),
            "executionTime_ms": job.get("executionTime"),
        }
        out = job.get("output") or {}
        if isinstance(out, dict):
            rec["model_load_s"] = out.get("model_load_s")
            rec["render_s"] = out.get("render_s")
            rec["total_s"] = out.get("total_s")
            rec["gpu"] = out.get("gpu")
            rec["ip_adapter"] = out.get("ip_adapter")
            # The worker echoes what it actually built the graph with, so a plate's
            # conditioning is checkable after the fact rather than inferred from the
            # request we believe we sent.
            rec["reference_strength_used"] = out.get("reference_strength")
            rec["reference_start_used"] = out.get("reference_start")
            if out.get("image_png_b64"):
                # The comparison set renders 0008 and 0013 twice, once per
                # conditioning arm, so the filename has to carry the arm or the
                # second render silently overwrites the evidence for the first.
                suffix = "" if send_conditioning else "-nocond"
                (run_dir / f"{plate}{suffix}.png").write_bytes(
                    base64.b64decode(out["image_png_b64"]))
                rec["fidelity"] = compare_to_home(plate, out["image_png_b64"])
            elif out.get("error"):
                rec["error"] = out["error"]
        else:
            rec["output_repr"] = repr(out)[:300]

        results.append(rec)
        fid = rec.get("fidelity") or {}
        fidtxt = ("identical" if fid.get("identical")
                  else (f"{fid.get('differing_pixels')} px differ" if fid.get("compared")
                        else ""))
        print(f"{kind:4s} {plate}  {rec['status']:9s} wall {wall:7.2f}s  "
              f"delay {rec['delayTime_ms']}ms  exec {rec['executionTime_ms']}ms  "
              f"render {rec.get('render_s')}s  {fidtxt}")
        if rec.get("gpu"):
            print(f"       gpu: {rec['gpu']}")

    # --- the idle window: worker warm, nothing sent -------------------------
    print(f"\nidle window: {args.idle_window:.0f}s warm and doing nothing")
    t_idle0 = time.time()
    states = []
    while time.time() - t_idle0 < args.idle_window:
        h = R.get(f"https://api.runpod.ai/v2/{args.endpoint}/health", timeout=30)
        if h.status == 200:
            w = h.json.get("workers", {})
            states.append({"t": round(time.time() - t_idle0, 1), **w})
        time.sleep(10)
    print(f"  worker states over the window: "
          f"{[(s['t'], s.get('idle'), s.get('ready'), s.get('running')) for s in states]}")

    print("\nreading the balance until it settles (it lags by minutes)...")
    b_after = settled_balance()

    warm = [r for r in results if r["kind"] == "warm" and r.get("render_s")]
    warm_render = sorted(r["render_s"] for r in warm)
    median = warm_render[len(warm_render) // 2] if warm_render else None
    cold = results[0]

    summary = {
        "tier": args.tier,
        "endpoint": args.endpoint,
        "started_utc": t_start,
        "cold": cold,
        "warm_render_s_sorted": warm_render,
        "warm_render_median_s": median,
        "warm_n": len(warm_render),
        "idle_window_s": args.idle_window,
        "idle_worker_states": states,
        "balance_before": b_before,
        "balance_after_settled": b_after,
        "cost_usd": round(b_before - b_after, 10),
        "results": results,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    print(f"\ncold start (wall)     {cold['wall_s']}s  "
          f"(delay {cold.get('delayTime_ms')}ms, exec {cold.get('executionTime_ms')}ms, "
          f"ComfyUI boot {cold.get('model_load_s')}s)")
    print(f"warm render median    {median}s  (n={len(warm_render)})  {warm_render}")
    print(f"home baseline         7.595 s (n=8, pg-41)")
    print(f"cost                  ${b_before - b_after:.10f}")
    if median:
        billed_s = (b_before - b_after)
        print(f"cost per warm plate   see FINDINGS.md; total billed ${billed_s:.10f} "
              f"across {len(results)} renders")
    print(f"\nsaved {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
