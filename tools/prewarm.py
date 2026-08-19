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

    ./prewarm.py --workers 4                 # endpoint id resolved by endpoint_id.py
    ./prewarm.py --workers 4 --dry-run       # spend nothing
    ./prewarm.py --endpoint <id> --workers 4 # or name it, if there are several

Credentials are never handled here: see tools/runpod_http.py.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, FIRST_COMPLETED, wait
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import runpod_http as R  # noqa: E402
import endpoint_id as EP  # noqa: E402

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
    # `idle` and `ready` are the SAME workers under two names, not two groups.
    # Summing them reported `workers warm 8` on an endpoint whose workersMax is
    # 4, and every health sample this project has taken has idle == ready. Take
    # one of them, not both. `running` is a worker mid-request, which is warm on
    # its own. `initializing` is not warm, and `throttled` is a worker Runpod has
    # not found a GPU for.
    booted = max(int(w.get("idle", 0)), int(w.get("ready", 0)))
    return booted + int(w.get("running", 0)), w


def _message(err: object) -> str | None:
    """The handler's message, not the JSON envelope Runpod wraps it in.

    A failed handler arrives as a string of JSON holding `error_message` and a
    full traceback. Printed raw it is 2 KB of noise whose first 200 characters
    are `{"error_type": ...`, so the one line that matters -- `render timed out
    after 300.0s` -- never reaches the screen.
    """
    if not err:
        return None
    if isinstance(err, str):
        try:
            return json.loads(err).get("error_message") or err
        except (json.JSONDecodeError, AttributeError):
            return err
    return str(err)


def one_warmup(endpoint: str, index: int, size: int, timeout_s: float,
               abandon: threading.Event | None = None) -> dict:
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
                # The handler's own message, and the only thing that says WHY a
                # request failed. Without it a FAILED row reads `boot None
                # render None`, which looks like a flaky job and is usually not:
                # two failures at 310.93 s and 301.36 s were both handler.py's
                # RENDER_TIMEOUT_S of 300 s, and nothing on screen said so.
                "error": _message(body.get("error")) or (
                    out.get("error") if isinstance(out, dict) else None),
                # Ground truth for fleet depth. `model_load_s` only says whether
                # THIS request loaded a model, so four requests served by four
                # already-warm workers reported "warmed 1 distinct worker" and
                # meant nothing of the kind. workerId says who actually answered.
                "worker_id": body.get("workerId"),
            }
        if abandon is not None and abandon.is_set():
            return {"worker": index, "status": "ABANDONED", "job_id": job_id,
                    "wall_s": round(time.monotonic() - t0, 3),
                    "error": "still running server-side; the client stopped waiting"}
        time.sleep(2.0)
    return {"worker": index, "status": "CLIENT_TIMEOUT", "wall_s": round(time.monotonic() - t0, 3)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--endpoint", default=None,
                    help="serverless endpoint id; omit to resolve it from runpodctl")
    ap.add_argument("--workers", type=int, default=4,
                    help="how many workers to warm; must match the endpoint's max")
    ap.add_argument("--size", type=int, default=512, help="warm-up render size")
    ap.add_argument("--timeout", type=float, default=1800.0,
                    help="per-request budget; a cold worker pulls ~17.7 GB first")
    ap.add_argument("--out", type=Path, help="write the result JSON here")
    # ON by default, at 60 s, after this was defaulted off and then back on.
    #
    # Off was wrong. The argument for off was that abandoning early under-reports
    # `distinct workers` -- true, it once printed 1 against a fleet really 4 deep.
    # But the line is labelled LOWER BOUND, and the go/no-go is ">= 2": a lower
    # bound of 2 is already a pass, and a lower bound of 1 costs one 70 s re-run.
    # Paying the handler's full 300 s on every pass to avoid that is a far worse
    # trade, and the ~300 s stall is frequent enough that it is the common case,
    # not the edge case.
    #
    # The abandoned jobs keep running server-side and still warm their worker,
    # which is what the pass is for. Pass --straggler-grace 0 to wait them out
    # when you specifically want an exact depth reading.
    # An ABSOLUTE cap on the whole pass, which --straggler-grace is not and cannot
    # be. The grace is measured from the last result of any kind, so two staggered
    # stalls defeat it: the first one failing at ~303 s resets the clock and the
    # pass ran 320.46 s under `--straggler-grace 15`, measured. On stage you need
    # "this ends in N seconds" with no argument about it.
    #
    # CAVEAT, measured: abandoning bounds YOUR wait, it does not free the worker.
    # An abandoned job runs on to its own 300 s handler timeout and keeps its
    # worker busy the whole time. Three back-to-back `--deadline 30` passes put
    # `inProgress: 4, inQueue: 6` on a 4-worker endpoint and the second and third
    # passes completed nothing at all, queued behind the first pass's leftovers.
    # Use it for ONE bounded pass in front of an audience. Do not loop it.
    ap.add_argument("--deadline", type=float, default=0.0,
                    help="hard cap in seconds on the whole pass; anything still "
                         "pending is abandoned but KEEPS RUNNING and keeps its "
                         "worker busy, so do not run repeatedly. 0 means no cap")
    ap.add_argument("--straggler-grace", type=float, default=60.0,
                    help="seconds to wait for stragglers after the other requests "
                         "land, then stop waiting (the jobs keep running and still "
                         "warm their worker). 0 waits the handler's full 300 s")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    args.endpoint = args.endpoint or EP.resolve()

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

    # Report each request AS IT LANDS, not after the slowest one. `pool.map`
    # returns a list, so it blocks until every future is done and prints nothing
    # meanwhile: a pass with three requests finished in 10 s and one stalled for
    # 300 s showed a blank screen for five minutes and was read as a hang. It was
    # not hung, and there was no way to tell from the outside.
    t0 = time.monotonic()
    results = []
    abandon = threading.Event()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending = {pool.submit(one_warmup, args.endpoint, i, args.size, args.timeout,
                               abandon) for i in range(args.workers)}
        last_landed = time.monotonic()
        while pending:
            # OFF unless --straggler-grace is passed; see the flag for why. When
            # it is on: once the others have landed, wait that long and then stop
            # waiting. The job keeps running server-side and the worker still ends
            # up warm, which is the only thing the pass was for.
            if args.deadline > 0 and (time.monotonic() - t0) > args.deadline:
                if not abandon.is_set():
                    print(f"  [{time.monotonic() - t0:>6.1f}s] deadline "
                          f"{args.deadline:.0f}s reached; abandoning {len(pending)} "
                          f"pending request(s), which keep running and still warm "
                          f"their worker", flush=True)
                abandon.set()
            elif (args.straggler_grace > 0 and results
                    and (time.monotonic() - last_landed) > args.straggler_grace):
                print(f"  [{time.monotonic() - t0:>6.1f}s] giving up on "
                      f"{len(pending)} straggler(s) after {args.straggler_grace:.0f}s "
                      f"idle; they keep running and still warm their worker",
                      flush=True)
                abandon.set()
            done, pending = wait(pending, timeout=2.0, return_when=FIRST_COMPLETED)
            for fut in done:
                r = fut.result()
                results.append(r)
                if r.get("status") == "COMPLETED":
                    last_landed = time.monotonic()
                print(f"  [{time.monotonic() - t0:>6.1f}s] worker {r['worker']}  "
                      f"{r['status']:<12} wall {r.get('wall_s', 0):>8.2f}s  "
                      f"pull+start {(r.get('delayTime_ms') or 0)/1000:>7.1f}s  "
                      f"boot {r.get('model_load_s')}  render {r.get('render_s')}  "
                      f"{r.get('gpu') or '-'}", flush=True)
                if r.get("error"):
                    print(f"           error  {str(r['error']).strip()[:200]}", flush=True)
                if r.get("worker_id"):
                    print(f"           served by  {r['worker_id']}", flush=True)
    elapsed = time.monotonic() - t0

    after_n, after = workers_ready(args.endpoint)
    cards = sorted({r.get("gpu") for r in results if r.get("gpu")})
    print(f"\nelapsed           {elapsed:.2f}s")
    print(f"workers warm      {after_n}  {json.dumps(after)}")
    print(f"distinct cards    {len(cards)}")
    for c in cards:
        print(f"  {c}")

    # N completed jobs is NOT N warm workers, and this is the second attempt at
    # measuring the difference. The first inferred it from `model_load_s`: a
    # request that loaded a model proved a cold worker, so "1 of 4 loaded" was
    # read as a fleet one deep. That inference is wrong in the common direction.
    # Four requests served by four ALREADY-WARM workers load nothing and were
    # reported as a one-deep fleet; a measured 2-worker pass on 2026-08-19 loaded
    # one model, was called one deep, and `workerId` showed two distinct workers.
    # `workerId` is the ground truth, so use it and keep the load count as colour.
    loaded = [r for r in results if (r.get("model_load_s") or 0) > 0]
    served_by = sorted({r["worker_id"] for r in results if r.get("worker_id")})
    abandoned = [r for r in results if r.get("status") == "ABANDONED"]
    if served_by:
        bound = "  LOWER BOUND: " + f"{len(abandoned)} request(s) abandoned" if abandoned else ""
        print(f"distinct workers  {len(served_by)}  (from workerId, not inferred){bound}")
        for w in served_by:
            got = [r["worker"] for r in results if r.get("worker_id") == w]
            print(f"  {w}  served request(s) {', '.join(map(str, got))}")
    if served_by and len(served_by) < args.workers:
        print(f"\nNOTE: {len(results)} requests were answered by {len(served_by)} "
              f"distinct worker(s), not {args.workers}. The fleet is "
              f"{len(served_by)} deep; a bake behind it will queue on those "
              f"workers rather than fan out. ({len(loaded)} of them loaded a "
              f"model on this pass; the rest were already warm.)")

    # A ~300 s FAILED is handler.py's RENDER_TIMEOUT_S: ComfyUI did not return an
    # image and the handler gave up. Observed four times on 2026-08-19.
    #
    # Two theories died here, so both are written down. It is NOT a wedged
    # worker: `sbvgs5tz3nk3cv` failed one request at 308.37 s and completed
    # another in 7.02 s in the same pass. It is NOT concurrency either: app.py
    # sets max_concurrency 1, and a worker that served three sequential requests
    # answered all three while a worker holding a SINGLE request stalled. It is
    # not throttling. What all ten observed stalls share is a `delayTime` of
    # 0.0-9.1 s -- dispatched instantly to an idle worker -- while every request
    # that queued behind other work (147-228 s) rendered fine. A fully warm
    # `idle 4, throttled 0` fleet still stalled two of four, so it is idleness
    # rather than newness. No mechanism is known; the pass warms the fleet
    # regardless.
    stalled = sorted({r["worker_id"] for r in results
                      if r.get("worker_id") and r.get("status") == "FAILED"
                      and "timed out" in str(r.get("error") or "")})
    if stalled:
        print(f"\nRENDER STALL on {', '.join(stalled)}: ComfyUI did not return an "
              f"image within the handler's 300 s budget.")
        print("  Intermittent, and not a permanently broken worker: the same worker")
        print("  usually serves other requests in the same pass in single digits.")
        print("  Every observed stall had pull+start under 10 s, dispatched instantly")
        print("  to an idle worker; queued requests have never stalled. No lever.")
        print("  Read `workers warm` above, not this: the pass warms the fleet")
        print("  regardless, and a stall does not mean a cold fleet.")

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
        # The headline metric, and it has to survive into the evidence file:
        # headline_bake.sh keeps prewarm.json as the record of how deep the fleet
        # was behind a bake, and inferring that later from model_load_s is the
        # mistake this field exists to replace.
        "distinct_workers": sorted({r["worker_id"] for r in results if r.get("worker_id")}),
        "results": sorted(results, key=lambda r: r["worker"]),
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(record, indent=2) + "\n")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
