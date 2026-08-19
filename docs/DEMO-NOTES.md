# Demo notes

The evidence behind [DEMO-RUNBOOK.md](DEMO-RUNBOOK.md). Nothing here is a step to
follow: it is why each step in the card exists, and what was measured to put it
there. Read it once before the talk, not during.

---

## Why step 1 is "free the GPU", and why it is a T-15 step

**What ComfyUI actually costs**, measured on this desktop on 2026-08-19: the card
is an RTX 5070 holding **12,227 MiB**, and ComfyUI had **6,940 MiB** of it,
**57%**, having rendered nothing for seven hours. Everything else on the desktop
came to **710 MiB** between all of Chrome, VS Code, the file manager, a text
editor and the terminal. Free memory with ComfyUI up: **3,204 MiB**.

`comfyui.service` starts at boot and runs headless as
`main.py --listen 0.0.0.0 --port 8188`. That `0.0.0.0` is deliberate (cross-host
access from Chronicle) and unauthenticated, so any machine on the LAN can queue
renders onto this card while you are standing on stage. The journal from the
evening before shows **1,313 renders** between 15:00 and 23:16, and none of them
are this project's: no bake here has ever been more than 91 plates, and they
render on Runpod.

```bash
journalctl -u comfyui --since "-16 hours" | grep -c "Prompt executed"
```

It prompts for a password, which is why it belongs at T-15 rather than on stage.
`TimeoutStopSec=30`, and a stop that lands mid-render can use all of it. A
`kill -9` reads as a crash to systemd (`Restart=on-failure`, `RestartSec=5`) and
you get a fresh ComfyUI five seconds later holding the memory again. Put it back
afterwards with `sudo systemctl start comfyui`; the unit is enabled, so a reboot
restores it by itself.

**Why the ollama check is separate.** The text steps are 74% of the bake and run
on `qwen3.5:9b`, which wants **5.30 GB resident**. It does not fit beside
ComfyUI, so ollama loads the fraction that does and runs the rest on the CPU.
Stopping ComfyUI frees the memory but does not repair a model that has already
loaded badly: it stays where it landed until something unloads it. `size_vram`
equal to `size` is the only thing separating a healthy resident model from a
squeezed one, and an `ollama` line in the `nvidia-smi` grep is not automatically
contamination, because it is this project's own text model.

**What contamination looks like.** The Cycle 6 rehearsal bake took **744.91 s**
against the headline's **325.24 s**, and the renders were not the problem: image
rendering was **60.38 s** against 59.74 s, within a second. Every one of the
419.67 s of difference was orchestration on this machine, and `bake_timing.py`
named the cause itself: *"20 ComfyUI renders in the window belong to nothing in
this bake."* One transform went from 2.523 s to **26-155 s** on a shared card.
The renders are on Runpod and are safe. The orchestration is not, and the
orchestration is most of the wall clock.

---

## Why `COMPLETED` is not warmth

In the Cycle 4 pre-warm, all four requests returned `COMPLETED` and exactly one
worker had loaded a model. That was read as "the other three were served by that
same already-warm worker, so the fleet is one deep", and Cycle 5 reproduced it.

**That reading was an inference, and the inference is unsound.** `model_load_s`
says only whether *this* request loaded a model. Four requests answered by four
already-warm workers load nothing at all and were reported as a one-deep fleet.
Measured on 2026-08-19: a 2-worker pass loaded exactly one model, the old NOTE
called it one worker deep, and the jobs' `workerId` fields showed **two distinct
workers**. So the Cycle 4 and Cycle 5 depth figures are unproven, not confirmed.

`prewarm.py` now reports `distinct workers` from `workerId`, which is measured
rather than inferred. `model_load_s` is kept as colour: it still separates a cold
render from a warm one, which is a different question from fleet depth.

**Fidelity, not just wall clock.** Cycle 4 measured that the first render after a
cold model load does not produce the same pixels as a render against a resident
model: 842,339 of 1,011,712 pixels different on plate 0001, reproducibly, on
home's own card and identically inside the container. Home's baseline bake
renders portraits first, so every page plate in it drew against a resident model.
If four workers each render their first plate cold, four of the sixteen differ
from home for a reason that has nothing to do with the GPU.

**There is no such thing as "the" pre-warm time.** Five measured passes:
**494.714 s**, **302.41 s**, **121.88 s**, **50.984 s**, **24.47 s**, a factor of
twenty on the same script and the same worker count. It depends entirely on
whether a worker already holds the image. Budget the worst case.

**`ready` does not predict latency.** The health route reported `idle: 1,
ready: 1` before a request that still paid a 31.387 s cold start. The load-time
report is the instrument; health is corroboration.

## The 300 s stall, and two theories that died

`RENDER_TIMEOUT_S` in `flash-imagegen/handler.py` is 300 s, and it raises
`render timed out after 300.0s` when ComfyUI has not returned an image by then.
`prewarm.py` did not read the status response's `error` field, so for four cycles
it printed `boot None  render None` and the fault table called it a flaky job.
It reads it now, which is how the rest of this was found.

Ten occurrences on 2026-08-19, every one landing between 300.66 s and 310.93 s.

**It is not a wedged worker.** That was the first theory, and it was written into
the tool before it was checked. `sbvgs5tz3nk3cv` failed one request at 308.37 s
and completed another in 7.02 s **in the same pass**.

**It is not concurrency either.** That was the second theory. `app.py` sets
`max_concurrency` 1, so requests to one worker are sequential, and the decisive
pass had a worker serve three sequential requests successfully while a different
worker holding a **single** request stalled.

**It is not throttling.** Stalls occurred at `throttled: 0`.

**What all ten share is a low `delayTime`**, 0.0 s to 9.1 s: each was dispatched
instantly, to a worker that was sitting idle and available. The mirror image
holds too, and it is the stronger half of the observation: **no request that
queued behind other work ever stalled.** Requests with `delayTime` of 147 s,
162 s, 167 s, 213 s and 228 s all rendered normally.

The first reading of this was "a worker that had only just come up", and the
final verification run killed it: a fleet reporting `idle 4, ready 4, running 0,
throttled 0` -- fully warm, nothing newly started -- still stalled two of four.
So it is not newness. What correlates is *idleness*: the first request to reach a
worker that has been sitting unused is the one at risk, which is also what the
older "gone-cold standby" note was circling.

That is a correlation across ten samples, not a mechanism. Nobody has read the
worker's ComfyUI log at the moment of a stall, and until somebody does this stays
an observation. The practical consequence is in the runbook: a long idle gap
before you speak is the risk, so pre-warm close to the demo rather than trusting
that a fleet left up is a fleet that will answer.

**What to do with it:** nothing. The pass warms the fleet regardless, which the
health line shows and the `FAILED` row hides. Read `workers warm` and `distinct
workers`, not the `FAILED`.

**And one thing not to do, which was tried.** `prewarm.py --straggler-grace 60`
stops waiting once the other requests have landed. It looks like the obvious fix
and it is not: on its first live run it abandoned three requests that were not
stalled at all (health showed `running: 3`, they were mid-render), and `distinct
workers` then reported **1** against a fleet that was really 4 deep. Abandoning
early destroys the one measurement the pass exists to make, and slow-but-fine
(233 s observed) is not separable from stalled (300 s) by duration. The flag
survives, defaulted off, for when you are time-boxed and would rather have a warm
fleet than a correct depth reading.

**`idle` and `ready` are the same workers under two names.**

**`idle` and `ready` are the same workers under two names.** Every health sample
this project has taken has `idle == ready`, and summing them made `prewarm.py`
report `workers warm 8` against a `workersMax` of 4. The warm count is
`max(idle, ready) + running`.

**Standby is free.** `workersStandby` tracks `workersMax` rather than
`workersMin`, so the fleet stays warm by itself at a measured **$0.00**, four
times over. That is a defect
([runpod/flash#364](https://github.com/runpod/flash/issues/364)); on stage it is
free cold-start insurance. Leave the fleet alone once it is warm.

---

## The numbers, and which one to quote

**The bake.** Rendering fell from 123.34 s to 59.74 s, but text and orchestration
stayed home and are 74% of the run, so **Amdahl's floor is 251.5 s** against a
measured **325.24 s** and a home baseline of **388.63 s**. The interesting number
is the ceiling, not the speedup.

**Four more runs on 2026-08-19**, all exit 0, all reporting `counts match
artifacts`:

| Run | Wall | Text | Orch | Rendering | Warm median | Fleet depth |
|---|---:|---:|---:|---:|---:|---:|
| a | 302 s | 53.1% | 29.2% | 46 s / 15.2% | 5.26 s (n=17) | deeper |
| 1 | 347 s | 47.3% | 22.4% | 93 s / 26.7% | 5.47 s (n=17) | 1 |
| 2 | 309 s | 52.5% | 26.2% | 58 s / 18.7% | 5.02 s (n=16) | 3 |
| 3 | 323 s | 49.7% | 26.5% | 65 s / 20.1% | 5.47 s (n=17) | 2 |

With the committed 325.24 s that is five measurements spanning **302-347 s**,
every one under home's 388.63 s and none near half of it. Text plus orchestration
was 70-82% throughout, which puts **Amdahl's floor at 242-248 s** in all five: the
floor is the stable quantity here, not the total.

**The variance has a cause and it is visible in the table.** Image rendering
ranged from 46 s to 93 s, and it tracks fleet depth: the slowest run was one
worker deep. That is the fan-out caveat arriving as a measurement rather than an
argument.

**The bake's own pre-warm carries `--straggler-grace 60`** (headline_bake.sh step
3, showcase_bake.sh at the prompts_draft gate). In 2 of the 3 runs a request
stalled there and was released at ~68 s rather than 300 s. It is correct in that
position and wrong for the go/no-go pass, because the preamble wants warmth and
the go/no-go wants a depth reading.

**Do not promise a fan-out.** Configured concurrency was 4 both times it was
measured, and it ran **1.249** wide once and **1.881** wide the other time. Same
image, same pin, same code. Whether Runpod's scaler opens the workers is not
something the caller controls.

**Say which median you are quoting.** A warm plate is **4.2790 s** against home's
**7.595 s** (**1.78x**); across the whole bake including two cold-load renders it
is **4.7725 s** (**1.59x**). The published per-image speedup uses the
conservative one.

**And say what was in flight beside it, because that moves the number.** Three
bakes on the same image, the same pin and the same configured concurrency of 4
gave warm medians of **4.2790 s**, **4.3080 s** and **5.0260 s**, at
`overlap_factor` 1.249, 1.881 and 1.778. A single request against an idle warm
worker, nothing else in flight, rendered in **2.813 s**, the fastest this project
has recorded.

So the safe form on stage is the range and its cause: **a warm plate takes about
2.8 s alone and about 5 s inside a bake, and where it lands is decided by how wide
Runpod's scaler opened, which the caller does not control.**

**One thing unexplained, and written down as unexplained.** The rehearsal's
fifteen warm renders split into two clusters, six at 3.517-3.792 s and nine from
5.026 s to 13.862 s, with almost nothing between them. Concurrency is the obvious
cause and `pg-120` contradicts it, having run wider still and stayed at 4.3080 s.
If someone asks: we know the range, we know it moves with load, and we have not
run the controlled experiment that would say why.

**The book.** *Treasure Island*: 91 renders, 65 plates, 25 portraits and a cover,
rendered on Runpod for **$0.4282544446**. It is a static export, so highlights and
reading position do not persist (saving them needs a PUT and there is no server).
Reading, search, the cast page and every illustration work fully.

**Use the production alias**, `scriptorium-reader.vercel.app`, never the hashed
`...-<hash>-<team>.vercel.app` URL that `vercel deploy` prints. Vercel's
deployment protection gates the hashed deployment URLs and leaves the production
alias public, so checking the wrong one will tell you the site is down when it is
not.

---

## Recovering a missing endpoint

Three things, in order, from the repository root.

1. `find . -path '*/.flash/resources.pkl' -delete`. The cache is written relative
   to the working directory, not `--app-dir`, and a stale one makes the provision
   print a plausible id and create nothing, with no error.
2. `RUNPOD_REGISTRY_AUTH_ID=<id> ~/.local/share/uv/tools/runpod-flash/bin/python tools/provision_client_endpoint.py --app-dir flash-imagegen`.
   **That interpreter, not `python3`**, because `runpod_flash` lives in the Flash
   CLI's own uv environment.
3. `python3 tools/endpoint_id.py` again, **which is the only test that works**.
   The provision prints an id either way, and elapsed time does not distinguish
   them: a genuine provision has been measured at both 3.29 s and 0.62 s.

Then a full cold start, about eight minutes. Inside eight minutes of speaking, go
straight to the book.
