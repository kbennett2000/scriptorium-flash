# Findings

Every number this project produces lives here and nowhere else. The README, the
ADRs, and the talk cite this file. Nothing numeric gets retyped by hand
somewhere else, because retyped numbers drift.

Rules for entries:

- **Measured, not estimated.** If a number is an estimate, it says so and says
  what it is an estimate of.
- **Dated**, newest first.
- **Sourced.** Every number names the file, log, or page it came from, so it can
  be checked.
- Runpod costs are real money. Every cent is logged, including zero.
- Claude Code usage figures are estimates of usage against a Claude Max
  subscription. They are **not charges** and are labelled as such.

---

## Runpod spend ledger

| Date | What | Cost | Source |
|---|---|---|---|
| 2026-08-17 | Cycle 2, entire cycle — read-only account queries only | $0.00 | `runpodctl billing {pods,serverless,network-volume}`, all-time window, all return `[]` |
| 2026-08-17 | Cycle 3, task 1 — `hello-flash` deployed, 4 requests, deleted after 458 s | **$0.0066245833** | `clientBalance` $49.9945861833 → $49.9879616000, settled and re-read |
| 2026-08-17 | Cycle 3, task 3 — 26 hosted text-model calls across two models, plus parameter and schema isolation | **$0.0838488300** | `clientBalance` $49.9879616000 → $49.9041127700; cross-checked against the endpoints' own `cost` fields |
| 2026-08-18 | Cycle 3, task 5 — render pass on the 24 GB tier: cold start + 6 warm plates + 90 s idle | **$0.0376933074** | `clientBalance` $49.9041127700 → $49.8664194626, settled after teardown |
| 2026-08-18 | Cycle 3, task 6 — render pass on a pinned RTX 4090: cold start + 6 warm plates + 90 s idle | **$0.0439145185** | `clientBalance` $49.8664194626 → $49.8225049441, settled after teardown |
| 2026-08-18 | Cycle 4, task 0 — default-bake equivalence check: 16 prompt replays and 13 local renders, all on home hardware | $0.00 | no Runpod resource touched; `clientBalance` unread and unmoved |
| 2026-08-18 | Cycle 4, task 1 — Python 3.11.15 container: one local build, 13 local renders on home's RTX 5070 | $0.00 | no Runpod resource touched |
| 2026-08-18 | Cycle 4, gate A — pinned 4090 endpoint, cold start + comparison render set + idle tail | **$0.0254124222** | `clientBalance` $49.8225049441 → $49.7970925219, settled over ten identical reads |
| 2026-08-18 | Cycle 4, gate B — pre-warm 4 workers + full `pg-41` bake (18 renders) + warm-worker demo + idle tail | **$0.1037042686** | `clientBalance` $49.7970925219 → $49.6933882533, settled after teardown; `runs/pg-41-runpod/balance-settle.log` |
| 2026-08-18 | Cycle 5, showcase bake — full `pg-120` bake (91 renders: 65 plates, 25 portraits, 1 cover) + pre-warm + 3 cold-load regens + warm-worker demo + idle tail | **$0.4282544446** | `clientBalance` $49.6933882533 → $49.2651338087, settled over six identical reads 45 s apart; `runs/pg-120-runpod/balance-settle.log` |

**Total Runpod spend to date: $0.7294523746**

Cycle 3: **$0.1720812392**, against a $0.20 estimate in the brief and a $0.45
ceiling. Cycle 4: **$0.1291166908**, against a $0.20 plan and a **$0.30 ceiling**
— both gates came in under their own estimates ($0.05 → $0.0254, $0.15 →
$0.1037).

Cycle 5: **$0.4282544446**, in one line, against a **$0.55 ceiling** Kris raised
from $0.40 to cover a book 5.6x longer than Sleepy Hollow. The pre-render
estimate was $0.21 expected and $0.45 worst case; the outcome landed at the
pessimistic end, and for a good reason — the estimate's optimistic case assumed
the fan-out would stay narrow as it did in Cycle 4. It did not. Four workers
opened, the bake ran 1.88 wide instead of 1.25, and four workers alive with
60-second idle tails is what the extra money bought. Faster and dearer, from the
same configuration, decided by Runpod's scaler rather than by us. Closing balance
**$49.2651338087**.

The total reconciles two ways to ten decimal places: the ledger rows sum to
$0.7294523746, and the account has moved $49.9945861833 → $49.2651338087, which
is the same number.

Cycle 2 spent nothing: all three billing categories returned `[]` over an
all-time window and `clientBalance` never moved.

**Two different instruments are needed for Cycle 3's spend, because neither one
works everywhere.**

*Serverless* spend has to be read off the balance. `runpodctl billing serverless`
returns `[]` over both today's window and an all-time window despite a charge
that demonstrably occurred, so the billing-history API cannot corroborate
anything at this scale.

*Public-endpoint* spend is the opposite: the endpoint's own `cost` field in each
response is exact — `total_tokens ×` the published rate, verified to the cent on
two models — while the balance is a poor instrument for it because **it lags
charges by several minutes.**

That lag caused a wrong number earlier in this cycle. A reading taken sixty
seconds after the last call, and confirmed "stable", reported roughly a third of
the real spend and supported a confident claim that this account was billed 3.26×
under list price. It is not; there is no discount. A stable balance reading is
not a settled one, and the only safe balance comparisons in this file are the
ones taken minutes apart with nothing running in between.

Cycle 2's gates were never reached, because `flash` could not authenticate.
Cycle 3's are live.

---

## 2026-08-18 — Cycle 5

### Treasure Island: the pre-registered threshold failed, the audit passed, and the threshold was wrong

The showcase book is *Treasure Island*, Project Gutenberg #120, ingested as `pg-120` and
checked against its source before any GPU time, by the rule Cycle 1 established after
*Usher* silently lost 48% of its text and reported no warnings. The procedure is now a
script, `tools/verify_ingest.py`, so the second book is checked the same way as the
first rather than a similar way. Output kept at `runs/pg-120/ingest-verify.json`.

| Field | Value |
|---|---|
| Source words | **68,637** (after Project Gutenberg boilerplate is stripped) |
| Stored words | **67,813** |
| **Retention** | **98.80%** |
| Threshold, set in advance | **99.5%** |
| **Verdict against the threshold** | **FAIL** |
| Pages after pagination | 134 |
| Chapters detected | 34 |
| Ingest warnings | `[]` |
| Shortfall | 824 words, reconciling exactly to the enumerated lines |

**The threshold failed and the book was baked anyway. That is a waiver, and it is
recorded as one.** Moving the number afterwards to make it pass would have been the
dishonest option and a much easier one.

What the 824 words are, every one of them named and grouped:

| Group | Lines | Words | What it is |
|---|---:|---:|---|
| contents | 35 | 564 | the table of contents, dot leaders included |
| headings | 51 | 80 | the `PART` lines and Roman numerals, now the 34 chapter titles in `structure.json` |
| other | 31 | 180 | title, byline, the dedication to S.L.O., and the verse *To the Hesitating Purchaser* |

**Not one word of narrative prose is missing.** The stored text opens on the true first
line of chapter I — `The Old Sea-dog at the Admiral Benbow / Squire Trelawney, Dr.
Livesey, and the rest of these gentlemen having asked me…` — and closes on the true last
line of the book, `…the sharp voice of Captain Flint still ringing in my ears: "Pieces of
eight! Pieces of eight!"`. The 51 heading lines are not lost but relocated. The real loss
is the 146 words of front matter, of which the verse dedication is the only part a reader
would miss, and it appears nowhere in the bundle.

As on pg-41, `warnings: []` is the *bad* sign rather than the good one:
`chapters_undetected` fires only when detection finds nothing and the whole-text
fallback keeps everything, so its absence means `_chapters_from_headings` ran — the path
that drops text. Retention is the only thing that says whether that mattered.

**The metric is wrong, and that is the finding.** A retention figure that counts a
table of contents as body text is measuring the wrong denominator. Treasure Island's
contents page is 564 words of chapter titles and dot leaders — whitespace tokenizing
scores `THE BLACK SPOT . . . . . . 24` as nineteen words — and no edition would set it
as prose. Excluding it, retention is **99.62%**, which clears the threshold that was set.

pg-41 never exposed this because *Sleepy Hollow* has no contents page: the 99.5% figure
was calibrated on a book that could not exercise the case it fails on. **Fix deferred,
not applied:** retention should exclude contents pages and front matter from the
denominator before the next book is judged by it. Changing it in the middle of a book
it had just failed would have been indistinguishable from moving a goalpost, so it is
written down instead and left for a cycle with nothing riding on it.

A curiosity in the source, recorded rather than corrected: Gutenberg's own text numbers
chapter XVIII as `XXVII`. It is a typo in the source and it survives into the chapter
titles, because ingest reads headings rather than checking their arithmetic.

### The showcase book: 91 renders, the fleet finally opened, and it ran 1.88 wide

One complete `pg-120` bake, text steps at home, every render on a Runpod endpoint
(`tw7wlntgpdetsc`) pinned to a single `NVIDIA_GEFORCE_RTX_4090`, plates fanned out four
at a time. Sources: `runs/pg-120-runpod/{run.json,timing.json,prewarm.json,warm-demo.json,balance-settle.log}`.

| | |
|---|---:|
| Pages | 134 |
| Words stored | 67,813 |
| Plates | 65 |
| Portraits | 25 |
| Cover | 1 |
| **Renders** | **91** |
| Chapters | 34 |
| Bundle revision | 4 |
| Reader download | 7.14 MB across 320 files |

Against the Cycle 4 headline bake, this is **5.1× the renders** (91 against 18) on a book
**5.6× longer** (67,813 words against 12,187).

**The fan-out opened this time, and that is the difference from Cycle 4.**

| | Cycle 4, `pg-41` | Cycle 5, `pg-120` |
|---|---:|---:|
| Renders | 18 | 91 |
| Work the workers reported | 92.13 s | **456.36 s** |
| Wall clock that work occupied | 73.76 s | **242.67 s** |
| **`overlap_factor`** | **1.249** | **1.881** |
| Warm render median | 4.7725 s (n=18) | **4.3080 s (n=91)** |

Configured concurrency was 4 in both runs. Cycle 4 got 1.25 wide because only one worker
ever warmed and two sat throttled; this run reached **1.88 wide**, and `/health` during
the render phase showed four workers alive (`idle 1, running 3`). The same endpoint
configuration, the same image, the same pin — **the difference is whether Runpod's
scaler opened the workers**, which is not something the caller controls and not
something the configuration predicts. Two runs, two answers.

The warm median at 4.3080 s (n=91) sits within 1% of pg-41's warm-only 4.2790 s (n=16),
which is the reassuring part: 91 renders on a different book found the same per-image
number.

**The pre-warm defect reproduced exactly.** Four concurrent 512 px requests all returned
`COMPLETED`, and `prewarm.py` — carrying the Cycle 4 fix — reported the truth anyway:

```
NOTE: 1 of 4 requests reported a model load. The rest were served by an
      already-warm worker, so this warmed 1 distinct worker(s), not 4.
WARNING: asked for 4 warm workers, health reports 1.
```

Only worker 0 loaded a model (3.513 s, render 10.821 s); the other three reported
`model_load_s: 0` and rendered in 3.78–4.35 s. The whole pre-warm took **50.98 s**, not
the ~490 s Cycle 4 paid, because the image was already on a worker from provisioning —
a cold start is only cold once per worker.

**Two cold-load images shipped into the bake and were replaced before publication.**
`portrait-ben-gunn` (model load 3.508 s) and `portrait-hunter` (2.508 s) were each some
worker's first render after staging. Both were regenerated through the bakery's own
regen route while the endpoint was still up, which post-publish writes an additive `-rN`
variant beside the untouched original and bumps the bundle revision; the reader resolves
highest-`rN`, so it downloads the replacement.

**What cannot be claimed about that, and is not.** The bake's render phase records the
worker's whole echo, but **the regen route records only width, height and seed** — no
`model_load_s`. So 88 of the 91 shipped images are *positively verified* warm from their
own echoes, and 3 are warm by *inference*: they were rendered against a fleet whose
`/health` reported warm slots, and each returned in seconds rather than showing a ~3 s
stage. That is weaker evidence and it is labelled as such. The tooling was corrected to
say so rather than to report a clean sweep it could not see.

**The live-demo measurement.** One request against an already-warm worker immediately
after the bake, at 832×832: **7.19 s** end to end, of which **3.559 s** was the render,
`model_load_s` 0 and `delayTime` 1.1 s.

**Cost: $0.4282544446**, settled. Opening $49.6933882533, closing **$49.2651338087**,
against a $0.55 ceiling Kris raised for this book.

That is **1,402 billed worker-seconds** at $1.10/hr for 456.36 s of reported render work
— a ratio of 3.07, which is the price of four workers being alive with 60-second idle
tails rather than of the renders themselves. The endpoint existed for 61 minutes with
four standby workers throughout, and only the render window billed: **standby remained
$0.00 for the fourth cycle running**, measured here across a 45-minute stall in which the
balance did not move at ten decimal places.

**The settle loop earned itself on the first use.** The balance read
`49.2718678087` five times in a row across three and a half minutes, and then dropped
again to `49.2651338087` — a further $0.0067340000 posting late.
`render_bench.settled_balance()`, which accepts two equal reads 30 s apart, would have
recorded the wrong number, and that is exactly how Cycle 3's two `summary.json` files
came to disagree with the ledger. `tools/settle_balance.py` demands six identical reads
45 s apart and caught it.

**The wall clock is not comparable to pg-41 and is not offered as a headline.** The bake
took 50 m 48 s, but roughly 25 minutes of that is the GPU-contention stall described
below, and `bake_timing.py`'s integrity guards flagged the window themselves
(`COUNT MISMATCH`, and 44 foreign local ComfyUI renders attributed inside it, because
another session was rendering on the same box). The render-phase numbers above are
sound — they come from the workers' own echoes, not from log pairing — but the
end-to-end figure is contaminated and stating it as a comparison would be dishonest.

### The showcase book is on Vercel, and what it cannot do there

**<https://scriptorium-reader.vercel.app>** — the real reader, unmodified, serving
Treasure Island from a static export.

The reader's read path is five GET routes (`/health`, `/api/users`, `/api/library`,
`/api/library/{id}/manifest`, `/api/library/{id}/files/{path}`), and a published bundle
is immutable static files, so the whole thing mirrors onto a static host with no server
at all. `tools/export_static_reader.py` lays those routes out as files — importing
`resolve_reader_files` from the Scriptorium server rather than reimplementing the
highest-`rN`-wins rule — and a `vercel.json` rewrite resolves the one structural
conflict, that `/api/library` must be a file while `/api/library/{id}/` must be a
directory.

Verified in a real browser rather than by status code: `tools/verify_reader.mjs` drives
Chromium through the profile picker, the shelf, a full checkout of all 320 files, opening
the book, and a page with an illustration on it, failing on any unexpected 4xx or console
error. It passes.

**What it cannot do, stated plainly rather than left for someone to discover on stage:**
the sync routes are PUTs (`/api/sync/annotations/…`, `/api/sync/positions/…`), and they
have nowhere to go on a static host. Highlights and reading position will not persist
across devices. The reader already probes `/health` and degrades when the server is
unreachable, so this is a **reduced reader, not a broken one** — reading, search, the
cast page and every illustration work fully offline once the book is downloaded, which is
the whole of what a fallback demo needs.

One inconsistency worth recording: after the three regens the bundle manifest's own
`total_bytes_reader` reads 7.28 MB while `GET /api/library` computes 7.14 MB. The shelf
figure is the correct one — it resolves `-rN` variants, and the export matches it to the
byte. The manifest field counts superseded originals it should not.

### The home baseline assumes an uncontended GPU, and 388.63 s was measured on a quiet machine

The showcase bake stalled mid-way through its prompt phase, and the cause is worth more
than the delay was. `illustration-prompt` calls went from pg-41's **2.523 s** median to
**26–155 s**, a 10–60× collapse, with no change to the model, the prompt, or the code.

The machine explains it exactly. The home RTX 5070 has 12,227 MiB. Another user of the
same desktop was rendering through the shared local ComfyUI, which held **9,312 MiB** of
it. Squeezed into what was left, ollama kept **0.13 GB of `qwen3.5:9b`'s 6.19 GB** in
VRAM and ran the other 98% on the CPU:

```
$ curl -s localhost:11434/api/ps
qwen3.5:9b   size_vram=0.13GB   size=6.19GB
```

Once the other session ended and the model was unloaded so it would reload with room to
land, `size_vram` came back as **5.30 GB of 5.30 GB** and latency returned to
**1.9–2.8 s** — a 37× recovery, measured across the same transform on the same book
minutes apart.

**Two things follow, and both belong in the log.**

The first is a caveat this file owes its own headline. **The 388.63 s home baseline was
measured on a quiet machine**, with the whole card available to the text model. It is a
fair number and it is the right comparison, but it is a *best-case* home number, not a
typical one. A home bakery on a desktop somebody also uses will not reproduce it, and
nothing in the baseline says so until now.

The second is an argument for the rented card that this project had not thought to make.
The 4090 on Runpod is not competing with a browser, an editor, or somebody else's image
generation. Its 24 GB is not shared with whatever else the machine is doing. The talk has
been framing serverless GPU as *faster silicon plus fan-out*; **isolation is a third
thing, and on this evidence it is worth more than either** — 37× on the text steps
against 1.59× on the renders. It is also the one an audience running models on their own
desktops will recognize immediately.

Recorded rather than acted on: nothing was changed about how the bakery manages VRAM,
and no measurement in this file was re-run. The stall cost no money — the endpoint was
provisioned throughout with four standby workers and the balance did not move.
### The image is not 42 GB, and the number that matters is 17.72 GB

Three instruments describe this one image and they disagree, so earlier entries in
this file used two of them interchangeably. Measured together, on the same image on
the same day:

| Instrument | Value | What it is |
|---|---:|---|
| `docker images` DISK USAGE | **42.0 GB** | compressed blobs *and* the unpacked snapshot, added together |
| `docker history`, layers summed | **24.26 GB** | what it unpacks to on the worker |
| registry manifest, 19 layers summed | **17.72 GB** | **what Runpod pulls** |

17.72 + 24.26 = 42.0, to three significant figures. The 42 GB is not a size; it is
two sizes, counted twice by the containerd store. `docker images` also reports
CONTENT SIZE 17.7 GB in the next column, which agrees with the manifest.

This corrects the attribution earlier in this file, which reasoned about cold start
from "42 GB uncompressed against 41.7 GB — 0.7% larger". Both of those are
double-counted figures; the comparable pair is 17.66 → 17.72 GB, a 0.34% difference,
which makes the 63 s pull difference even less explicable by size than it looked.
The conclusion there does not change — it was already recorded as unattributed — but
the arithmetic offered in support of it should not be reused.

### The image carries two complete CUDA stacks, and PyTorch uses neither of the apt ones

The base is `nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04`, which apt-installs CUDA
12.8 (3.11 GB) and cuDNN 9 (1.05 GB). The torch wheels then bring their own, 4.30 GB
of `nvidia/*` packages inside site-packages.

`ldd` settles which set is live, and it is not close:

```
$ ldd /usr/local/lib/python3.11/dist-packages/torch/lib/libtorch_cuda.so
  libcudart.so.12    => .../nvidia/cuda_runtime/lib/libcudart.so.12
  libcublas.so.12    => .../nvidia/cublas/lib/libcublas.so.12
  libcudnn.so.9      => .../nvidia/cudnn/lib/libcudnn.so.9
  libcufft.so.11     => .../nvidia/cufft/lib/libcufft.so.11
  libcusparse.so.12  => .../nvidia/cusparse/lib/libcusparse.so.12
  libcusparseLt.so.0 => .../nvidia/cusparselt/lib/libcusparseLt.so.0
  libcurand.so.10    => .../nvidia/curand/lib/libcurand.so.10
  libnccl.so.2       => .../nvidia/nccl/lib/libnccl.so.2
```

Every one resolves into the pip wheels. Not one resolves to `/usr/local/cuda-12.8`
(2.79 GB) or to the apt `libcudnn*` in `/usr/lib/x86_64-linux-gnu` (1.00 GB). The
CUDA base image is 2.76 GB of pull that this workload never opens.

### The diet, priced in pulled bytes

Pull is **98%** of the cold start — 478.2 s of 489.82 s — so a diet is worth exactly
what it removes from the pull, at the measured **37.1 MB/s**. Compression ratios are
measured per layer rather than assumed, because they differ: safetensors are
already-compressed weights and shrink by 8%, while shared objects and Python trees
roughly halve. Produced by `tools/image_diet.py`, output kept at `runs/image-diet.txt`.

| Candidate removal | Pulled bytes saved | Pull time saved | Fidelity risk |
|---|---:|---:|---|
| Drop the CUDA base image (`nvidia/cuda` → `ubuntu:22.04`) | 2.76 GB | 74.5 s | none — proved unused by `ldd` |
| Store the CLIP vision encoder fp16 rather than fp32 | 1.16 GB | 31.4 s | **moves pixels; must pass `verify_port.py` first** |
| Drop `nccl` + `nvshmem` + `cusparseLt` from the torch wheels | 0.56 GB | 15.1 s | none if torch still imports |
| Drop the ComfyUI workflow-template media packages | 0.20 GB | 5.5 s | none |
| Store the SDXL VAE fp16 rather than fp32 | 0.15 GB | 4.2 s | **moves pixels; must pass `verify_port.py` first** |
| Drop `av`, `av.libs`, `botocore`, `boto3`, `OpenGL` | 0.09 GB | 2.5 s | none |
| **Total** | **4.94 GB** | **133.2 s** | |
| of which carrying no fidelity risk | 3.62 GB | 97.6 s | |

The two fp16 candidates are listed because they are real bytes, not because they are
recommended. This project's whole argument rests on pixel comparisons against home,
and re-quantising a weight file is exactly the kind of change that would invalidate
them. They are free to test locally with `verify_port.py`, and they should not be
adopted without that test. The SDXL base checkpoint is **already F16** (2,515 F16
tensors), so the largest file in the image offers nothing.

**What the diet actually buys.** 17.72 GB becomes 12.78 GB, 28% smaller, and the cold
start goes from **490 s to about 357 s**. Stated in the units a talk cares about: 8.2
minutes becomes 5.9 minutes. **The diet does not remove the cold start, it shortens
it**, and a demo still cannot hide a six-minute wait. The thing that removes the cold
start is the warm-up procedure, and that is free.

### The rebuild gate: about 3.5 hours of wall clock to save 2.2 minutes of cold start

Scaling the measured push — 17.72 GB in 3 h 56 m 53 s, an effective 1.246 MB/s from
this house — a 12.78 GB image re-pushes in about **2 h 51 m**. A base-image change
invalidates the build cache, so the build is nearer the 31 m 29 s first build than
the 12 m 35 s warm one, plus 127.3 s of model staging; call it 35 minutes. Local
pixel verification of anything fp16 is free and adds perhaps 10 minutes.

**Total: roughly 3 h 30 m to 4 h of wall clock, to take the cold start from 8.2 to
5.9 minutes.** No re-push has been made and none will be without a decision. This is
a wall-clock question against the days remaining before the talk, not a money
question — the push itself is free.

---

## 2026-08-18 — Cycle 4

### The default bake is unchanged by ADR-0036 and ADR-0037, proved three ways

Scriptorium master gained ADR-0036 (a book-wide owner negative prompt applied to
every plate) and ADR-0037 (per-plate video in the picture editor) on 2026-08-17,
and the `388.63 s` baseline this cycle is measured against was taken the same
day. If either had touched a bake where the owner supplied nothing, the baseline
would be citing one pipeline and this cycle would be measuring another.

It did not, and the check is worth more than the code reading that predicted it.

**1. The bakery was already running that code when the baseline was baked.** The
commits are dated 2026-08-17 09:02, but the source mtimes are 2026-08-13/14 and
the `scriptorium-bakery` unit started 2026-08-16 18:55 — the work was written
before it was committed. `library/pg-41/meta.json` carries `"negative": null`, a
key only post-ADR-0036 `build_meta` emits, and
`"pipeline_version": "v0.1.0-24-gfbb7e6f"`, which is ADR-0037's commit. So there
is no before-and-after: there is one pipeline, and the baseline is on it.

**2. Every request string replays byte-identically.** Re-running today's
`wrap_prompt` against the baseline's own job record, styles catalog and prompt
documents reproduces the stored `wrapped_prompt` and `negative_prompt` for all
**16 of 16** plates — 9 page plates, 6 portraits, 1 cover.

The guard is one expression. `wrap_prompt` folds the owner negative in as
`user_negative or ""` (`p7_render.py:225, 239`), and `_dedupe_terms`
(`:186-195`) skips empty terms, so `_dedupe_terms(a, b, c)` and
`_dedupe_terms(a, b, c, "")` return the same string. `bake_config["negative"]` is
`null` on this book. ADR-0037 never enters a bake at all: it touches
`reader/**`, `artsets/`, and adds `animate`/`video_health` to the imagegen client
without altering `txt2img`, `health`, `_map_error` or `_digest`, and its only
entry point is `POST /artsets/{user}/{book}/edits/{plate_id}/video-candidate`.

**3. Every plate seed-replays pixel-identically on the home GPU.** `verify_port.py`
rebuilds each plate from its own provenance — seed, prompt, negative, size,
reference portrait — submits it to the home ComfyUI, and compares against the
stored PNG.

| Plate | Figures | IP-Adapter weight / start | Differing pixels |
|---|---:|---|---:|
| 0001 | 1 | none (no reference) | **0** of 1,011,712 |
| 0003 | 1 | 0.5 / 0.3 | **0** |
| 0006 | 1 | 0.5 / 0.3 | **0** |
| 0008 | 2 | 0.35 / 0.4 | **0** |
| 0011 | 2 | 0.35 / 0.4 | **0** |
| 0013 | 3 | 0.35 / 0.4 | **0** |
| 0015 | 1 | 0.5 / 0.3 | **0** |
| 0018 | 1 | none (no reference) | **0** |
| 0020 | 2 | 0.35 / 0.4 | **0** |

Nine of nine. **The home-side numbers in this file are safe to cite.**

Free: 16 prompt replays and 13 local renders, all on the home RTX 5070. No
Runpod resource was touched.

### Removing `PYTORCH_JIT=0` moved the pixels not at all, and the proof is bit-for-bit

This is the measurement the Cycle 3 debt note was owed. The question was whether the
release-candidate interpreter and the disabled TorchScript were changing the output.

**The answer is no, exactly and measurably no.** The Cycle 4 container — real Python
3.11.15, TorchScript on — was sent four requests byte-identical to ones the Cycle 3
container answered on the same pinned card. All four returned **the same number of
differing pixels to the pixel**:

| Plate | Conditioning sent | Cycle 3 container (3.11.0rc1, JIT off) | Cycle 4 container (3.11.15, JIT on) |
|---|---|---:|---:|
| 0001 | none (no IP-Adapter) | 637,911 | **637,911** |
| 0003 | service default | 633,047 | **633,047** |
| 0008 | omitted | 993,300 | **993,300** |
| 0013 | omitted | 989,906 | **989,906** |

Four for four, to the last pixel, across the LoRA-only path and the IP-Adapter path.
Cycle 3 *inferred* that `PYTORCH_JIT=0` was not the cause of divergence, from the
fact that plate 0001 uses no IP-Adapter and diverged anyway. This measures it
directly: swap the interpreter, turn TorchScript back on, and not one pixel moves.

So the honest accounting of the rebuild is that it bought **correctness, not
fidelity**. The container no longer runs a 2022 release candidate and no longer
disables a feature home has on — which is worth having, and was the stated reason —
but nobody should expect it to have changed an image, and it did not.

### The conditioning gap is confirmed on Runpod hardware, and it splits the divergence

The same pass ran plates 0008 and 0013 **both ways** on the same worker, minutes
apart: once omitting the conditioning (reproducing Cycle 3's request) and once
sending the 0.35 / 0.4 that home actually sent.

| Plate | Figures | Omitted (Cycle 3's request) | Sent (home's request) | Attributable to conditioning |
|---|---:|---:|---:|---:|
| 0008 | 2 | 993,300 (98.2%) | **721,810 (71.3%)** | **26.9 points** |
| 0013 | 3 | 989,906 (97.8%) | **533,994 (52.8%)** | **45.0 points** |

The corrected figures land inside the band the single-figure plates already occupy —
0001 at 63.1% and 0003 at 62.6% — which is the silicon floor. Once the right
conditioning is sent, a multi-figure plate is no worse than a single-figure one, and
0013 is actually the *closest* plate to home in the whole set.

The worker echoes what it built the graph with, so this is checkable rather than
assumed: `weight=0.5 start=0.3` on the omitted arm, `weight=0.35 start=0.4` on the
sent arm.

**The split, stated plainly.** Cycle 3's 97.7–98.2% figures for plates 0008, 0011 and
0013 were the sum of two causes. Roughly 27 and 45 points of it were our own harness
sending a computation home never ran; the remaining 52–71% is silicon, and matches
what the untainted plates always showed. The correction recorded earlier this cycle
was right, and this is the measurement behind it.

### The single pin was honoured again, but `workersStandby` now tracks the *maximum*

`gpu=GpuType.NVIDIA_GEFORCE_RTX_4090` read back as `gpuTypeIds: ["NVIDIA GeForce
RTX 4090"]` and every one of the six requests ran on
`cuda:0 NVIDIA GeForce RTX 4090 : cudaMallocAsync`. Two cycles, two passes, single
pin honoured both times.

But `workers=(0, 4)` deployed:

```
workersMin: 0    workersMax: 4    workersStandby: 4
```

**This is worse than what `runpod/flash#364` reports.** That issue was written from
`workers=(0, 1)` producing `workersStandby: 1`, and reads as an off-by-one against
`min`. It is not: **standby tracks `max`**. Asking for a fleet that scales to zero and
peaks at four gets four workers held warm continuously. On this tier, four RTX 4090s
billed as active workers would be **$4.40/hr**.

They did not bill. `currentSpendPerHr` stayed `0` and the balance did not move while
four standby workers existed, which is consistent with the two null measurements
Cycle 3 recorded for one. But the exposure scales with `workersMax`, and a reader of
#364 would not know that. **A follow-up comment on #364 is owed**, with this readback.

*Cycle 5:* posted, with the readback, the endpoint id and a minimal reproduction —
[runpod/flash#364 (comment)](https://github.com/runpod/flash/issues/364#issuecomment-5332749910),
2026-08-18T19:03:09Z. The issue was still open with zero comments and no triage label
at the time of posting.

Also recorded for the first time: the endpoint's **`templateId: 17i3os12gk`**. Cycle 3
never captured one, because `PodTemplate(...)` creates it implicitly and nothing prints
it back.

### The rebuilt image is slower to pull and slower to render, and the pixels prove it is not the workload

| | Cycle 3 image | Cycle 4 image |
|---|---:|---:|
| Cold start, wall | 431.73 s | **489.82 s** |
| — of which image pull + worker start | 414.9 s | **478.2 s** |
| — of which ComfyUI boot | 6.5 s | **2.51 s** |
| Warm render median | 4.2175 s (n=6) | **5.289 s** (n=5) |
| Warm range | 4.025–7.363 s | 4.344–5.797 s |

The pull is 63 s longer against an image only 0.06 GB larger, and the warm renders are
about a second slower each. Neither is explained by the change: the pixel table above
proves the two containers compute *the same thing*, so this is the host, the physical
card, or a neighbour on it — not the workload.

That is worth stating because it is the second time this project has caught a
serverless timing difference that has nothing to do with the code under test, and it
sets a floor on how finely these numbers can be read. **A one-second difference in a
five-second render is not a signal on this platform** unless it repeats across passes.
ComfyUI booting in 2.51 s rather than 6.5 s points the same way.

### The billing API did show the charges, a day later, and it agrees with the balance to nine decimal places

Cycle 3 recorded that `runpodctl billing serverless` returned `[]` for charges
that demonstrably happened, and concluded that "**the billing-history API cannot
do that job**" — leaving the balance as the only instrument, and leaving one
question open in as many words: *"Whether the charge posts to the history later,
or whether sub-cent serverless usage never appears there, is not yet
established."*

Re-reading it today, unchanged commands, costs nothing:

| Category | Amount | Endpoint / GPU | Billed ms |
|---|---:|---|---:|
| `pods` | 0.0066245836 | NVIDIA RTX A4500 | 95,394 |
| `serverless` | 0.0439145190 | `h4rz8tmjkq35fu` | — |
| `serverless` | 0.0376933077 | `ugculdhag081uh` | — |
| `network-volume` | *(empty)* | — | — |

**Answer: they post later.** The API is not blind to sub-cent serverless usage; it
lags. Cycle 3's conclusion was right about what it could see at the time and wrong
about why, and the corrected statement is that the billing history is a *slow*
instrument rather than an absent one.

**Every balance-derived figure is now independently confirmed.** Against the
ledger, on charges derived from a completely different instrument:

| Ledger line | Ledger (balance delta) | Billing history | Difference |
|---|---:|---:|---:|
| Cycle 3, task 1 — hello-flash | 0.0066245833 | 0.0066245836 | 3 × 10⁻¹⁰ |
| Cycle 3, task 5 — 24 GB tier | 0.0376933074 | 0.0376933077 | 3 × 10⁻¹⁰ |
| Cycle 3, task 6 — pinned 4090 | 0.0439145185 | 0.0439145190 | 5 × 10⁻¹⁰ |

That is the project's own rule — *every cent verified against billing records* —
finally satisfied by the instrument it named, rather than by the balance standing
in for it. It also retires the concern that the balance might have been measuring
something other than this project's spend.

**Two details worth keeping.**

*A serverless endpoint billed under `pods`.* The hello-flash charge appears in
`runpodctl billing pods`, not `billing serverless`, with `gpuId "NVIDIA RTX
A4500"` — the card the `AMPERE_16` group actually handed out. Anyone reconciling
serverless spend by querying the serverless category alone would have missed a
third of this project's charges. Query all three.

*Public-endpoint spend still appears nowhere.* The billing total is
**$0.0882324104** against a ledger total of **$0.1720812392**. The missing
**$0.0838488288** is the hosted text-model spend to within 1.2 × 10⁻⁹ — and it is
in none of the three categories, because there is no
`runpodctl billing public-endpoints`. Cycle 2's reasoning about the
$0.0054138167 shortfall was sound: per-token spend moves the balance and is
invisible to this API. For that class of spend the balance remains the only
instrument, and the endpoint's own `cost` field the only cross-check.

### The two render `summary.json` files disagree with the ledger, and the ledger is right

`runs/runpod-render/*/summary.json` record `cost_usd` **0.0118587491** and
**0.0268797963**, against ledger figures of **$0.0376933074** and
**$0.0439145185**. The `balance_before` values match the ledger exactly; only the
"after" readings differ.

The cause is the failure this project already named once: a reading taken while
the balance was still settling. `settled_balance()` requires two consecutive equal
reads 30 s apart, which is a test for *stable*, and Cycle 3's own lesson is that
**a stable balance reading is not a settled one**. The field is called
`balance_after_settled`, which is now a misleading name for what it holds.

The ledger figures are the later reads, and the billing history above confirms
them from a different instrument to nine decimal places. The JSON files are left
as they were written and annotated in `runs/runpod-render/README.md` rather than
edited, because a measurement artifact that gets quietly corrected after the fact
is worth less than one that carries its own error.

### The container runs a real 3.11.15, the workaround is gone, and it is now pixel-identical to home

Cycle 3 shipped `ENV PYTORCH_JIT=0` because the container segfaulted on boot every
time, inside `torch.jit.script` while importing kornia. The cause was the
interpreter: Ubuntu 22.04's `python3.11` package is **3.11.0rc1**, a release
candidate from 2022, against home's **3.11.15**.

**deadsnakes carries the exact release home runs**, which was the one open risk in
paying this debt:

```
Package: python3.11
Version: 3.11.15-1+jammy1
```

It is pinned to that string rather than floated. deadsnakes ships only the latest
patch in a series, so an unpinned install silently drifts off home the day 3.11.16
lands — and a pin that names a series rather than a release is what caused this
defect in the first place. The build now also *asserts* the interpreter, so a drift
fails the build instead of being discovered on a paid worker:

```
#6 0.205 interpreter: Python 3.11.15
```

That assertion was validated in isolation first — a 37-line throwaway Dockerfile
containing only the apt block, built in **1 minute**, rather than discovering a
broken PPA pin 30 minutes into a full build.

| | Cycle 3 image | Cycle 4 image |
|---|---|---|
| Tag | `sdxl-base-1.0` | **`sdxl-base-1.0-py31115`** |
| Python | 3.11.0rc1 | **3.11.15 final** |
| `PYTORCH_JIT` | `0` (workaround) | **unset** |
| `torch.jit` enabled | False | **True**, matching home |
| Size (`docker image inspect`) | 17.66 GB | **17.72 GB** |
| Local build | 31 m 29 s | **12 m 35 s** (warm layer cache for the model staging) |

A new tag rather than an overwrite: the apt layer invalidates everything below it,
so all ~13 GB re-pushes either way, and keeping `sdxl-base-1.0` intact preserves the
Cycle 3 artifact the comparison rests on.

**It boots.** No segfault, TorchScript on, all four IP-Adapter nodes registered,
`torch 2.11.0+cu128` and `kornia 0.8.3` identical to home.

**And it renders what home renders.** Run on home's own RTX 5070 — same silicon, so
there is nowhere for a hardware difference to hide:

| Plate | Figures | IP-Adapter | Differing pixels |
|---|---|---|---:|
| 0001 | 1 | none | **0** of 1,011,712 |
| 0003 | 1 | ichabod, 0.5 / 0.3 | **0** |
| 0008 | 2 | brom-bones, 0.35 / 0.4 | **0** |
| 0013 | 3 | ichabod, 0.35 / 0.4 | **0** |
| 0018 | 1 | none | **0** |

**The container is exonerated completely.** Whatever divergence remains on a Runpod
card is silicon, because on identical silicon this image is bit-identical to home on
both the LoRA-only and the IP-Adapter paths.

Free. One local build and thirteen local renders; no Runpod resource was touched.

### A model that has just been loaded does not render what a resident model renders

This was found while running the check above, and it is not about the container.

The first render after a cold model load differs from every render after it — on the
same card, the same seed, the same graph. Plate 0001, which has no IP-Adapter and is
therefore the simplest path in the book:

| Where | Model state | Differing pixels | Max abs |
|---|---|---:|---:|
| Home ComfyUI | cold (VRAM freed first) | **842,339** (83.3%) | 221 |
| Home ComfyUI | warm | **0** | 0 |
| Cycle 4 container, home 5070 | cold (VRAM freed first) | **842,339** (83.3%) | 221 |
| Cycle 4 container, home 5070 | warm | **0** | 0 |

Both sides give **the same number to the pixel**, in both states, and each state is
reproducible — the cold figure was measured twice on each side and did not move. So
this is deterministic behaviour of the render stack, not noise, and not the
container's: matching home's *cold* result as exactly as its warm one is stronger
evidence of faithfulness than matching only the warm one would have been.

The mechanism is ComfyUI's dynamic VRAM staging (`Model SDXL prepared for dynamic
VRAM loading. 4896MB Staged. 788 patches attached. Force pre-loaded 512 weights`),
which is present and identical on both sides. What is not yet established is *which*
part of that staging moves the numerics.

**Why the baseline is unaffected.** Portraits render before page plates, so the
cold-load render in the `pg-41` bake was a portrait; every page plate drew against a
resident model. That is why home's stored `0001` matches a warm render, and why all
nine plates passed the task 0 sweep.

**Why it matters for this cycle.** On Runpod each worker's *first* render is a
cold-load render. Fanning 16 plates across 4 workers without pre-warming would make
4 of them cold-load renders that differ from home for a reason that has nothing to do
with the GPU. The headline bake pre-warms every worker before it starts, and that is
now a fidelity requirement rather than only a wall-clock one.

**The honest general statement** is stronger than the one Cycle 3 reached. A plate
re-renders identically only when the card **and** the model-residency state match.
Cycle 3 recorded the first half of that; this is the second.

### A measurement trap: ComfyUI's execution cache looks exactly like a hang

Submitting a byte-identical graph twice in a row returns the cached result:

```
[INFO] got prompt
[INFO] Prompt executed in 0.00 seconds
```

The history entry carries no new `outputs`, so a client polling for outputs waits
until its own timeout and reports a hang. Nothing is wrong and nothing is running.

It cost twenty minutes here, chasing a GPU that looked stuck while `queue_running`
and `queue_pending` were both zero. It never touched a recorded number — every
figure above came from an execution that reported a real duration, never `0.00` —
but a benchmark that re-submits one plate repeatedly would measure the cache rather
than the renderer. Vary the graph, or clear the cache, between repeats.

### Five issues filed, on three repositories

Kris approved drafts 1–5. All five are now filed; draft 6 is held back by
decision and stays a recorded finding.

| Issue | Subject | Repository |
|---|---|---|
| **[runpod/flash#364](https://github.com/runpod/flash/issues/364)** | `Endpoint(workers=(0, N))` deploys `workersStandby: 1` | `runpod/flash` |
| **[runpod/flash#365](https://github.com/runpod/flash/issues/365)** | `flash deploy` reports success for a client-mode app but provisions no endpoint | `runpod/flash` |
| **[runpod/flash#366](https://github.com/runpod/flash/issues/366)** | A list of `GpuType`s does not constrain placement; a single `GpuType` does | `runpod/flash` |
| **[runpod/docs#800](https://github.com/runpod/docs/issues/800)** | `PodTemplate.containerRegistryAuthId` is required for private images and is documented nowhere | `runpod/docs` |
| **[runpod/runpodctl#327](https://github.com/runpod/runpodctl/issues/327)** | `runpodctl registry create` accepts a registry password only as a command-line flag | `runpod/runpodctl` |

Each was filed with `gh issue create --repo <org/repo> --title <t> --body-file <f>`.
The command is recorded because Cycle 3 filed `runpod/flash#363` and did not
write down how, which left a hole in an otherwise reproducible record.

Fifteen duplicate searches were run across the three repositories before filing
— three per draft, terms recorded beside each draft in AI-ASSIST.md — and none
returned a hit.

Draft 4 went to `runpod/docs` rather than `runpod/flash` deliberately: the field
works correctly, so the defect is entirely documentary. Draft 5 went to
`runpod/runpodctl`, which is a third repository this project had not filed
against before.

**What changed between draft and filing.** Draft 1 went out unchanged — it was
written after its measurement and was already complete. The other four gained an
exact versions block, and three gained evidence that did not exist when they were
drafted: draft 2 the live build manifest, draft 3 both endpoint ids and the 2.8×
render-time gap that makes the substitution cost something, draft 4 the
confirmation that two endpoints have since pulled a private image using the
undocumented field. Draft 5 gained `docker login`'s own warning text as the
precedent it is asking Runpod to match.

Three older annotations were corrected in the same pass. AI-ASSIST.md's billing
section still said "nothing has been filed" when Gap 1 had gone out as
`runpod/docs#798` in Cycle 3; Gap 3 still read as live after being killed; and
Gap 2 still asked whether image-pull time is billed, which Cycle 3 answered
(775 s of pull across two passes, none of it billed). All three are annotated in
place rather than rewritten.

### The multi-figure plates were never a silicon result, and Cycle 3's claim is corrected here

The nine-plate sweep above only reads that way after a defect was found in our
own comparison harness. The first run of it failed plate 0013 at **1,009,358 of
1,011,712 differing pixels, max absolute channel difference 179** — on the same
GPU, the same interpreter and the same seed that drew the stored image.

**The cause is two numbers this port could not receive.** Scriptorium gives a
plate whose frame holds more than one person a weaker, later identity anchor:
`reference_conditioning` (`p7_render.py:333-340`) returns IP-Adapter weight
**0.35** and start **0.4** when `derived.depicted` has more than one entry,
against the service default of 0.5 / 0.3. It has always sent them as
`referenceStrength` / `referenceStart`. `flash-imagegen/graph.py` hardcoded
0.5 / 0.3 and `handler.py` had no input for them, so every multi-figure plate
rendered here was a different computation from the one home ran.

Four of the nine `pg-41` plates are multi-figure: **0008** (2 figures), **0011**
(2), **0013** (3), **0020** (2).

**Measured on home hardware, where silicon cannot be the explanation:**

| Plate | Conditioning sent | Differing pixels | Max abs |
|---|---|---:|---:|
| 0013 | 0.5 / 0.3 — the old port | 1,009,358 (99.77%) | 179 |
| 0013 | 0.35 / 0.4 — what home sent | **0** | **0** |
| 0008 | 0.5 / 0.3 — the old port | 1,009,980 (99.83%) | 163 |
| 0008 | 0.35 / 0.4 — what home sent | **0** | **0** |

Same card, same interpreter, same seed, same prompt; only those two floats move,
and they move 99.8% of the pixels.

**What this corrects.** Cycle 3 recorded, under *"The plates are not
pixel-identical, and the GPU is why"*, that **"different silicon is the cause"**
of the divergence it measured. That conclusion is right for the plates it can be
right for, and it is not right for all seven it was applied to:

- It **stands** for the single-figure plates. 0001 uses no IP-Adapter at all and
  still differed by 79.6% / 63.1%; 0003, 0006 and 0015 differed by 51–65%. Those
  plates sent identical conditioning on both sides, so silicon is the only
  variable left, and the reasoning that two Runpod cards also differ from *each
  other* is untouched.
- It **does not stand** for 0008, 0011 and 0013 — the three highest divergences
  in the Cycle 3 table at 97.7–98.2%, and the three multi-figure plates in the
  sample. Those numbers conflate two causes, and the second one is ours. The
  conditioning gap alone produces 99.8% on hardware that never changed.

The pattern was visible in the published table and was not read: the three worst
plates clustered near 98% while the rest sat between 51% and 80%, and the split
falls exactly on `len(depicted) > 1`. A divergence that bimodal was evidence of a
second mechanism, not of a noisier one.

**How much of the 98% is silicon is not yet known**, and it is not guessable from
here — that measurement is task 1's comparison set, which renders 0008 and 0013
on the pinned 4090 both with the conditioning and without it. Until then the
honest statement is that the Cycle 3 figures for those three plates measure the
sum of a hardware difference and a harness defect, in unknown proportion.

**What it does not change.** The timing comparison is unaffected: the graph
shape, weights, sampler, scheduler and 25 steps are identical either way, and an
IP-Adapter weight does not change how long a render takes. `4.406 s` against
`7.595 s` stands.

**Fixed in the port.** `graph.build()` takes `reference_strength` and
`reference_start`; `None` keeps 0.5 / 0.3, so a caller that omits them builds a
byte-identical graph to the pre-Cycle-4 port and one image can measure both
behaviours. `verify_port.py` recomputes what home sent from the plate's own
`derived.depicted` and grew `--reference-strength` / `--reference-start` to force
the other arm, which is how the cause above was proved rather than argued.

**The wider point.** The harness that checks fidelity had a fidelity bug, and it
passed for three cycles because it was only ever pointed at single-figure plates
— Cycle 2's verification used 0001 and 0003. A check that is only run where it
passes is not a check. The nine-plate sweep is now the default.

### The headline bake: 325.24 s against home's 388.63 s

One complete `pg-41` bake, text steps at home, every render on a Runpod endpoint
pinned to a single `NVIDIA_GEFORCE_RTX_4090`, plates fanned out four at a time.
Source: `runs/pg-41-runpod/{run.json,timing.json,prewarm.json,health-samples.json}`.

| Bucket | Home | Runpod | Change |
|---|---:|---:|---:|
| Text steps | 162.20 s | 161.36 s | −0.84 s |
| Image rendering | 123.34 s | 59.74 s | **−63.60 s** |
| Model loading | 31.19 s | 23.22 s | −7.97 s |
| Orchestration | 71.89 s | 80.92 s | +9.03 s |
| **Wall clock** | **388.63 s** | **325.24 s** | **−63.39 s** |

**1.195× end to end**, and the Runpod run produced **18 images against home's
16** — the text steps selected 11 plates where the baseline selected 9, so the
faster run also did more work. Two extra illustration prompts is also why text
came in flat rather than lower.

**The parallelism did far less than the card did, and that is the finding.**
The workers reported **92.13 s** of render work, which occupied **73.76 s** of
wall clock. That ratio — `renderer_reported.overlap_factor` — is **1.249**,
against a configured concurrency of 4. Decomposing the render bucket:

- home rendered 16 images in 123.34 s, i.e. **7.709 s** each
- at that rate 18 images would have taken **138.8 s**
- the 4090 did those 18 in 92.13 s of work: the card saved **46.7 s**
- overlapping that work saved a further **18.4 s**

So of the ~65 s the render bucket lost, **72 % is the faster silicon and 28 % is
the fan-out we built this cycle for.** Warm render median fell from **7.595 s**
to **4.7725 s** (n=18), a 1.59× per-image speedup that lines up with Cycle 3's
pinned-4090 single-plate number once the conditioning correction is applied.

**Amdahl's floor.** With rendering at exactly zero this bake would still take
**251.5 s** (325.24 − 59.74 − 14.02). Text steps and orchestration are now
**74 %** of the run. Cycle 2 predicted this when text overtook rendering; the
headline number confirms it. Nothing further is available from the GPU.

### Why the fan-out only ran 1.25 wide

Not a bug in the fan-out — it submitted correctly, and `/health` shows up to
three jobs in flight with a queue behind them. The endpoint never had four
workers to give.

**The pre-warm warmed exactly one worker, while appearing to warm four.** All
four requests returned `COMPLETED` on a 4090, which is what the script checked.
But only **one of the four reported a model load** (`model_load_s` 3.005 s,
render 4.821 s); the other three reported `model_load_s: 0` and rendered in
~1.51 s, which is a model already resident. Their 476–492 s of `delayTime` was
not four image pulls — it was one pull and three waits in the queue behind it.

`/health` confirms it independently: at the moment the pre-warm finished,
`{"idle": 0, "initializing": 1, "ready": 0, "running": 1, "throttled": 2}`. Two
workers were **throttled** — Runpod had no free 4090 for them. The throttle
cleared five seconds later and two more workers began initializing, but a
17.66 GB pull takes ~8 minutes and the render phases began ~3 minutes later. One
of those two joined mid-bake. The fourth was still `initializing` when the
endpoint was torn down, having pulled for five minutes and rendered nothing.

**This has a fidelity consequence, and it is the one the Python rebuild
predicted.** Cycle 4 established that a worker's first render after a cold model
load produces different pixels from every render after it — reproducibly, on
home's own card as well as in the container. Two of the eighteen renders in this
bake carried a cold load: `portrait-hans-van-ripper` (3.508 s) and plate `0011`
(10.511 s). Those two images are cold-load images. Pre-warming was supposed to
prevent exactly this, and it prevented it for one worker out of the three that
ended up serving.

**The trade the pin makes.** Cycle 3 asked for two card types and got a third
substituted. Cycle 4 asked for one exact card and got it — every one of the 18
renders reports `NVIDIA GeForce RTX 4090`, verified per-plate from provenance —
but waited for it, and never got the full four. **A single-GpuType pin buys
reproducibility and pays for it in availability.** Both halves are real and both
belong in the talk.

### The live-demo configuration: 5.06 s

One request against an already-warm worker, immediately after the bake, at the
plate resolution of 832×832: **5.06 s** end to end, of which **3.897 s** was the
render and `delayTime` was **0.0 s**. That is the number a stage demo produces,
and it is the honest one to quote for a live demo — provided the worker is warm.

The standby worker Flash forces on us (`workersStandby`, not settable to 0 by
CLI, SDK or REST — `runpod/flash#364`) bills **$0.00** while warm, measured
across 11 m 13 s and 2 h 59 m 37 s in Cycle 3. On stage that defect is an
advantage: it is free cold-start insurance, and it is the one context where the
right answer is to leave it alone.

The alternative is what this cycle measured: a cold worker is **~490 s** before
it renders anything. Only one of the four pre-warm requests actually pulled, and
it reported **476.6 s** of `delayTime` against Cycle 3's 431.73 s wall (414.9 s
pull) for the previous image.

**That difference is not attributed.** The new image is 42 GB uncompressed
against 41.7 GB — 0.7 % larger, which does not account for ~10 %. Pull time
depends on the datacenter the worker lands in and on Runpod-side network, and
this is one sample of each. Recorded as a range, not a regression: a cold start
is **seven to eight minutes**, and pull time is not billed but is wall clock a
demo cannot hide.

### Claude Code usage for this cycle — usage, not a charge

The rule at the top of this file has existed since Cycle 1 and has never been
exercised. It is exercised here. **These are not charges.** This work runs
against a Claude Max subscription; no per-token money changed hands, and the
figures below are usage against that subscription.

They are **measured, not estimated** — the session transcripts record a `usage`
object per request, aggregated from
`~/.claude/projects/-home-kb-Desktop-projects-scriptorium-flash/*.jsonl`.

| | Cycle 4 (session `72136585`) | All four sessions |
|---|---:|---:|
| Requests | 665 | 2,120 |
| Output tokens | 640,788 | 2,328,069 |
| Input tokens (uncached) | 1,330 | 9,660 |
| Cache writes | 2,107,554 | 4,967,579 |
| Cache reads | 192,052,515 | 589,874,218 |

Cycle 4 spans 11:40–18:33 UTC on 2026-08-18. The shape worth noting is that
uncached input is **1,330 tokens against 192 million cache reads** — essentially
all context is served from cache across a long session.

**No dollar equivalent is given.** Converting these to an API-list-price figure
would mean quoting a rate card this environment cannot verify, and an unverified
price in this file would be exactly the kind of retyped number the rules at the
top forbid. The token counts are the measurement; a costed version can be
produced if a verified rate card is supplied.

### What the first parallel bake broke in the timing tool, and how it was caught

`bake_timing.py` was written for a serial pipeline, where the sum of render
durations and the wall clock they occupy are the same number. Under a fan-out
they are not, and the tool reported the difference as nonsense rather than
failing: `orchestration_detail.unexplained_s` came out at **−70.27 s** and
`--markdown` died with `KeyError: 'full_cold_after_free'`.

Three defects, all fixed, none of which moved a home-side number:

1. **The image bucket double-counted overlap.** It summed render durations, so
   two renders in the same second counted twice against a wall clock that only
   runs once. It now reports the **union** of the render intervals —
   `elapsed_union_s` — alongside the work sum and the ratio. For a serial bake
   the intervals are disjoint and the union equals the sum exactly, which is why
   this changed nothing published.
2. **Remote renders counted as idle time.** The "was the orchestrator busy here"
   test only knew about locally journalled renders, so every Runpod render
   looked like a gap between phases. `idle_between_phases_s` fell from 132.82 s
   to 35.07 s once renderer-reported intervals were included, and the residual
   went positive.
3. **The same upper-middle median bug as Cycle 3, in a second place.**
   `sorted(...)[n // 2]` returned 5.023 s where the true median of the 18 renders
   is **4.7725 s**. It was fixed in `render_bench.py` last cycle and this copy was
   missed. The corrected figure is the one quoted above.

**The regression check could not be run the obvious way, and that is worth
recording.** Re-running the tool on `pg-41` no longer reproduces the baseline:
the headline bake deleted and re-baked that book, so the live work directory now
holds the Runpod run. The baseline reproduces byte-identically — 388.63 s, every
bucket, `7.595 s` median, 16/16 matched, zero warnings — only when the tool is
pointed at `~/scriptorium-baseline-pg41-20260818` via `--data-root`. Without that
backup, taken before the re-bake, the check would have been impossible and the
comparison would have rested on a number that could no longer be regenerated.

---

## 2026-08-17 — Cycle 3

### Account baseline, re-read at the start of the cycle

`runpodctl user`, free read-only query. Every Cycle 3 cost is measured against
this line.

| Field | Value |
|---|---|
| `clientBalance` | **$49.9945861833** |
| `currentSpendPerHr` | $0 |
| `spendLimit` | $80 |
| Serverless endpoints (`runpodctl serverless list`) | `[]` |
| Container-registry credentials (`runpodctl registry list`) | `null` |
| Flash apps (`flash app list`) | none |

**Unchanged to the last decimal place from Cycle 2's closing reading.** Both CLIs
now authenticate against one `~/.runpod/config.toml`, which after `flash login`
carries a top-level `apikey` **and** a `[default].api_key`, both 50 characters.
Neither value has been read by this project.

### The credential defect is filed

**[runpod/flash#363](https://github.com/runpod/flash/issues/363)** — `flash`
cannot read a `~/.runpod/config.toml` written by `runpodctl`; the error suggests
exporting the key instead.

Filed on `runpod/flash`, the public repository behind the `runpod-flash` package.
No duplicate existed. Three corrections to the Cycle 2 draft were made before
filing; they are in [AI-ASSIST.md](AI-ASSIST.md) under "Cycle 3: the credential
issue, filed". The one that matters most for the record: **Runpod's
documentation never claims the two CLIs interoperate.** That claim is in Runpod's
shipped agent skills, a different artifact in a different repository, and the
issue attributes it there.

Draft issues 2 (container disk billing at zero workers) and 3 (whether an
`idle`/`ready` worker bills) stay unfiled until their measurements land.

### Hello-world: the first thing this project ever deployed

One Flash app, `hello-flash`, unchanged from Cycle 2 — `GpuGroup.AMPERE_16`,
`workers=(0, 1)`, `idle_timeout=60`, no dependencies, a 0.2 MB artifact of two
files. It echoes its input. The point is the three numbers.

| | Value |
|---|---|
| Endpoint id | `qb4qjquyist574` (first deploy) |
| Deployed | 2026-08-17T19:41:35Z |
| Deleted | 2026-08-17T19:49:13Z |
| **Cold start — first request** | **31.387 s** |
| **Warm request median** | **0.354 s** (n=3: 0.437, 0.320, 0.354) |
| Worker | `d5571d1c3f08` |
| **Verified cost** | **$0.0066245833** |

Cold start is caller-observed wall clock on the first request: the whole
exchange, which is what a caller actually waits for. All four calls returned 200.

**Cost is verified against the account balance, and only against the balance,
because the billing history could not corroborate it.** See "The billing history
API did not show a charge that demonstrably happened" below.

| | |
|---|---|
| `clientBalance` before | $49.9945861833 |
| `clientBalance` after, settled | $49.9879616000 |
| **Difference** | **$0.0066245833** |

At the 16 GB tier's **$0.58/hr** — confirmed live on runpod.io/pricing during
this cycle — that difference is **41.12 billed-equivalent seconds**.

The estimate at the gate was $0.02–0.03 for roughly 90–150 s of worker life. The
actual was **$0.0066**, about a quarter of the low end. The reason is in the next
section, and it is the most useful thing this deployment produced.

### Two separate claims about idle, and the pair is the finding

These get stated apart because conflating them is how the wrong conclusion gets
drawn, and Cycle 2 drew it from documentation alone.

**Claim 1 — the platform claim: an endpoint at zero workers bills nothing.**
Still believed, still consistent with everything measured. Nothing here
contradicts it.

**Claim 2 — the tool behaviour: `flash` does not give you zero workers.**
`Endpoint(workers=(0, 1))` is documented as `(min, max)`, and this repo's entire
scale-to-zero cost argument rests on it. What it actually deploys, read from the
REST API:

```
workersMin: 0     workersMax: 1     workersStandby: 1
```

`workersStandby` is the API field behind what the console calls **active
workers**, which `docs.runpod.io/serverless/endpoints/endpoint-configurations`
describes as "Minimum number of workers that remain warm and ready at all times"
and says "incur charges continuously, including when idle."

**`runpodctl` does not report `workersStandby` at all.** Neither
`runpodctl serverless list` nor `runpodctl serverless get <id>` includes the
field, so nothing in the CLI would reveal it. It took a direct
`GET https://rest.runpod.io/v1/endpoints` call to see it.

**It reproduces.** A second, independent deploy of the same unchanged app
produced `workersStandby: 1` again (endpoint `ivmpm73jnh01jw`, created
2026-08-17T19:57:02Z).

**Observed behaviour matches.** Across four minutes of polling with zero jobs
ever queued, the worker never scaled to zero — it oscillated between `running`
and `idle`/`ready` well past the 60-second idle timeout.

So the honest statement is: **zero workers costs nothing, and `flash
workers=(0, 1)` does not give you zero workers.** Either half alone is
misleading.

### What the 41.12 billed seconds does *not* mean

The endpoint existed for **458 seconds** and billed the equivalent of **41.12
seconds — 9.0% of its lifetime**. Caller-observed request time across all four
calls was 32.498 s.

**So the standby worker did not bill continuously**, and the reading that
Cycle 2 took from the documentation — that a warm worker bills for every second
it is warm — is not what this account was charged. That is a measurement against
one short window, not a law, and what the remaining ~8.6 s covers is not yet
pinned down. A longer window with the phases separated is running now; its result
and the arithmetic go in the idle-billing section.

That question is now answered — see "What is billed: the pull is free, the idle
tail is not" below. The 41.12 s is execution plus a short worker-start tail, and
the standby time is not in it. **Draft issue 3 is killed**, and the reasoning is
under "Draft issue 3 is killed, and the misreading is the finding".

### Does an idle Flash app bill? No. Three hours, to ten decimal places.

Cycle 2 answered this from documentation and could not test it, because `flash`
could not authenticate. Measured now.

`hello-flash` was deployed at 2026-08-17T19:57:02Z with `workers=(0, 1)` and left
alone. It is not a hypothetical zero-worker endpoint: Flash gave it
`workersStandby: 1`, so a worker sat **warm** for the whole window.

| | |
|---|---|
| Window | 19:57:24Z → 22:57:01Z (**2 h 59 m 37 s**) |
| `clientBalance` at open | $49.9879616000 |
| `clientBalance` at close | $49.9041127700 |
| Difference | $0.0838488300 |
| — hosted text-model calls in the same window (task 3) | $0.0838488300 |
| **— attributable to the idle app** | **$0.0000000000** |

Every cent of the window's spend is accounted for by task 3's public-endpoint
calls, whose costs are independently confirmed by each response's own `cost`
field. The remainder is zero to ten decimal places.

**A tighter measurement isolates it completely.** Before task 3 began, the app
sat with nothing else running at all:

| | |
|---|---|
| Window | 19:57:43Z → 20:08:56Z (**11 m 13 s**), zero requests sent |
| Balance | $49.9879616000 → $49.9879616000 |
| **Difference** | **$0.0000000000** |

If a warm 16 GB worker were billed at $0.58/hr, eleven minutes would have accrued
**$0.108** — eight orders of magnitude above the balance's resolution. It did not
move.

**Verdict: an idle Flash app costs nothing, and it costs nothing even though
Flash holds a worker warm.** The Cycle 2 documentary answer was right, and the
practical worry that prompted it — a 64 GB container disk quietly accruing
$6.40/month — does not happen.

**Decision: the app stays deployed**, which is what Cycle 2 concluded on paper
and what the measurement now supports.

**One caveat that matters for the render endpoint, not this one.** "Idle" here
means *no traffic*. A worker warm inside its `idle_timeout` immediately after a
request **is** billed — measured separately at 87.9 s and 94.3 s on the two
render passes. Leaving an untouched app deployed is free; leaving `idle_timeout`
generous on an app that is being used is not.

### Draft issue 2 — confirmed, and filed as runpod/docs#798

Draft issue 2 said the serverless pricing page implies container disk bills
independently of workers, and that a reader of that page alone concludes a
deployed idle endpoint accrues ~$6.40/month for Flash's default 64 GB.

**The measurement confirms the draft.** Three hours of a deployed endpoint with a
64 GB container disk and a warm worker accrued **$0.00**. Had container disk been
the standalone monthly meter the pricing page implies, eleven minutes alone would
have shown $0.0016 — detectable at ten decimals. Nothing accrued.

**Filed: [runpod/docs#798](https://github.com/runpod/docs/issues/798)** — per the
cycle rule that a draft goes out only when its measurement confirms it. No
duplicate existed.

### Hosted text models: 26 real calls, 0 clean parses, and a fixable reason

The question was whether moving Scriptorium's text steps — 41.7% of a `pg-41`
bake and its largest bucket — to a Runpod **public endpoint** is a URL swap or a
bigger change.

**It is a bigger change. It is also achievable, and the blocker is specific
enough to name.**

Home does not ask a model politely for JSON. `text-transform-service/src/tts/llm.py`
passes each transform's full JSON Schema to Ollama's `format` field, which is
grammar-constrained decoding — the model *cannot* emit anything off-schema. The
question was whether any equivalent exists on a public endpoint. No Runpod page
documents one.

Test: the real `cast-mentions` transform v0.3.0, imported from the running
text-transform-service source rather than copied, against ten real `pg-41`
pages. A parse is clean only if the pipeline's own `_attempt_reason()` accepts
it — `json.loads` **and** `jsonschema.validate` against the transform's schema.

#### The catalogue moved under us mid-cycle

Cycle 2 enumerated seven priced text endpoints from the documentation. Live:

| Slug | Documented in | Result |
|---|---|---|
| `cogito-671b-v2-1-fp8-dynamic` | `docs.runpod.io/public-endpoints/models/cogito-671b` | **404** |
| `qwen3-32b` | the live reference page | **404** |
| `granite-4` | the live reference page | **404** |
| `moonshot-kimi` | — | 200 → `kimi-k2.6`, `kimi-k2.7-code`, `kimi-k3` |
| `qwen3-32b-awq` | *not on the reference page* | 200 → `Qwen/Qwen3-32B-AWQ` |

**Cogito was priced in Cycle 2 at $0.50/1M and was gone from the catalogue the
same day.** It was this cycle's chosen model on the strength of that price — 20×
cheaper than the alternatives — and it now returns `endpoint not found`.

That is a production risk, not a documentation nit. A per-token dependency whose
cheapest model can be withdrawn between one day and the next has no price floor
a cost model can rest on, and the withdrawal is silent: a 404 at request time is
the first notice. Anything built on a public endpoint needs a fallback model and
an alerting path for `404`, which is work that a "URL swap" framing hides.

**The reference page also conflates two different identifiers.** It lists
"model slugs" in one column, but `kimi-k2.6` is a *model id* passed in the
request body, and the *endpoint slug* that serves it is `moonshot-kimi`. Using
the documented value as a slug returns 404. Two of the three text slugs the page
does list are dead, and the one working Qwen endpoint is not on it.

#### Neither model returned anything the pipeline could parse

| | `kimi-k2.6` | `Qwen/Qwen3-32B-AWQ` |
|---|---|---|
| Calls | 10 | 2 |
| HTTP 200 | 10 | 2 |
| **Clean parses** | **0** | **0** |
| Latency median | **13.106 s** | 27.9 s and 59.3 s |
| Cost | $0.040734 | $0.039080 |

Home's `cast-mentions` median is **2.877 s**. The hosted models are **4.5× to
20× slower per call** on the identical prompt.

**They failed in two different ways, and neither is "the model is bad".**

`kimi-k2.6` is a reasoning model. Every one of the ten calls returned
`finish_reason: length` with **699 of its 700 output tokens spent on
`reasoning_content` and zero characters of `content`**. Home's `num_predict` of
700 is not a budget this model can work inside — it thinks past it every time,
and the account pays for all 7,000 wasted tokens.

`Qwen/Qwen3-32B-AWQ` emits its chain of thought **into `content`** as a `<think>`
block when nothing constrains it, so the response fails at character 1. Of two
calls, one produced JSON missing a required property and one produced 3,036
characters that were not JSON.

#### Structured output does exist, and it is undocumented

No Runpod page mentions it. All four mechanisms work on the vLLM-backed
endpoint, tested against a simple schema:

| Parameter | Result |
|---|---|
| none | 200 — but `content` begins `<think>` |
| `response_format: {type: json_object}` | **200** — `{"ok":true}` |
| `response_format: {type: json_schema}` | **200** — `{"ok":true}` |
| `response_format: {type: json_schema, strict: true}` | **200** — `{"ok":true}` |
| `guided_json` (vLLM native) | **200** — `{"ok":true}` |

So the constraint mechanism Scriptorium needs is available on
`qwen3-32b-awq` — it is simply written down nowhere.

#### But Scriptorium's actual schema does not compile

Bisected one feature at a time, same endpoint, same prompt:

| Schema | Result |
|---|---|
| array of strings | 200 |
| + nested objects | 200 |
| + `additionalProperties: false` | 200 |
| + `maxItems` | 200 |
| **+ `minLength` / `maxLength` on a string** | **HTTP 500 after 60.5 s** |
| the real `cast-mentions` schema | **HTTP 500** |

**String length bounds are the breaking feature.** The failure is an opaque
`{"status":500,"title":"Internal Server Error"}` after a minute of apparent
work — no diagnostic naming the schema, no hint that a constraint is
unsupported.

`cast-mentions`'s schema uses `minLength: 1` and `maxLength: 60` on `name`,
`maxLength: 60` on aliases and `maxLength: 140` on descriptors.

**So the migration is a specific, bounded piece of work**: send a wire schema
with the string bounds stripped, keep the full schema for local validation after
the response arrives. That is a change to text-transform-service, not a URL swap
— but it is a day's work, not a rewrite.

#### One more thing that returns 500: ordinary sampling parameters

On `moonshot-kimi`, **`temperature` and `top_p` each cause HTTP 500**,
independently. Isolated with minimal requests:

| Body | Result |
|---|---|
| `messages` + `max_tokens` | 200 |
| + system message | 200 |
| + `temperature: 0.2` | **500** |
| + `top_p: 0.8` | **500** |
| + both | **500** |
| `max_tokens: 700`, no sampling | 200 |

Two of the most basic OpenAI parameters, on an endpoint advertised as
OpenAI-compatible, with the same opaque error body. Home runs every transform at
a deliberate `temperature` — `cast-mentions` at 0.2 — so this endpoint cannot
reproduce home's sampling at all.

#### Does per-token usage draw down the credit? Yes.

Cycle 2 could not settle this and leaned on a $0.0054 shortfall as circumstantial
evidence. Settled now: **the balance moves.** It fell from $49.9879616000 to
$49.9078527700 across this task's calls. Runpod's credit pays for public-endpoint
tokens, and Cycle 2's reading of that shortfall was right.

#### Cost, and a correction to how it was measured

**The endpoint's own `cost` field is exact.** It equals `total_tokens ×` the
published rate, verified on both models — Kimi reported $0.040734 for 13,404 in
and 7,000 out at $0.95/$4.00 per 1M, which is the list arithmetic to the cent.

**An earlier reading in this cycle claimed the account was billed 3.26× under
list price. That was wrong, and the error was in the method.** The probe read
`clientBalance` sixty seconds after the last call and treated a stable reading as
a settled one. Runpod's balance lags charges by several minutes, so an early read
reports a fraction of the spend and then stops changing, which looks exactly like
a settled number. Corrected: there is no discount, and the tool now reports the
endpoint's `cost` field as authoritative with the balance quoted only as a
lagging cross-check.

**Extrapolated to one full `pg-41` bake** — 55 text calls (20 `cast-mentions`,
20 `scene-update`, 9 `illustration-prompt`, 6 `cast-canonicalize`):

| Model | Rate | Per full bake | Note |
|---|---|---:|---|
| `Qwen/Qwen3-32B-AWQ` | $10.00/1M blended | **$1.07** | the only one that can be constrained |
| `kimi-k2.6` | $0.95 in / $4.00 out | **$0.22** | for 55 responses containing nothing |
| Home `qwen3.5:9b` | — | **$0.00** | marginal; the GPU is already owned |

Both are over-estimates: they scale `cast-mentions`, which carries the largest
`num_predict` of the four transforms.

#### Verdict

**Moving the text steps is a bigger change than a URL swap.** Four things have to
be true that are not true today, and only the first is really about code:

1. The wire schema must drop `minLength`/`maxLength`, with full validation moved
   after the response. Bounded work.
2. `response_format` has to be sent on every call, because unconstrained output
   is `<think>` prose and parses at 0%.
3. The pipeline must tolerate a model catalogue that changes without notice, with
   a fallback and a 404 alarm.
4. Someone has to accept **$1.07 a book** against $0.00 at home, and **4.5–20×
   the latency** on the step that is already the largest bucket in the bake.

The image steps are the opposite case: a GPU Scriptorium does not own, doing work
it cannot parallelise locally. The text steps are cheap and fast at home and get
expensive and slow hosted. On this evidence **the text steps should stay local**,
and that is a more useful answer than the one this cycle set out to confirm.

### The billing history API did not show a charge that demonstrably happened

`runpodctl billing serverless` returns `[]` — over today's window with hourly
buckets, and over an all-time window with monthly buckets — while the account
balance dropped $0.0066245833 for serverless work in that same period.

That matters beyond bookkeeping. This project's rule is that every cent is
verified against billing records. For serverless spend at this scale, **the
billing-history API cannot do that job**, and the balance — read to ten decimal
places — is the only instrument that works. Every cost in this cycle is therefore
sourced to a balance delta, with the billing history quoted alongside as
corroboration where it has any to offer.

Whether the charge posts to the history later, or whether sub-cent serverless
usage never appears there, is not yet established.

### Three smaller things the deployment taught

**`ready` does not mean ready.** The platform health route reported
`workers: {idle: 1, ready: 1}` *before* the first request, and that request still
paid the full 31.387 s cold start. A caller cannot use `ready` to predict
latency.

**`NVIDIA_VISIBLE_DEVICES` is worthless for identifying the card.** It returned
the literal string `void`. This was going to be `flash-imagegen`'s only record of
which GPU ran a plate, on a tier that can hand out more than one model of card.
Fixed — the render handler now reads the device name from ComfyUI's
`/system_stats` instead. Recorded here because the defect was ours and the
evidence for it came from this deployment.

**The endpoint is a load balancer, and the job counters stay at zero.**
`jobs: {completed: 0, …}` never moved despite four successful requests, because
load-balanced routes are not queue jobs. Anyone reading `completed` as "requests
served" on a Flash LB endpoint will read zero forever.

### The render container: built, and it did not work

The image that carries the home render stack to a Runpod GPU.

| | |
|---|---|
| Size | **17.66 GB** (`docker image inspect`) |
| First build | **31 min 29 s** wall clock |
| Model staging | **127.3 s** for all five files, copied and hash-verified |
| ComfyUI boot, measured locally | **8.0 s** |

Layer breakdown: models 10.8 GB, torch + ComfyUI requirements 8.48 GB, CUDA base
1.05 GB, apt 173 MB, ComfyUI 144 MB, IP-Adapter nodes 6 MB.

**The five model files came off this machine rather than off HuggingFace**, and
that is safe because they are checked the same way either route. All five are
present locally at the exact recorded sizes and SHA256s, so `fetch_models.py
--from-dir` copied them in 127 s instead of pulling ~11 GB. A cached file that
fails its hash is deleted and re-downloaded rather than trusted; that behaviour
has its own test. Without `--build-context` the cache stage is empty and the
build downloads exactly as before.

**Do not trust `docker images` for the size.** It reports **41.7 GB** for this
image — the containerd store counts the manifest and the unpacked snapshot
separately. `docker image inspect` reports 17.66 GB, and the layer sum is
24.07 GB uncompressed. Three numbers for one image; the middle one is the image.

### Pushing 17.66 GB to a private registry took four hours

| | |
|---|---|
| Registry | `ghcr.io/kbennett2000/scriptorium-imagegen:sdxl-base-1.0`, **private** |
| Pushed | 2026-08-17T21:24:06Z → 2026-08-18T01:20:59Z |
| **Wall clock** | **3 h 56 m 53 s** |
| Digest | `sha256:7df38e537f6c8a8f1830ef917b8e316985507dac84deaf882e86febc16185cda` |
| Visibility, checked after | **`private`** |

The digest is the fixed image, not the first one — the segfaulting build was
`sha256:b057b3530d98…` and never became the tag.

**Two things made this slow, and only one of them was the network.** Home upload
measured **20.5 Mbit/s**, which puts a ~13 GB compressed push at 85–105 minutes
on its own. It took nearly four hours because a stale push of the earlier image
ran concurrently for three of them, uploading the same blobs and halving the
available bandwidth.

That was avoidable and it was our error: `pkill -f "docker push"` reported
success, and the process survived. Snap's confinement denies signals to the
docker client even from the user that owns it —

```
$ kill -9 622468
kill: (622468) - Permission denied     # process owner is kb; so is the shell
```

— and the client is not doing the upload anyway. `/proc/<pid>/io` for the client
shows **0.03 GB read and 0 written** across the whole push: `dockerd` streams the
layers, so killing the client would not have stopped the transfer regardless. The
lesson is the general one — a kill that prints nothing is not a kill that worked.

**Registry credentials, and what Runpod was given.** Runpod pulls a private image
using a stored credential, created in the console rather than with
`runpodctl registry create`, whose only interface puts a registry password in the
process table and the shell history. The token Runpod holds is scoped
**`read:packages` only**, so a compromise of Runpod's copy cannot publish
anything. This project read back only the credential id, which is not a secret.

### Home versus Runpod, measured

Both tiers ran the identical protocol: one cold request, then six warm renders on
the same `pg-41` plates with the same seeds and prompts the home bakery used,
then a deliberate 90-second idle window. Seven of the nine plates carry an
IP-Adapter reference portrait, and the references were sent, so the work is the
same work.

| | Home RTX 5070 | Runpod 24 GB tier | Runpod 24 GB PRO |
|---|---:|---:|---:|
| Card actually used | RTX 5070 (12 GB) | **RTX PRO 6000 Blackwell MIG 1g.24gb** | **RTX 4090** |
| Card requested | — | A5000 *or* 3090 | RTX 4090 |
| Rate | — | $0.69/hr | $1.10/hr |
| **Warm render median** | **7.595 s** (n=8) | **12.381 s** (n=6) | **4.406 s** (n=6) |
| Warm range | — | 9.457–15.916 s | 4.025–7.363 s |
| vs home | — | **63% slower** | **42% faster** |
| Cold start, wall | n/a | 387.27 s | 431.73 s |
| — of which image pull + worker start | — | 360.2 s | 414.9 s |
| — of which ComfyUI boot | — | 1.5 s | 6.5 s |
| **Cost per warm plate** | $0 marginal | **$0.002656** | **$0.001742** |
| Cost, whole 7-render pass | — | **$0.0376933074** | **$0.0439145185** |

> **Corrected 2026-08-18.** The two Runpod figures are the *upper* of the two
> middle values of a six-sample set, not the median. `render_bench.py` computed
> `sorted(...)[n // 2]`, which is the median only for odd n. The true medians are
> **4.2175 s** (4090) and **11.937 s** (24 GB tier) — so against home's 7.595 s the
> 4090 was **44.5% faster** rather than 42.0%, and the 24 GB tier **57.2% slower**
> rather than 63.0%. The two rows below inherit the same error.
>
> Home's 7.595 s is unaffected: it comes from `bake_timing.py`, which uses
> `statistics.median`, on n=8. The Runpod figures are left in place because they
> are what the Cycle 3 artifacts contain and what its commit message quotes. The
> tool now emits `statistics.median` as `warm_render_median_s` and keeps the index
> form beside it as `warm_render_upper_middle_s`, so both stay reproducible.
>
> No conclusion moves: the 4090 was faster than home and the cheaper tier slower,
> by a slightly larger and a slightly smaller margin respectively.

Home's second reference bake, `pg-1952`, gives 7.615 s (n=6), so the home
constant is stable across books at ~7.6 s.

**The 4090 is 42% faster than home and cheaper per plate than the slower tier.**
$1.10/hr buys renders at $0.001742 each; $0.69/hr buys them at $0.002656,
because the cheaper card takes 2.8× as long. On per-plate cost the expensive
tier wins, and it is not close.

**A whole `pg-41` bake is 16 renders.** At the 4090's measured per-plate cost
that is **$0.028** of GPU time, against 123.34 s of the home bake. The cold start
is the thing that dominates a single-book run, not the rendering.

### Runpod did not give us the GPU we asked for

**The 24 GB pass requested two specific cards and got a third.** `app.py` named
`NVIDIA RTX A5000` and `NVIDIA GeForce RTX 3090`, and the created endpoint read
back exactly those two:

```json
"gpuTypeIds": ["NVIDIA RTX A5000", "NVIDIA GeForce RTX 3090"]
```

Every one of the seven renders reported:

```
cuda:0 NVIDIA RTX PRO 6000 Blackwell Server Edition MIG 1g.24gb : cudaMallocAsync
```

A MIG partition of a Blackwell — neither requested card. It is inside Runpod's
24 GB tier (the pricing page lists "L4, A5000, 3090, MIG 24GB" together at
$0.69/hr) so the billing is right, but the hardware constraint was not honoured
and nothing reported the substitution. Only the handler reading ComfyUI's
`/system_stats` revealed it, which is the entire reason that defect was fixed
before this pass.

**Pinning one exact card was honoured.** The second pass set
`gpu=GpuType.NVIDIA_GEFORCE_RTX_4090` — a single `GpuType` rather than a list —
and every render ran on `cuda:0 NVIDIA GeForce RTX 4090`.

So the rule, from two measurements: **a list of `GpuType`s is advisory, a single
pinned `GpuType` is respected.** For a measurement that means to compare
hardware, only the pinned form is usable. For a production workload it means a
multi-card list buys supply resilience at the price of not knowing what you are
running on — which is fine for throughput and not fine for a latency SLO.

This also retires the Cycle 2 plan's reasoning. Excluding the L4 from the pool
bought nothing: the pool substituted a card that was not on the list at all.

### The plates are not pixel-identical, and the GPU is why

> **PARTLY SUPERSEDED 2026-08-18 by Cycle 4, task 0.** Kept verbatim as the
> record of what was concluded and on what evidence. The conclusion below holds
> for the single-figure plates (0001, 0003, 0006, 0015). It does **not** hold for
> 0008, 0011 and 0013: those three are multi-figure, and this comparison sent
> them IP-Adapter conditioning of 0.5 / 0.3 where home sent 0.35 / 0.4, because
> the port had no input for the parameter. That difference alone moves 99.8% of
> the pixels on home's own card. Their 97.7–98.2% figures therefore measure a
> hardware difference plus a harness defect, in a proportion not yet split. See
> *"The multi-figure plates were never a silicon result"* under Cycle 4.

Cycle 2 proved `flash-imagegen` reproduces the home render graph **pixel for
pixel** — 0 of 1,011,712 pixels different, on both the LoRA-only and the
LoRA+IP-Adapter paths. That proof was run on home's GPU — and, it turns out, only
on single-figure plates, which is why it missed the conditioning gap.

On Runpod's GPUs it does not hold:

| Plate | IP-Adapter | 24 GB tier | 4090 |
|---|---|---:|---:|
| 0001 | none | 79.6% differ | 63.1% differ |
| 0003 | ichabod | 64.8% | 62.6% |
| 0006 | ichabod | 56.3% | 58.1% |
| 0008 | brom-bones | 98.2% | 98.2% |
| 0011 | ichabod | 97.7% | 97.8% |
| 0013 | ichabod | 97.7% | 97.8% |
| 0015 | ichabod | 51.0% | 54.6% |

Maximum absolute channel difference reached 214 of 255, so these are not
last-bit differences; they are visibly different images of the same scene.

**`PYTORCH_JIT=0` is not the cause.** That was the stated risk of the container
workaround, and the measurement clears it: plate **0001 uses no IP-Adapter at
all** — the path where kornia and TorchScript play no part — and it differs by
79.6%. Whatever is moving the pixels moves them without IP-Adapter in the
picture.

**Different silicon is the cause.** SDXL at a fixed seed is deterministic *on the
same hardware and kernels*. Across architectures — a 12 GB Ada-class 5070, a
Blackwell MIG slice, and a 4090 — cuDNN algorithm selection, TF32 behaviour and
reduction order all differ, and 25 sampling steps compound any divergence from
the first one. The two Runpod cards also differ from **each other**, which is the
tell: if the container were at fault both would differ from home identically.

> **Corrected 2026-08-18.** "The cause" is too strong: it is *a* cause, and the
> only one for the single-figure plates. It was applied to all seven, and for
> 0008, 0011 and 0013 a second cause — this port sending the wrong IP-Adapter
> conditioning — was also present. The evidence quoted here for silicon is
> sound; the error was in the scope of the word "the", and in not reading a
> divergence that split cleanly into two clusters as a sign of two mechanisms.

**What this costs the project, stated plainly.** The comparison is still a fair
one *for timing* — both sides run the same graph, the same weights, the same
sampler, the same steps, and produce a plate of the same scene. It is no longer a
claim of bit-identical output. Anything that depends on a plate re-rendering
identically — re-running a bake and expecting the same book — holds only while
the hardware is held constant. That is a real constraint on moving rendering to a
pool of mixed GPUs, and it was not visible before this measurement.

### What is billed: the pull is free, the idle tail is not

Both passes reconcile the same way, and the arithmetic is unusually clean.

| | 24 GB tier | 4090 |
|---|---:|---:|
| Rate | $0.69/hr | $1.10/hr |
| Cost | $0.0376933074 | $0.0439145185 |
| **Billed seconds** | **196.7 s** | **143.7 s** |
| Endpoint lifetime | 918 s | 967 s |
| Image pull + worker start | 360.2 s | 414.9 s |
| Sum of execution time | 108.7 s | 49.5 s |
| **Billed − execution** | **87.9 s** | **94.3 s** |
| Deliberate idle window | 90 s | 90 s |

**Image pull is not billed.** Between them the two passes spent 775 seconds
pulling a 17.66 GB image, and none of it appears in billed time — billed seconds
are far below endpoint lifetime in both cases, and the gap is fully explained
without it. This answers the question AI-ASSIST.md's Gap 2 raised: the docs
exempt model download and are silent on image pull; measurement says image pull
is exempt too. **That is a large practical result for a container this size** —
a six-to-seven minute pull that costs nothing changes the economics of baking
weights into an image rather than mounting a network volume.

**The idle tail after a request is billed.** Billed-minus-execution came to
87.9 s and 94.3 s against a 90-second idle window in both runs — an agreement too
close to be coincidence across two different tiers and rates.

**And a standby worker with no traffic at all is not billed.** Three hours of
`hello-flash` sitting at `workersStandby: 1` cost exactly $0.0000000000.

So there are **two different warm states and they bill differently**:

| State | Billed? | Evidence |
|---|---|---|
| Worker warm after a request, inside `idle_timeout` | **Yes** | 87.9 s and 94.3 s against 90 s windows |
| Worker warm with no traffic (standby) | **No** | 3 h at $0.00, twice-confirmed |
| Image pull / worker start | **No** | 775 s unaccounted across two passes |

The health API muddies this: during the billed idle window it reported the worker
as `running`, not `idle`, for the first ~81 seconds of 90, flipping to
`idle`/`ready` only at the end. So the state that bills is not labelled `idle` in
the API while it is billing.

### Draft issue 3 is killed, and the misreading is the finding

Draft issue 3 said `runpod/golden-paths/15-monitor-and-debug.md:73` was **wrong**
to list `idle`/`ready` as not billed, and that `13-autoscaling-tuning.md:229`
("warm & billed during idle timeout") was right. It was going to be filed as a
correction to `15`.

**It is not filed, because the measurement shows both pages are partly right and
the real answer is a distinction neither of them draws.** The idle-timeout tail
after a request bills, which is `13`'s claim. A warm worker with no traffic does
not bill, which is `15`'s claim. They are describing two different states with
one label.

Cycle 2 reached its conclusion from documentation alone and picked a side. The
brief's rule — do not file when the measurement contradicts the draft, and record
the misreading as its own finding — applies exactly, and this is that record.

What could honestly be filed instead is a different issue: that both pages use
`idle`/`ready` for two states that bill differently, and that the health API
reports the billing one as `running`. That is new text, not the approved draft,
so it goes to Kris rather than to a repository.

### The container segfaulted on boot, and a free local test caught it

**The first build could not run at all.** Started locally on the home GPU, it
died before serving anything:

```
Fatal Python error: Segmentation fault
Stack (most recent call first):
  File ".../torch/jit/_script.py", line 1262 in _script_impl
  File ".../kornia/__init__.py", line 28 in <module>
  File "/opt/ComfyUI/nodes.py", line 2510 in init_builtin_extra_nodes
```

**The cause is the interpreter, and it is our defect.** Ubuntu 22.04's
`python3.11` package is **3.11.0rc1** — a release candidate from 2022. Home runs
**3.11.15**. Every other version is identical across the two:

| | Home | Container |
|---|---|---|
| Python | **3.11.15** | **3.11.0rc1** |
| kornia | 0.8.3 | 0.8.3 |
| torch | 2.11.0+cu128 | 2.11.0+cu128 |
| torchvision | 0.26.0+cu128 | 0.26.0+cu128 |
| scipy | 1.17.1 | 1.17.1 |
| safetensors | 0.8.0 | 0.8.0 |

Same packages, different interpreter, and only the container crashes — inside
`torch.jit.script`, which does deep bytecode introspection and is exactly the
kind of code an interpreter release candidate breaks.

The Dockerfile's own header says everything is pinned to what home runs. The
Python was not, and nothing in the build would have told us.

**Worked around with `ENV PYTORCH_JIT=0`, which fixes it completely** — ComfyUI
then boots in 8.0 s and reports its device correctly. The proper fix is a real
3.11.15 from deadsnakes, which invalidates every layer below the apt install and
costs a full rebuild and re-push. **Deferred to Cycle 4 as a recorded trade-off.**

**What the workaround might cost, stated in advance rather than after.**
TorchScript is off in the container and on at home. kornia is used in IP-Adapter
image preprocessing, and 7 of the 9 `pg-41` plates condition on a reference
portrait, so a low-order pixel difference is possible in principle.
`tools/render_bench.py` pixel-compares every returned plate against the one home
already rendered, so this is measured, not assumed.

**The wider point is about where this was caught.** Nothing about this failure
needed a Runpod worker to find. Running the container on the machine that built
it costs nothing, and it turned what would have been a paid cold start ending in
a crash loop into a twenty-minute local diagnosis. The pixel-fidelity check in
Cycle 2 was built on the same principle: verify locally and free, before
spending.

---

## 2026-08-17 — Cycle 2

### Account baseline, before any spend


Read with `runpodctl user` and `runpodctl billing`, both free read-only queries.
This is the reference point every later cost in this cycle is measured against.

| Field | Value |
|---|---|
| `clientBalance` | **$49.9945861833** |
| `currentSpendPerHr` | $0 |
| `spendLimit` | $80 |
| Billing history — pods | `[]` |
| Billing history — serverless | `[]` |
| Billing history — network volumes | `[]` |

The billing histories are empty over an all-time window
(`--start-time 2024-01-01T00:00:00Z --end-time 2026-08-18T00:00:00Z
--bucket-size month`), not merely over the default one-day window. So nothing has
ever been charged to this account for pods, serverless, or network volumes.

**One thing this does not explain, recorded rather than guessed at.** The balance
is **$0.0054138167 short of a round $50.00**. Three categories of billing history
are empty, so that difference did not come from a pod, an endpoint, or a volume.
Two candidates: the credit was never exactly $50.00, or something was spent in a
category `runpodctl` cannot report. The only category it cannot report is
per-token **public endpoint** usage — there is no
`runpodctl billing public-endpoints` subcommand, though the REST API has
`get-public-endpoint-billing-history`.

That matters beyond bookkeeping: **if that $0.0054 was a public-endpoint charge,
it is direct evidence that this account's credit does pay for per-token
billing**, which is the Task 5 question the documentation cannot answer. It is a
lead, not an answer, and it is not counted as this project's spend — it predates
Cycle 2's first command.

### Sleepy Hollow — ingest integrity, checked before baking

Cycle 1 established the rule: verify ingest against the source before spending
any GPU time, because *Usher* silently lost 48% of its text and reported no
warnings. Sleepy Hollow was not previously ingested, so it was created fresh and
checked.

| Field | Value |
|---|---|
| Book | *The Legend of Sleepy Hollow* |
| Author | Washington Irving |
| Source | Project Gutenberg ebook #41 |
| Source words | **12,214** (after Project Gutenberg boilerplate is stripped) |
| Stored words | **12,187** |
| **Retention** | **99.78%** |
| Pages after pagination | 20 |
| Chapters detected | 2 |
| Ingest warnings | `[]` — none |
| Scriptorium book id | `pg-41` |

Source count measured the same way as Cycle 1: fetch
`https://www.gutenberg.org/ebooks/41.txt.utf-8`, cut everything outside the
Project Gutenberg START/END markers, count whitespace-separated tokens. Stored
count is the sum of the 20 page word counts in
`scriptorium-data/work/pg-41/pages/*.json`.

**The chapter-detection bug did fire, and it cost 27 words, none of them prose.**
This needs stating carefully, because "99.78%" could hide a real loss.

The warnings array is empty, and that is the *bad* sign rather than the good one.
`chapters_undetected` — the warning *Yellow Wallpaper* produced — only fires when
detection finds nothing and the whole-text fallback keeps everything. Its absence
means detection succeeded and `_chapters_from_headings` ran, which is the path
that drops text. Two headings were detected, both all-caps lines:
`FOUND AMONG THE PAPERS OF THE LATE DIEDRICH KNICKERBOCKER.` and
`FOUND IN THE HANDWRITING OF MR. KNICKERBOCKER.`

Every one of the 27 missing words is accounted for:

| Words | Text | Why it went |
|---:|---|---|
| 8 | `The Legend of Sleepy Hollow by Washington Irving` | precedes the first detected heading, so it falls outside every chapter |
| 9 | `FOUND AMONG THE PAPERS OF THE LATE DIEDRICH KNICKERBOCKER.` | became a chapter title in `structure.json` rather than body text |
| 7 | `FOUND IN THE HANDWRITING OF MR. KNICKERBOCKER.` | same |
| 1 | `POSTSCRIPT.` | classed as heading-ish |
| 2 | `THE END.` | classed as heading-ish |
| **27** | | **sums exactly to the measured shortfall** |

Not one word of narrative prose is among them. `CASTLE OF INDOLENCE.` — the
epigraph's attribution — was *not* detected as a heading and survives in the body.

Spot-checks both pass. The stored text opens `A pleasing land of drowsy head it
was, Of dreams that wave before the half-shut eye…` and closes `…“as to that
matter, I don't believe one-half of it myself.” D. K.`

**One incidental benefit.** Because the title-and-byline line was dropped,
Washington Irving cannot be mistaken for a character. *Yellow Wallpaper* kept its
byline inside page 1 and the cast stage duly picked up "Charlotte Perkins
Gilman" as a person in the story. The same defect that loses 8 words here
prevents a worse defect downstream.

**Verdict: pass.** Retention 99.78% against a 99.5% threshold set in advance,
with every missing word identified and none of it prose. Recorded, not fixed —
the defect belongs to Scriptorium and is out of scope this cycle.

### Sleepy Hollow — plate count

**9 plates in the measured run**, inside the settled 8–12 target. Read from
`selection.plates`, which is what the selection engine wrote.

| Reason | Count | Pages |
|---|---:|---|
| `chapter_open` | 2 | 0001, 0020 |
| `fill` | 5 | 0003, 0006, 0008, 0011, 0013 |
| `scene_boundary` | 2 | 0015, 0018 |

Selection parameters, unchanged from Cycle 1: preset `lavish`, `min_gap` 1,
`max_gap` 3, `salience_floor` 0.40, `chapter_open` and `scene_boundary` both on.

**The plate count is not deterministic, and that is worth knowing before anyone
cites it.** The pre-flight probe of the same book with the same settings selected
**10** plates; the measured run selected **9**. Nothing was changed between them.
The cause is upstream: `scene-update` and `cast-mentions` are language-model calls
run at `temperature` 0.2, so the per-page salience scores differ slightly from run
to run, and selection marks pages by comparing salience against
`salience_floor` and each other. Both runs landed inside 8–12, and the two
`scene_boundary` pages (0015, 0018) and both chapter openers were identical across
runs — it is the gap-filling positions that moved.

So the honest claim is **"Sleepy Hollow yields 9–10 plates at `lavish`"**, not a
single number, and the figure quoted alongside any timing is the one from that
same run.

**It is a better standard story than Yellow Wallpaper, not merely a longer one.**
Yellow Wallpaper produced 5 plates of which 4 were gap-filling, because a
first-person diary set in one room gives the selection engine almost no scene
changes to find. Sleepy Hollow contributes 2 genuine `scene_boundary` marks and 2
real chapter openers, so 4 of its 9 plates are chosen by content rather than by
spacing arithmetic.

### An observation about the cast, because it affects the render count

Cast canonicalization left 21 characters, 6 of them marked major, and the major
six are what get portraits. Several entries are plainly the same person:
`brom-bones`, `redoubtable-brom-bones` and `bones`; `van-tassel`,
`balt-van-tassel`, `old-baltus-van-tassel` and `mynheer-van-tassel`;
`headless-horseman`, `galloping-hessian` and `galloping-hessian-2`.

This is recorded because it is load-bearing for the numbers, not as a complaint:
portrait count follows the major-cast count, portraits are renders, and renders
are what the Runpod comparison measures. A different canonicalization would
change the total render count without changing the per-render time. It is a
Scriptorium quality issue, out of scope this cycle, and it was not touched.

### Baseline: the home bakery on Sleepy Hollow, end to end

One complete bake of `pg-41`, run unchanged on its normal home setup. Scriptorium's
source was not touched and its deployed configuration was not modified. Both human
review gates were cleared by the driver the instant they opened, so gate wait is
effectively zero and machine time equals wall clock.

Same hardware and models as Cycle 1: one NVIDIA RTX 5070 with 12 GB of video
memory, text model `qwen3.5:9b` served by Ollama behind text-transform-service,
image model `sd_xl_base_1.0` served by ComfyUI behind imagegen-service. Bake
settings: density preset `lavish`, `images_per_scene: 1`, portraits enabled,
portrait review off, style `oil-painting`, era `1790s Hudson Valley`.

**Wall clock: 388.63 s (6 min 29 s). Gate wait: 0.009 s.**

| Bucket | Time | Share |
|---|---:|---:|
| Text steps | 162.20 s | 41.7% |
| Image rendering | 123.34 s | 31.7% |
| Orchestration | 71.89 s | 18.5% |
| Model loading | 31.19 s | 8.0% |
| **Total** | **388.63 s** | **100%** |

Model loading is reported separately but happens *inside* the other two. Including
it, text steps took 165.49 s gross and image rendering 151.24 s gross.

**Text steps — 55 model calls, 162.20 s net**

| Transform | Calls | Total | Median |
|---|---:|---:|---:|
| `cast-mentions` | 20 | 59.86 s | 2.877 s |
| `scene-update` | 20 | 63.54 s | 2.946 s |
| `illustration-prompt` | 9 | 26.42 s | 2.523 s |
| `cast-canonicalize` | 6 | 15.67 s | 1.791 s |

All 55 returned 200. Call counts match artifact counts exactly (20 / 20 / 6),
which is how the measurement window is confirmed correct.

**Image rendering — 16 renders, 123.34 s net**

Warm render median **7.595 s** at 832×1216 (n=8). All 16 renders were attributed
to this bake and none were left unclaimed; pairing gap p50 was 0.38 s, max
0.592 s. The 16 are 9 plates, 6 character portraits at 1024×1024, and 1 cover.

**Model loading — 31.19 s**

| Cause | Count | Each | Total |
|---|---:|---:|---:|
| Image model reloaded after the orchestrator freed the GPU | 1 | 8.195 s | 8.20 s |
| Image model re-staged under video-memory pressure | 7 | 2.815 s | 19.71 s |
| Text model loaded cold | 1 | — | 3.29 s |

The orchestrator freed the GPU 4 times and unloaded the text model 3 times.
Incidental re-staging — ComfyUI evicting and restoring the image model under
12 GB of pressure — happened 7 times in 16 renders and again cost more than the
deliberate swapping did.

**Orchestration — 71.89 s**

| Component | Time |
|---|---:|
| Idle between phases (11 gaps, 5 s runner tick) | 34.11 s |
| Generating web and thumbnail derivatives | 6.95 s |
| Everything else (HTTP, artifact writes, ingest, publish) | 30.83 s |

Machine-readable output: `runs/pg-41/timing.json`. Driver log: `runs/pg-41/run.json`.
Collector integrity flags: counts match artifacts, residual non-negative, no
foreign transforms in the window, no warnings.

### Sleepy Hollow against Yellow Wallpaper — the constants hold

The point of re-measuring is not the wall clock, which obviously grows with a
longer book. It is whether the *derived* per-render constants reproduce.

| | `pg-1952` | `pg-41` | Difference |
|---|---:|---:|---:|
| Words | 6,085 | 12,187 | +100% |
| Pages | 11 | 20 | +82% |
| Plates | 5 | 9 | +80% |
| Renders | 12 / 12 | 16 / 16 | — |
| Text calls | 33 | 55 | +67% |
| Wall clock | 289.39 s | 388.63 s | +34% |
| **Warm render median** | **7.615 s** (n=6) | **7.595 s** (n=8) | **−0.3%** |
| Re-stage penalty | 2.795 s | 2.815 s | +0.7% |
| Reload-after-free penalty | 10.565 s | 8.195 s | −22% |
| GPU free events | 4 | 4 | — |

**The warm render median agrees to within 0.3% across two different books.** With
Cycle 1's two reference bakes (`pg-75201` at 7.44 s, `pg-28054` at 7.49 s) that is
four independent measurements of the same constant spanning 7.44–7.615 s. **7.6 s
per 832×1216 plate is a sound number to hold Runpod against.**

Two things did move, and both are explainable rather than noise:

- **Reload-after-free dropped 22%** (10.565 s → 8.195 s). It is a single event in
  each run, so it is one sample, not a median — a 2 s spread on one cold load is
  not a finding.
- **Text steps went from 28.6% of the run to 41.7%**, and the per-call medians rose
  (`cast-mentions` 1.869 s → 2.877 s). Sleepy Hollow's pages are longer (609 words
  average against 553) and it has 21 cast members against Yellow Wallpaper's
  smaller cast, so each call carries more input and returns more output. This is
  the more interesting shift for the migration: **on this book the text steps are
  now the largest bucket, larger than image rendering.**

**What that means for the Runpod plan.** Image generation — the part moving to
Flash first — is 31.7% of this run, close to Cycle 1's 32.8%. But text steps are
now 41.7%. Moving rendering to Runpod addresses the second-largest bucket, not the
largest. The hosted per-token endpoints in Task 5 matter more than Cycle 1's
numbers suggested.

### The standard comparison story is now Sleepy Hollow

Locked. Every home-versus-Runpod measurement from here uses this book.

| Field | Value |
|---|---|
| Book | *The Legend of Sleepy Hollow* |
| Author | Washington Irving |
| Source | Project Gutenberg ebook #41 |
| Source words | 12,214 |
| Stored words | 12,187 (99.78% retention) |
| Pages | 20 |
| Plates | 9–10 at `lavish` (9 in the measured run) |
| Renders | 16 (9 plates + 6 portraits + 1 cover) |
| Scriptorium book id | `pg-41` |
| Bake settings | `lavish`, `images_per_scene: 1`, portraits on, portrait review off, `oil-painting`, era `1790s Hudson Valley` |

It replaces *The Yellow Wallpaper*, which is **superseded, not deleted** — its
numbers below are the evidence for the 7.6 s constant and remain citable as such.
The reason for the change is the plate count: the brief asked for a story yielding
8–12 plates, Yellow Wallpaper produced 5 and structurally could not do better, and
Sleepy Hollow produces 9–10 with 4 of them chosen by content rather than spacing.

### Tooling versions these numbers came from

| Tool | Version |
|---|---|
| `runpodctl` | `2.9.0-c094cac`, installed from the pinned GitHub release, SHA256 verified against `checksums_2.9.0_sha256.txt` |
| `flash` | `Runpod Flash CLI v1.19.0` (`runpod-flash` 1.19.0 on Python 3.13) |

### Key check result

| Tool | Reads the installed `~/.runpod/config.toml`? |
|---|---|
| `runpodctl` | **Yes.** `runpodctl user` returns the account record with nothing set in the environment. |
| `flash` | **No.** Every account-touching subcommand fails with `RunpodAPIKeyError`. |

The cause is a format mismatch, not a missing key: `runpodctl` uses a top-level
`apikey`, while `flash` requires a `[default]` table containing `api_key`. Full
diagnosis and the draft issue are in [AI-ASSIST.md](AI-ASSIST.md); the practical
consequence is in [hello-flash/README.md](hello-flash/README.md) under "Two CLIs,
one file, two formats".

**This blocks deployment.** Nothing that needs `flash` can run until `flash login`
is done once, interactively, in a browser. No workaround was attempted, because
every remedy the CLI itself suggests requires extracting the plaintext key.

### Does an idle Flash app with zero workers bill anything?

**No — provided no network volume is attached and minimum workers is 0.**

The question was asked specifically about container storage, because Runpod's
serverless pricing page lists container disk as its own cost line with a
"(5-min intervals)" qualifier, which reads like something that accrues on a timer
whether or not anything is running. It does not.

**The decisive sentence is on a different page from the price.**
`docs.runpod.io/serverless/storage/overview` describes container disk as
"Temporary storage that exists only while a worker is running", and gives its cost
as "**included in the worker's running cost**". So container storage is not a
separate meter that outlives the worker; it is part of the worker's per-second
charge. At zero workers there is no worker cost, so there is no container storage
cost, because there is no container.

Two further statements agree:

- `docs.runpod.io/serverless/workers/overview` — flex workers "cost nothing when
  not in use."
- `docs.runpod.io/pods/pricing` — the only Runpod table that says it outright:
  container disk is "**Not charged**" on a stopped Pod. Network volume, in the same
  table, costs the same stopped or running.

**On the five-minute interval specifically**, there are two different statements
and conflating them is the trap:

1. `docs.runpod.io/accounts-billing/billing` — "Billing runs every 5 minutes, and
   charges are deducted continuously based on the resources you have running."
   That is the account-wide ledger sweep, and it is scoped to *running* resources.
   At zero workers the sweep finds nothing to charge.
2. `docs.runpod.io/serverless/pricing`, container-disk row — "Worker storage
   (5-min intervals)". That parenthetical is the entire text on the subject, and it
   is never defined anywhere.

**So container storage's 5-minute billing does not apply at zero workers, because
container storage does not exist at zero workers.**

**The one thing that does bill at idle is a network volume.** Charged continuously,
stopped or running, at $0.07/GB/month under 1 TB. Flash's `NetworkVolume` defaults
to 100 GB, so attaching one would burn about **$7.00 a month** whether or not a
single request ever arrived. That is why the production image-generation app fetches
its weights at build time instead of mounting them.

**Decision: leave the app deployed.** Tearing it down buys nothing and costs a
rebuild.

**The empirical half is not done, and the answer above is documentary only.** The
brief asked for confirmation against the account's real billing records after a
deployment. Nothing has been deployed, because `flash` cannot authenticate (above),
so there is no idle window to measure. What the check would look for is recorded
now so it can be run without re-deriving it:

> If Flash's default 64 GB container disk *were* billed at zero workers,
> $0.10/GB/month would accrue **$0.0089/hr** — so a three-hour idle window should
> show about **$0.027** against `runpodctl billing serverless`, which is clearly
> distinguishable from $0.00. Read `runpodctl billing serverless` and
> `runpodctl billing network-volume` at deploy time and again after the window,
> and record the achieved idle duration alongside the result.

### Runpod's hosted per-token text models

Runpod calls these **Public Endpoints**: models Runpod operates, billed per token,
with nothing to deploy, no workers to scale, no cold start you own and nothing to
tear down. Enumerated from the documentation, free. **No call was made** — see the
end of this section.

Base URL `https://api.runpod.ai/v2/{slug}`. Two request shapes: a native
`/runsync` that wraps arguments in an `input` object, and an OpenAI-compatible
`/openai/v1/chat/completions`.

| Model | Model id | Input /1M | Output /1M |
|---|---|---:|---:|
| Cogito 671B v2.1 FP8 | `cogito-671b-v2-1-fp8-dynamic` | $0.50 blended | |
| Moonshot Kimi k2.6 | `kimi-k2.6` | $0.95 | $4.00 |
| Moonshot Kimi k2.7-code | `kimi-k2.7-code` | $0.95 | $4.00 |
| Moonshot Kimi k3 | `kimi-k3` | $3.00 | $15.00 |
| Qwen3 32B AWQ | `Qwen/Qwen3-32B-AWQ` | $10.00 blended | |
| GPT-OSS 120B | `openai/gpt-oss-120b` | $10.00 blended | |
| IBM Granite 4.0 | `granite-4-0-h-small` | $10.00 blended | |

"Blended" means the documentation quotes one rate covering input and output
together; only the Kimi models publish a split. Source:
`docs.runpod.io/public-endpoints/reference` and the per-model pages under
`docs.runpod.io/public-endpoints/models/`.

Two documented facts that matter for cost modelling: **failed generations are not
charged**, and there is **no idle cost**, because nothing is deployed.

### Which of them could do Scriptorium's text steps

The three text steps are `cast-mentions` (who is on this page), `scene-update`
(what changed) and `illustration-prompt` (what a picture of it should show). All
three send roughly a page of prose and expect short structured JSON back.

Home does this with `qwen3.5:9b` at Q8_0 through Ollama. Measured on the `pg-41`
baseline above: 55 calls, medians 1.791–2.946 s, `temperature` 0.2–0.5,
`num_predict` 350–700, and input around 570–770 estimated tokens per call. That is
an instruction-following job, not a reasoning-heavy one, so **none of these models
is short of capability** — the choice is about price and output discipline.

- **Cogito 671B v2.1** — $0.50/1M blended, 20× cheaper than the $10 tier. The
  value pick.
- **Qwen3 32B AWQ** — $10.00/1M, documented for "reasoning, instruction-following,
  agent capabilities". Same model family as the one home already runs, which makes
  it the most likely to behave similarly on prompts that were tuned against
  `qwen3.5:9b`. That is worth something real when the prompts are not being
  rewritten.
- **Kimi k2.6** — $0.95 in / $4.00 out. Wins when output is short relative to
  input, which is this workload's shape.

**A rough cost sketch, from the baseline's measured token counts.** 55 calls at
roughly 700 input and 300 output tokens is about 38,500 input and 16,500 output
tokens per book. At Cogito's $0.50/1M blended that is **about $0.03 per book**. At
the $10/1M tier it is **about $0.55 per book**. Both are estimates from published
prices against measured call counts, not charges, and the token figures are
Scriptorium's own estimator (`TOKENS_PER_WORD = 1.35`), not a tokenizer.

**The gap that matters more than price.** No Runpod page documents JSON mode,
`response_format`, or grammar-constrained decoding for public endpoints.
Scriptorium's transforms need parseable JSON and currently get it from a local
Ollama that can constrain output. Moving those steps to a public endpoint means
relying on the prompt alone unless the OpenAI-compatible route happens to accept
`response_format` undocumented. That is a functional risk, not a cost one, and it
is the thing to test first.

### Do the assignment credits cover per-token billing?

**Not established from the documentation — and the documentation is the wrong place
to settle it.** What exists:

- Billing docs say credits "can only be used for Runpod services": a restriction
  *to* Runpod, with no carve-out excluding any product line.
- There is a first-class `get-public-endpoint-billing-history` REST endpoint, which
  puts public-endpoint spend in the same billing-history family as pods, serverless
  and volumes, implying one shared ledger.
- But the single sentence enumerating what credits are spent on says "Pods,
  Serverless endpoints, and storage" and omits public endpoints, and the word
  "promotional" does not appear in the billing documentation at all.

**The account itself is better evidence than the docs, and it points to yes.** The
pre-spend baseline at the top of this cycle shows a balance $0.0054138167 below a
round $50.00 with all three `runpodctl billing` categories empty over an all-time
window. The one spend category `runpodctl` cannot report is per-token
public-endpoint usage. If that shortfall is a public-endpoint charge, then this
account's credit demonstrably pays for per-token billing.

That is a strong lead, **not proof** — the alternative explanation is simply that
the credit was never exactly $50.00. Closing it needs either the console's billing
view or a `get-public-endpoint-billing-history` call.

### The Runpod render app reproduces the home graph exactly

Measured, not asserted. The app is built and **not deployed**, so there is no
Runpod render time yet — but the thing that makes such a number honest is settled,
and it is settled by comparing output rather than by comparing settings tables.

`flash-imagegen/verify_port.py` rebuilds a plate the home bakery already rendered,
using the seed, positive prompt and negative prompt recorded in that plate's own
provenance file, submits it to the local ComfyUI, and compares the result against
the stored PNG pixel by pixel.

| Plate | Path exercised | Differing pixels | Max abs difference |
|---|---|---:|---:|
| `pg-41` `0001` | LoRA only | **0** of 1,011,712 | 0 |
| `pg-41` `0003` | LoRA + IP-Adapter | **0** of 1,011,712 | 0 |

Pixel-identical on both paths. SDXL at a fixed seed is deterministic, so any
difference in checkpoint, VAE, LoRA, sampler, scheduler, step count, CFG, size or
IP-Adapter wiring would change the image. The 7 of 9 Sleepy Hollow plates that
used a character reference make the second row the more important one.

**It failed the first time, which is the reason the check exists.** The initial
port *set* the negative prompt on node `7`. imagegen-service *appends* it — the
workflow template carries a baseline `blurry, lowres, deformed, text, watermark`
and the caller's negative is joined onto it (`engine.ts:562-569`). Replacing it
dropped five negative terms and changed **1,010,483 of 1,011,712 pixels**. Every
setting in the comparison table was correct at the time.

Model files are verified the same way rather than trusted by filename: all five
match the recorded byte count and SHA256 of the files the home machine is running
(`flash-imagegen/fetch_models.py --check-only`, 5 of 5 ok). The style LoRA's hash,
`74b377ee…adc87fd`, also matches CivitAI's record for version 2.1 and the
creator's own HuggingFace mirror, which is what establishes its provenance.

Pinned for this to stay true: ComfyUI 0.27.0 at `6cc8144`, `ComfyUI_IPAdapter_plus`
at `a0f451a`, torch 2.11.0+cu128.

### The test call was not made

It needs an `Authorization: Bearer` header, and the only way to build one here is
to extract the plaintext key out of `~/.runpod/config.toml`. `runpodctl` has no
subcommand that invokes a public endpoint, so there is no tool-mediated route that
leaves the key unread. Deferred rather than worked around — the estimate stands at
about $0.002 for two calls, which is not the reason it did not happen.

---

## 2026-08-17 — Cycle 1

### The standard comparison story — SUPERSEDED 2026-08-17 by `pg-41`

> **Superseded in Cycle 2.** The standard comparison story is now *The Legend of
> Sleepy Hollow* (`pg-41`) — see "The standard comparison story is now Sleepy
> Hollow" above. The reason is the plate count: the brief asked for a story
> yielding 8–12 plates and this one yields 5, for structural reasons given below.
>
> Everything in this section is still **correct and still cited.** The 7.615 s
> warm render median measured here is one of the four independent measurements
> that establish the 7.6 s per-plate constant, and the Runpod comparison rests on
> it. Kept verbatim rather than rewritten.

Every home-vs-Runpod measurement from here on uses the same book, so the
numbers stay comparable across cycles.

| Field | Value |
|---|---|
| Book | *The Yellow Wallpaper* |
| Author | Charlotte Perkins Gilman |
| Source | Project Gutenberg ebook #1952 |
| Words | 6,085 (after Project Gutenberg boilerplate is stripped) |
| Pages after pagination | 11 (Scriptorium targets 550 words per page) |
| Scriptorium book id | `pg-1952` |

Bake settings: density preset `lavish`, `images_per_scene: 1`, portraits
enabled, portrait review off, style `oil-painting`, era `1890s New England`.

**Ingest verified before baking:** the 11 pages contain 6,085 words, i.e. 100.0%
of the source. This check exists because the first story tried failed it — see
"Story #932 was rejected" below.

**Plate count came in under target.** The brief asked for a story sized to yield
8–12 plates. Selection chose **5**. The reason is in `selection.json`: the
selection engine marks a page when the scene changes, then fills gaps so no run
of pages exceeds `max_gap` (3 on `lavish`). *The Yellow Wallpaper* is a
first-person diary set almost entirely in one room, so the model found nearly no
scene changes and 4 of the 5 plates were chosen by gap-filling rather than by
content. With 11 pages and `max_gap: 3`, roughly 4–5 plates is the floor this
story can produce.

Total rendered images was **12**, which is in the intended range, but they are
not all plates:

| Image kind | Count | Size |
|---|---|---|
| Plates | 5 | 832×1216 |
| Cover | 1 | 832×1216 |
| Character portraits | 6 | 1024×1024 |
| **Total renders** | **12** | |

This is a decision Kris needs to make before Cycle 2, because the standard story
is locked once later measurements start citing it. Options are in the status
report.

### Baseline: the home bakery, end to end

One complete bake of `pg-1952`, run unchanged on its normal home setup — the
deployed service configuration was not modified, and Scriptorium's source was
not touched. Both human review gates were cleared by an automated driver the
instant they opened, so gate wait is effectively zero and machine time equals
wall clock.

Hardware: one NVIDIA RTX 5070, 12 GB of video memory. Text model
`qwen3.5:9b` served by Ollama behind text-transform-service. Image model
`sd_xl_base_1.0` served by ComfyUI behind imagegen-service.

**Wall clock: 289.39 s (4 min 49 s). Gate wait: 0.016 s.**

| Bucket | Time | Share |
|---|---:|---:|
| Image rendering | 94.79 s | 32.8% |
| Text steps | 82.64 s | 28.6% |
| Orchestration | 72.25 s | 25.0% |
| Model loading | 39.71 s | 13.7% |
| **Total** | **289.39 s** | **100%** |

Model loading is reported separately but happens *inside* the other two — a
model load is part of whichever request triggered it. Including it, text steps
took 97.81 s gross and image rendering took 119.33 s gross.

**Text steps — 33 model calls, 82.64 s net**

| Transform | Calls | Total | Median |
|---|---:|---:|---:|
| `cast-mentions` | 11 | 34.5 s | 1.869 s |
| `scene-update` | 11 | 34.2 s | 2.720 s |
| `cast-canonicalize` | 6 | 14.1 s | 1.639 s |
| `illustration-prompt` | 5 | 14.9 s | 1.971 s |

All 33 returned 200. Call counts match artifact file counts exactly (11 / 11 /
6), which is how the measurement window is confirmed correct.

**Image rendering — 12 renders, 94.79 s net**

Warm render median **7.615 s** at 832×1216 (n=6). All 12 renders were attributed
to this bake; none were left unclaimed.

**Model loading — 39.71 s, and this is the interesting number**

| Cause | Count | Each | Total |
|---|---:|---:|---:|
| Image model reloaded after the orchestrator freed the GPU | 1 | 10.565 s | 10.56 s |
| Image model re-staged under video-memory pressure | 5 | 2.795 s | 13.97 s |
| Text model loaded cold | 1 | — | 15.17 s |

The orchestrator freed the GPU 4 times and unloaded the text model 3 times
during this run. That deliberate swapping cost 10.6 s. The *incidental*
re-staging — ComfyUI evicting and restoring the image model under 12 GB of
video-memory pressure — happened 5 times in 12 renders and cost more.

**Orchestration — 72.25 s, a quarter of the run**

| Component | Time |
|---|---:|
| Idle between phases (11 gaps, 5 s runner tick) | 36.21 s |
| Generating web and thumbnail derivatives | 5.47 s |
| Everything else (HTTP, artifact writes, ingest, publish) | 30.57 s |

The single worker sleeps 5 seconds between advancing phases. On a book this
short that fixed cost is 12.5% of the entire run, spent doing nothing.

Machine-readable output: `runs/pg-1952/timing.json`. Driver log:
`runs/pg-1952/run.json`.

**What this means for the Runpod comparison.** Only 32.8% of this run was image
generation — the part moving to Flash first. A further 28.6% is text steps,
which move to a hosted endpoint later. The remaining 38.7% is orchestration and
model loading, and model loading is a cost that mostly *disappears* when the two
models stop sharing one GPU.

### Story #932 was rejected, and why it matters

The first choice was *The Fall of the House of Usher* (Project Gutenberg #932,
7,087 words). Scriptorium's ingest produced 11 pages containing only 3,670
words — **48% of the story was silently discarded**, including the entire
opening.

Cause: `detect_chapters` in `server/src/scriptorium/ingest/base.py:323` builds
chapters from detected headings, and `_chapters_from_headings` keeps only text
that falls under a heading. Usher contains an interior poem, "The Haunted
Palace", whose six stanzas are numbered I–VI. Those stanza numbers were detected
as chapter headings, so everything before the poem — the narrator's arrival and
the description of the house — fell outside every chapter and was dropped. The
resulting book reported no warnings.

This is a Scriptorium defect, not a Runpod one. It is out of scope this cycle
and was not fixed. It is recorded here because it is the reason the standard
story changed, and because any book with interior numbered sections is affected.

The check that catches it is one line: after ingest, compare the sum of page
word counts against the source word count. *The Yellow Wallpaper* returns
100.0%; *Usher* returns 51.8%.

### Hello-world Flash app

*Blocked.* No Runpod API key is present on this machine, so nothing was
deployed and nothing was spent. See the status report for the one step that
unblocks it.

---

## Reference numbers from earlier runs

Not produced by this project. Two bakes were already on disk when this work
started, and they are what `tools/bake_timing.py` was validated against before
it was trusted on the run above.

| | `pg-75201` | `pg-28054` | `pg-1952` (this cycle) |
|---|---:|---:|---:|
| Wall clock | 46 m 40 s | 10 h 01 m | 4 m 49 s |
| Renders attributed | 145 / 147 | 452 / 454 | 12 / 12 |
| Warm render median | 7.44 s | 7.49 s | 7.615 s |
| Re-stage penalty | 2.89 s | 2.80 s | 2.795 s |
| Reload-after-free penalty | 10.07 s | 10.49 s | 10.565 s |
| GPU free events | 4 | 4 | 4 |

The three derived constants agree to within 4% across three independent bakes
run days apart, which is the evidence that the measurement method is sound
rather than a coincidence of one run.

`pg-28054`'s bucket *percentages* are meaningless — that run sat about seven
hours at an overnight human review gate, so orchestration swallows 74.6% of it.
Its absolute seconds and derived constants are still usable. The collector also
correctly flags that run's window as contaminated by another project's traffic.

**Collector validation.** Before use, `tools/bake_timing.py` was required to
reproduce both past bakes within tolerance *and* to fail loudly when given a
deliberately wrong window. Widening `pg-75201`'s window by 15 minutes either
side made it report a count mismatch and 29 unattributable renders, which is the
behaviour wanted — a silent wrong answer is worse than a loud refusal.
