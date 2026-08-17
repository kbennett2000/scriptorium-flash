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
| — | Nothing spent yet | $0.00 | — |

**Total Runpod spend to date: $0.00**

---

## 2026-08-17 — Cycle 1

### The standard comparison story

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
