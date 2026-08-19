# Demo runbook

The card. **Run everything from the repo root**, in one terminal: that `cd` is
the only state any command inherits. No endpoint id to copy or paste; the tools
work it out themselves.

Why each number is what it is: [DEMO-NOTES.md](DEMO-NOTES.md). Read that once
before the talk, not during.

```bash
cd /home/kb/Desktop/projects/scriptorium-flash
python3 tools/endpoint_id.py       # want one id. An error here: "Endpoint missing", below
```

---

## T-15

### 1. Free the GPU. Every time.

```bash
sudo systemctl stop comfyui
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv \
  | grep -Ei 'comfy|python|ollama' || echo "  clear"
curl -s localhost:11434/api/ps     # want size_vram == size, or {"models":[]}
```

Want `clear`. Chrome and VS Code always hold a few hundred MB; that is fine. What
matters is `comfyui`, a stray `python`, `ollama`. ComfyUI is a boot service, not a
window: never `kill -9` it, give `systemctl stop` up to 30 s, and re-check rather
than assume. If `size_vram` is the smaller number, `ollama stop qwen3.5:9b`.

A contended desktop does not spoil the renders (those are on Runpod). It spoils
the wall clock, which is 74% orchestration: 325.24 s became 744.91 s the one time
this was skipped.

### 2. Is it alive?

```bash
python3 tools/runpod_http.py \
  "https://api.runpod.ai/v2/$(python3 tools/endpoint_id.py)/health"
```

Want `idle`, `ready` or `running`. `initializing` and `throttled` are **not**
warm. Throttled is common and is not an error: see the fault table.

### 3. Warm it, then warm it again

```bash
python3 tools/prewarm.py --workers 4
```

The second pass is the proof. `--straggler-grace` defaults to 60 s, so a stalled
request costs about 70 s rather than 300 s; the abandoned job keeps running and
still warms its worker. Pass `--straggler-grace 0` only if you specifically want
an exact depth count and have five minutes to spend on it.

**Read `distinct workers`, not `COMPLETED` and not the health count.** It comes
from each job's `workerId`, so it is measured rather than inferred: it is how
deep the fleet actually is. A `COMPLETED` says a request was answered, not that
it was answered by a worker of its own.

**The go/no-go is `distinct workers` >= 2 and `boot 0` on the repeat pass.** A
`LOWER BOUND: n request(s) abandoned` on that line is fine as long as the number
shown is already >= 2 — a bound of 2 is a pass. A bound of 1 is inconclusive, not
a failure: run it again, which costs ~70 s.
Four is reachable but not reliable: on 2026-08-19 most passes reported
`throttled` between 1 and 3 and landed on 2 or 3 deep, and one clean pass reached
`idle 4, throttled 0` in **13.74 s**. If you get 1, you are one deep: go narrow,
say so out loud, and quote per-render numbers instead of a fan-out. Do not
re-provision to chase a 4.

Read these columns for whether a given request was warm:

| Column | Cold | Warm |
|---|---|---|
| `pull+start` (`delayTime`) | **476-492 s** on a first image pull | **0.0 s**, milliseconds not seconds |
| `boot` (`model_load_s`) | 3.005 s, or 3.513 s | **0** |
| `render` at 512 px | 4.821 s | **1.96-5.2 s** across every clean warm render on 2026-08-19 (**1.51 s** originally). Treat under ~6 s with `boot 0` as warm. |
| `render` at 832 px | 10.511 s | **3.737-3.897 s** |

Each request now prints the moment it lands, with the worker that served it, so
a slow one is visible instead of looking like a hang. A `FAILED` row prints the
handler's own message under it. A `render timed out after 300.0s` is intermittent
and does not mean a cold fleet: see the fault table.

**Budget 500 s, not 30.** Measured passes range from 24.47 s to 494.714 s
depending on whether a worker already holds the 17.7 GB image.

**Warm it again just before you speak.** The fleet does stay up by itself at a
measured $0.00, but "up" is not "responsive": every one of the ten 300 s stalls
measured on 2026-08-19 was a request dispatched *instantly* (`pull+start` under
10 s) to a worker sitting idle, while requests that queued behind other work
(`pull+start` in the tens or hundreds of seconds) always rendered. A fully warm
`idle 4, throttled 0` fleet still stalled two of four. Treat a long idle gap as
the risk, not the safety.

### 4. Check the fallback before you need it

```bash
node tools/verify_reader.mjs https://scriptorium-reader.vercel.app pg-120 \
     /tmp/reader-verify
```

Ends with `PASS -- the deployed reader downloads and reads the book end to end.`
Use that production alias, never the hashed URL `vercel deploy` prints.

**It retries by itself now.** The checkout is ~330 requests for 6.8 MB and one run
in seven died partway on 2026-08-19, with the reader showing `Failed to fetch` and
the card at `incomplete`. That is the reader working correctly: it offers **Resume
download**, and the check now clicks it, up to three attempts. A `checkout stalled
... clicking "Resume download"` line is not a failure. Only `FAILED at: checkout`
is, and it writes a screenshot.

---

## The demo, in order

### 1. The warm-up, shown rather than described  ·  bounded to ~25 s

```bash
python3 tools/prewarm.py --workers 4 --deadline 30
```

**`--deadline 30` is not optional on stage, and `--straggler-grace` is not a
substitute.** A request can stall for the handler's full 300 s. The grace is
measured from the last result, so two staggered stalls defeat it: measured, a
pass with `--straggler-grace 15` still ran **320.46 s**. `--deadline` is an
absolute cap on the whole pass. Measured three times at 34 s, 31 s and 32 s
against a 30 s cap.

**Run it once.** Abandoning bounds your wait but does not free the worker: the
job runs on to its own 300 s timeout holding that worker. Three bounded passes
back to back left `inProgress: 4, inQueue: 6` and the later ones completed
nothing. One pass on stage, then move on.

Show the `boot 0` column and the `served by` ids, and say why `COMPLETED` was not
enough. If a `RENDER STALL` line appears, it is worth saying out loud: it is a
real intermittent fault, you know exactly what it is, and it does not mean the
fleet is cold. That reads better than pretending it did not happen.

**If you are risk-averse, skip this step entirely and open on step 3.** The single
warm render is 5 s and has reproduced three times within 0.2 s. This step is the
one with a tail.

### 2. The live bake  ·  ~5-6 min

```bash
OUT=runs/pg-41-live KEEP_ENDPOINT=1 ./tools/headline_bake.sh
```

**Both variables matter.** `OUT` stops this run overwriting the committed
evidence behind the headline. `KEEP_ENDPOINT=1` stops step 6 deleting the
endpoint you still need for step 3.

It prints its own comparison. **Five measured runs against home's 388.63 s:**
302, 309, 323, 325.24 and 347 s. **Quote "about 5 to 6 minutes, against 6.5 at
home", not a single figure** — the spread is 45 s and you do not control which
end you land on. Every run beat home; none came close to halving it.

While it runs, say the ceiling rather than the speedup. Text and orchestration
stayed home and were **70-82%** of the run across those five, so **Amdahl's floor
is 242-248 s** every time. Image rendering was only **15-27%** of the wall clock,
and the variation in that share is the whole story: the 347 s run was one worker
deep and spent 93 s rendering; the 302 s run was deeper and spent 46 s.

Warm render median per bake: **5.02, 5.26, 5.47, 5.47 s** (n=16-17 each).

**Do not promise a fan-out.** Configured concurrency of 4 has run 1.249 and 1.881
wide on identical code, and three consecutive bakes on 2026-08-19 ran against
fleets 1, 3 and 2 workers deep. The caller does not control it, and it is worth
45 s of wall clock.

**The bake pre-warms itself, with `--straggler-grace 60`.** In 2 of those 3 runs a
request stalled in that preamble and was released at ~68 s instead of 300 s. Do
not remove that flag: without it, two of three live demos gain four minutes before
the bake starts.

### 3. One warm render  ·  ~5 s

```bash
python3 tools/prewarm.py --workers 1 --size 832
```

**5.06 s** end to end, **3.897 s** of it the render, `delayTime` 23 ms.
Reproduced 2026-08-19 at **5.18 s / 3.737 s / 0.0 s**, so this one is solid.
Honest only because the worker is warm, which is what T-15 established.

The safe form on stage is the range and its cause: **a warm plate takes about
2.8 s alone and about 5 s inside a bake, and where it lands is decided by how wide
Runpod's scaler opened.** Do not promise a single per-render figure to an audience
that can watch the fleet width change.

### 4. The book  ·  ~2 min

<https://scriptorium-reader.vercel.app>

*Treasure Island*: 91 renders on Runpod for **$0.4282544446**. Open it, turn to a
page with an illustration. Say the limit before anyone finds it: static export, so
highlights and reading position do not persist. Everything else works.

---

## If it goes wrong, in this order

1. **Live bake**, end to end.
2. **Warm single render**, ~5 s, against the already-warm worker.
3. **The showcase book**: static, nothing live to fail.

Fall down the ladder rather than debugging upward. Each rung is independent of the
one above it.

## Failure modes, and one action each

Every one of these was observed by this project, not imagined.

| Failure | How you know | Do this |
|---|---|---|
| **Pre-warm looks stuck** | some workers have printed, one has not | Each request prints the second it lands, with its elapsed time and the worker that served it, so a gap means one request is genuinely still out. Give it up to 300 s: past that it is the render stall below. **Ctrl-C is safe** — it does not cancel the jobs, they keep running and the workers still come up warm. You lose the report, not the warmth. |
| **Throttled workers** | `/health` shows `throttled: 3`: Runpod has no free 4090 | **Wait and poll `/health`, it is free.** Observed clearing in 5 s once and ~40 s another, full `idle: 4` by 80 s. **Do not re-provision**: you pay a fresh cold start and are still queued. Not cleared in two minutes means availability-bound: go narrow, say so, drop to the warm single render. |
| **A render stalls at ~300 s** | a `FAILED` row whose `error` reads `render timed out after 300.0s` | **Intermittent, and it does not mean a cold fleet.** It is `RENDER_TIMEOUT_S` in [handler.py](../flash-imagegen/handler.py#L41): ComfyUI never returned an image. Ten were observed on 2026-08-19, all between 300.7 s and 310.9 s. Every one had `pull+start` under 10 s (dispatched instantly to an idle worker) and **no request that queued behind other work ever stalled**. It is **not** throttling, **not** a wedged worker (the same worker serves other requests in the same pass in single digits) and **not** concurrency (`max_concurrency` is 1, and a worker holding a single request stalled while another served three). No mechanism is known, only that correlation. **Read `workers warm` and `distinct workers`, not the `FAILED`** — the pass warms the fleet anyway. If you are time-boxed, `--straggler-grace 60` stops waiting after 60 s idle: the jobs keep running and still warm their worker, but `distinct workers` then reads as a lower bound, so do not use it for the go/no-go pass. |
| **A request comes back `FAILED` fast** | the `error` line names a `ValueError` or a missing field | A bad request, not a bad fleet. Fix the input; nothing to re-provision. |
| **Narrow scaler** | `NOTE: 4 requests were answered by 1 distinct worker(s), not 4` | Nothing to do, the caller does not control it. Re-run the pre-warm, expect the bake to queue rather than fan out, and quote per-render numbers (4.3080 s, n=91) instead of wall clock. |
| **Cold-load plate** | a render reports `model_load_s` above zero mid-bake | `python3 tools/cold_load_plates.py --book-id <BOOK>` to name them, then `python3 tools/remediate_cold_plates.py --book-id <BOOK>` to replace them. **Before teardown**: the endpoint has to be alive to re-render. |
| **Gone-cold standby** | `pull+start` in the hundreds of seconds on a worker you thought was warm | Re-run the pre-warm and budget **~490 s**, of which 478.2 s is image pull. This is what T-15 exists to prevent. Inside eight minutes of speaking, skip to the book. |
| **Reader checkout stalls** | `verify_reader.mjs` prints `checkout stalled ... clicking "Resume download"` | Nothing: that is the retry doing its job, and the reader offering `Resume download` is the designed recovery for a dropped fetch. One run in seven on 2026-08-19. Only `FAILED at: checkout` after three attempts is a real failure, and it leaves a screenshot in the shot directory. |
| **Endpoint missing** | `endpoint_id.py` says there is none | Eight minutes to recover: see [DEMO-NOTES.md](DEMO-NOTES.md#recovering-a-missing-endpoint). Inside eight minutes of speaking, go straight to the book. |

## Two things not to claim

- **The showcase book's wall clock is not a comparison.** Contaminated by a
  GPU-contention stall and by foreign renders inside its window, and
  `bake_timing.py`'s own integrity guards flagged it. The per-render numbers are
  sound; the end-to-end figure is not.
- **88 of the 91 shipped images are verified warm** from their own echoes. Three
  were regenerated and are warm by inference, because the regen route does not
  record the worker's echo. Say "inference", not "verified", about those three.

---

## After the talk

The endpoint costs nothing at idle, so there is no rush.

```bash
runpodctl serverless delete "$(python3 tools/endpoint_id.py)" && \
  runpodctl serverless list       # confirm. Never trust the delete's exit code.
sudo systemctl start comfyui
python3 tools/settle_balance.py --out runs/demo-day-settle.log
```

`settle_balance.py` takes six consecutive identical reads, 45 s apart. **A stable
balance is not a settled one**, and here is that in one line: run at
`--reads 3 --gap 20` while a paid bake was actively rendering, it reported
`settled: 3 identical reads over 40 s`. The charge had simply not landed yet.
**Run it after the teardown, and do not lower the defaults.**

**Order matters.** Delete the endpoint first, then settle. Settling while workers
are still warm measures a bill that is still being written.
