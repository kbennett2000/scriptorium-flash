#!/usr/bin/env python3
"""Bring every worker on an endpoint to a warm, model-resident state.

Two independent reasons, and the second one is the surprise.

**Wall clock.** A fan-out across workers that have not pulled the image yet is
four cold starts wearing a trenchcoat. The 4090 pass measured a cold start at
431.73 s wall, of which 414.9 s was image pull. Sixteen plates spread over four
cold workers would report a bake time that is really a pull time.

**Fidelity.** Cycle 4 measured that the first render after a cold model load does
not produce the same pixels as a render against a resident model -- 842,339 of
1,011,712 pixels different on plate 0001, reproducibly, on home's own card, and
identically inside the container. Home's baseline bake renders portraits first, so
every page plate in it drew against a resident model. If four workers each render
their first plate cold, four of the sixteen differ from home for a reason that has
nothing to do with the GPU. Pre-warming removes that variable.

The warm-up render is deliberately small (512x512 by default). Size does not change
what matters -- the checkpoint, LoRA and VAE all load on the first render whatever
the resolution -- so a small one buys the same residency for less billed time.

    ./prewarm.py --endpoint <id> --workers 4
    ./prewarm.py --endpoint <id> --workers 4 --dry-run   # spend nothing

Credentials are never handled here: see tools/runpod_http.py.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import runpod_http as R  # noqa: E402

# Enough to force the full model set to load; small enough not to pay for pixels
# nobody will look at.
WARM_PROMPT = "oil painting, a quiet room, warm-up"
WARM_SEED = 1


def health(endpoint: str) -> dict:
    resp = R.get(f"https://api.runpod.ai/v2/{endpoint}/health", timeout=30)
    return resp.json if resp.status == 200 else {}


def workers_ready(endpoint: str) -> tuple[int, dict]:
    body = health(endpoint)
    w = body.get("workers") or {}
    # `idle` and `ready` are both "booted and not working". `running` is a worker
    # mid-request, which is also warm. What is NOT warm is `initializing`.
    return int(w.get("idle", 0)) + int(w.get("ready", 0)) + int(w.get("running", 0)), w


def one_warmup(endpoint: str, index: int, size: int, timeout_s: float) -> dict:
    t0 = time.monotonic()
    payload = {
        "prompt": WARM_PROMPT,
        "negative": "",
        # A distinct seed per worker so no two requests are byte-identical: an
        # identical graph can be served from a cache without loading anything,
        # which would defeat the entire point of warming.
        "seed": WARM_SEED + index,
        "width": size,
        "height": size,
        "lora": True,
    }
    started = R.post(f"https://api.runpod.ai/v2/{endpoint}/run", {"input": payload}, timeout=120)
    if started.status != 200:
        return {"worker": index, "status": "SUBMIT_FAILED", "http": started.status}
    job_id = started.json.get("id")
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        st = R.get(f"https://api.runpod.ai/v2/{endpoint}/status/{job_id}", timeout=60)
        if st.status == 200 and st.json.get("status") in (
            "COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"
        ):
            body = st.json
            out = body.get("output") or {}
            return {
                "worker": index,
                "status": body.get("status"),
                "wall_s": round(time.monotonic() - t0, 3),
                "delayTime_ms": body.get("delayTime"),
                "executionTime_ms": body.get("executionTime"),
                "model_load_s": out.get("model_load_s") if isinstance(out, dict) else None,
                "render_s": out.get("render_s") if isinstance(out, dict) else None,
                "gpu": out.get("gpu") if isinstance(out, dict) else None,
            }
        time.sleep(2.0)
    return {"worker": index, "status": "CLIENT_TIMEOUT", "wall_s": round(time.monotonic() - t0, 3)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--endpoint", required=True)
    ap.add_argument("--workers", type=int, default=4,
                    help="how many workers to warm; must match the endpoint's max")
    ap.add_argument("--size", type=int, default=512, help="warm-up render size")
    ap.add_argument("--timeout", type=float, default=1800.0,
                    help="per-request budget; a cold worker pulls ~17.7 GB first")
    ap.add_argument("--out", type=Path, help="write the result JSON here")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.dry_run:
        print(f"endpoint {args.endpoint}")
        print(f"would send {args.workers} concurrent {args.size}x{args.size} renders, "
              f"seeds {WARM_SEED}..{WARM_SEED + args.workers - 1}")
        print(f"prompt {WARM_PROMPT!r}")
        print("\ndry run, nothing submitted")
        return 0

    before_n, before = workers_ready(args.endpoint)
    print(f"endpoint          {args.endpoint}")
    print(f"workers warm now  {before_n}  {json.dumps(before)}")
    print(f"sending           {args.workers} concurrent {args.size}x{args.size} renders\n")

    t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(
            lambda i: one_warmup(args.endpoint, i, args.size, args.timeout),
            range(args.workers),
        ))
    elapsed = time.monotonic() - t0

    for r in sorted(results, key=lambda r: r["worker"]):
        print(f"  worker {r['worker']}  {r['status']:<12} wall {r.get('wall_s', 0):>8.2f}s  "
              f"pull+start {(r.get('delayTime_ms') or 0)/1000:>7.1f}s  "
              f"boot {r.get('model_load_s')}  render {r.get('render_s')}  "
              f"{r.get('gpu') or '-'}")

    after_n, after = workers_ready(args.endpoint)
    cards = sorted({r.get("gpu") for r in results if r.get("gpu")})
    print(f"\nelapsed           {elapsed:.2f}s")
    print(f"workers warm      {after_n}  {json.dumps(after)}")
    print(f"distinct cards    {len(cards)}")
    for c in cards:
        print(f"  {c}")

    # N completed jobs is NOT N warm workers, and the difference is invisible
    # unless you look for it. A worker that loads the model reports a non-zero
    # model_load_s; one that was already resident reports 0 and renders in about
    # a third of the time. In the first headline run, four jobs completed but only
    # ONE reported a model load, so three were served by a worker that was already
    # warm -- the fleet was one deep, not four, and the bake behind it fanned out
    # 1.25-wide against a configured 4.
    loaded = [r for r in results if (r.get("model_load_s") or 0) > 0]
    if results and len(loaded) < args.workers:
        print(f"\nNOTE: {len(loaded)} of {len(results)} requests reported a model load. "
              f"The rest were served by an already-warm worker, so this warmed "
              f"{len(loaded)} distinct worker(s), not {args.workers}.")

    # The point of the exercise is N warm workers. Say so plainly if it did not
    # happen, rather than letting the bake discover it.
    if after_n < args.workers:
        print(f"\nWARNING: asked for {args.workers} warm workers, health reports {after_n}. "
              f"Runpod's scaler may not have opened them all; the bake will queue "
              f"rather than fan out, and its first renders on any cold worker will "
              f"not be pixel-comparable to home.")

    record = {
        "endpoint": args.endpoint,
        "requested_workers": args.workers,
        "warm_before": before, "warm_after": after,
        "warm_after_count": after_n,
        "elapsed_s": round(elapsed, 3),
        "size": args.size,
        "distinct_cards": cards,
        "results": sorted(results, key=lambda r: r["worker"]),
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(record, indent=2) + "\n")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
