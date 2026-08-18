# Demo runbook

The live demo, minute by minute. Every command here is paste-ready and
self-contained: no variable is inherited from an earlier block, and every one
starts by saying where to run it.

Fill in your endpoint id once, at the top of your terminal, and paste it into
each command:

```bash
cd /home/kb/Desktop/projects/scriptorium-flash
runpodctl serverless list      # the id is the "id" field
```

> Everything below assumes the render endpoint already exists. If
> `runpodctl serverless list` returns `[]`, go to **Endpoint missing** in the
> failure table — and know that recovering costs about eight minutes.

---

## T-15 — before you speak

Four steps. Do not skip the second one; it is the whole reason this section
exists.

### 1. Is it alive?

```bash
cd /home/kb/Desktop/projects/scriptorium-flash && runpodctl serverless list
```

Expect one endpoint. `[]` means it is gone.

```bash
curl -s https://api.runpod.ai/v2/<ENDPOINT-ID>/health
```

Want `idle`, `ready` or `running`. `initializing` and `throttled` are **not**
warm.

### 2. Warm it, and verify warmth by the load-time report

```bash
cd /home/kb/Desktop/projects/scriptorium-flash && \
  python3 tools/prewarm.py --endpoint <ENDPOINT-ID> --workers 4
```

Then **run it again**. The second pass is the proof.

### The warmth-verification signature

**Never trust `COMPLETED`.** In the Cycle 4 pre-warm, all four requests returned
`COMPLETED` and exactly one worker had loaded a model — the other three were
served by that same already-warm worker. The fleet was one deep, not four, and
nothing in the status said so. Cycle 5 reproduced it exactly.

Read these fields instead, from `prewarm.py`'s per-worker lines:

| Field | Cold | Warm |
|---|---|---|
| `pull+start` (`delayTime`) | **476–492 s** on a first image pull | **0.0 s** — milliseconds, not seconds |
| `boot` (`model_load_s`) | 3.005 s, or 3.513 s | **0** |
| `render` at 512 px | 4.821 s | **~1.51 s** |
| `render` at 832 px | 10.511 s | **3.897 s** |

**There is no such thing as "the" pre-warm time.** Five measured passes:
**494.714 s**, **302.41 s**, **121.88 s**, **50.984 s**, **24.47 s** — a factor
of twenty, on the same script and the same worker count. It depends entirely on
whether a worker already holds the image. Budget the worst case and be pleased
when it is the best.

And read the two lines `prewarm.py` prints when it is not satisfied:

```
NOTE: 1 of 4 requests reported a model load. The rest were served by an
      already-warm worker, so this warmed 1 distinct worker(s), not 4.
WARNING: asked for 4 warm workers, health reports 1.
```

**A clean second pass shows `boot 0` on every worker and `workers warm 4`.** That
is the only state worth walking on stage with.

One caveat that has already bitten: **`ready` does not predict latency.** The
health route reported `idle: 1, ready: 1` before a request that still paid a
31.387 s cold start. The load-time report is the instrument; health is
corroboration.

### 3. Then leave it alone

`workersStandby` tracks `workersMax`, not `workersMin`, so the fleet stays warm
by itself — at a measured **$0.00**, four times over. That is a defect
([runpod/flash#364](https://github.com/runpod/flash/issues/364)); on stage it is
free cold-start insurance.

### 4. Check the fallback works before you need it

```bash
cd /home/kb/Desktop/projects/scriptorium-flash && \
  node tools/verify_reader.mjs https://scriptorium-reader.vercel.app pg-120 \
       /tmp/reader-verify
```

Ends with `PASS -- the deployed reader downloads and reads the book end to end.`

**Use the production alias**, `scriptorium-reader.vercel.app` — never the hashed
`…-<hash>-<team>.vercel.app` URL that `vercel deploy` prints. Vercel's deployment
protection gates the hashed deployment URLs and leaves the production alias
public, so checking the wrong one will tell you the site is down when it is not.

---

## The demo, in order

### 1. The warm-up, shown rather than described  ·  ~1 min

Run the pre-warm live if the fleet is already warm — it is fast, and the output
*is* the point. Show the `boot 0` column and say why `COMPLETED` was not enough.

### 2. The live bake  ·  ~5–6 min

```bash
cd /home/kb/Desktop/projects/scriptorium-flash && \
  OUT=runs/pg-41-live KEEP_ENDPOINT=1 ./tools/headline_bake.sh <ENDPOINT-ID>
```

**Both environment variables matter.** `OUT` keeps this run from overwriting the
committed evidence behind the headline number. `KEEP_ENDPOINT=1` stops step 6
from deleting the endpoint you may still need for step 3.

It prints its own comparison when it finishes — the bake's wall clock in whole
seconds, beside the home baseline of **388.63 s**. The measured run behind the
headline came in at **325.24 s**.

While it runs, the thing to say is what the decomposition shows: rendering fell
from 123.34 s to 59.74 s, but text and orchestration stayed home and are 74% of
the run, so **Amdahl's floor is 251.5 s**. The interesting number is the ceiling,
not the speedup.

**Do not promise a fan-out.** Configured concurrency was 4 both times it was
measured, and it ran **1.249** wide once and **1.881** wide the other time. Same
image, same pin, same code. Whether Runpod's scaler opens the workers is not
something the caller controls.

### 3. One warm render  ·  ~5 s

```bash
cd /home/kb/Desktop/projects/scriptorium-flash && \
  python3 tools/prewarm.py --endpoint <ENDPOINT-ID> --workers 1 --size 832
```

**5.06 s** end to end, of which **3.897 s** is the render and `delayTime` is
23 ms. That is the honest live-demo number, and it is honest only because the
worker is warm — which is what step 1 established.

Say which median you are quoting. A warm plate is **4.2790 s** against home's
**7.595 s** (**1.78×**); across the whole bake including two cold-load renders it
is **4.7725 s** (**1.59×**). The published per-image speedup uses the
conservative one.

### 4. The book  ·  ~2 min

<https://scriptorium-reader.vercel.app>

*Treasure Island*: 91 renders, 65 plates, 25 portraits and a cover, rendered on
Runpod for **$0.4282544446**. Open it, turn to a page with an illustration.

Say the limit before anyone finds it: it is a static export, so highlights and
reading position do not persist — saving them needs a PUT and there is no server.
Reading, search, the cast page and every illustration work fully.

---

## If it goes wrong, in this order

1. **Live bake** — the whole thing, end to end.
2. **Warm single render** — one request, ~5 s, against the already-warm worker.
3. **The showcase book** — static, no server, nothing live to fail.

Fall down the ladder rather than debugging upward. Each rung is independent of
the one above it.

## Failure modes, and one action each

Every one of these was observed by this project, not imagined.

| Failure | How you know | Do this |
|---|---|---|
| **Throttled workers** | `/health` shows `throttled: 3` — Runpod has no free RTX 4090 to give you | **Wait, and poll `/health` — it is free.** Observed clearing twice: after about five seconds once, and after about 40 s in the Cycle 6 rehearsal, reaching a full `idle: 4, ready: 4` about 80 s in. **Do not re-provision** — you will pay a fresh cold start and still be queued. If it has not cleared in a couple of minutes the fleet is availability-bound rather than configuration-bound: go narrow, say so out loud, and drop to the warm single render. |
| **A request comes back `FAILED`** | `prewarm.py` prints `FAILED` with `boot None  render None` and a small `pull+start` | Re-send it. A `pull+start` under a second means it reached a live worker and failed there, so the fleet is healthy and one job is not — `/health` will show `"failed": 1` and the other workers still `idle`/`ready`. Do not re-provision and do not re-warm the whole fleet. Seen once, in the Cycle 6 rehearsal, where it also held the pass open for five minutes: if you are short of time, kill it rather than waiting. |
| **Narrow scaler** | `NOTE: 1 of 4 requests reported a model load`, or `WARNING: asked for 4 warm workers, health reports 1` | Nothing to do — the caller does not control it. Re-run the pre-warm, expect the bake to queue rather than fan out, and quote per-render numbers (4.3080 s, n=91) instead of wall clock. |
| **Cold-load plate** | a render reports `model_load_s` above zero mid-bake | `python3 tools/cold_load_plates.py --book-id <BOOK>` to name them, then `python3 tools/remediate_cold_plates.py --book-id <BOOK> --endpoint <ENDPOINT-ID>` to replace them. **Before teardown** — the endpoint has to be alive to re-render. It re-warms first, because a regen against a spun-down worker just swaps one cold image for another. |
| **Gone-cold standby** | `pull+start` in the hundreds of seconds on a worker you thought was warm | Re-run the pre-warm and budget **~490 s**, of which 478.2 s is image pull. This is exactly what T-15 exists to prevent. If you are inside eight minutes of speaking, skip to the book. |
| **Endpoint missing** | `runpodctl serverless list` returns `[]` | Three things, in order, from the repository root. `find . -path '*/.flash/resources.pkl' -delete` — the cache is written relative to the working directory, not `--app-dir`, and a stale one makes the provision print a plausible id and create nothing with no error. Then `RUNPOD_REGISTRY_AUTH_ID=<id> ~/.local/share/uv/tools/runpod-flash/bin/python tools/provision_client_endpoint.py --app-dir flash-imagegen` — **that interpreter, not `python3`**, because `runpod_flash` lives in the Flash CLI's own uv environment. Then **`runpodctl serverless list` again, which is the only test that works**: the provision prints an id either way, and elapsed time does not distinguish them — a genuine provision has been measured at both 3.29 s and 0.62 s. Then a full cold start: about eight minutes. Inside eight minutes of speaking, go straight to the book. |

---

## Two things not to claim

- **The showcase book's wall clock is not a comparison.** It is contaminated by
  a GPU-contention stall and by foreign renders inside its window, and
  `bake_timing.py`'s own integrity guards flagged it. The per-render numbers are
  sound; the end-to-end figure is not.
- **88 of the 91 shipped images are verified warm** from their own echoes. Three
  were regenerated and are warm by inference, because the regen route does not
  record the worker's echo. Say "inference", not "verified", about those three.

---

## After the talk

The endpoint costs nothing at idle, so there is no rush. When you are done:

```bash
cd /home/kb/Desktop/projects/scriptorium-flash && \
  runpodctl serverless delete <ENDPOINT-ID> && \
  runpodctl serverless list        # confirm. Never trust the delete's exit code.
```

Then settle the balance before recording what it cost:

```bash
cd /home/kb/Desktop/projects/scriptorium-flash && \
  python3 tools/settle_balance.py --out runs/demo-day-settle.log
```

Six consecutive identical reads, 45 s apart. A stable balance is not a settled
one.
