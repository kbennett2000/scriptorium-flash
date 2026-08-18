# The numbers

Every figure on this page appears in [FINDINGS.md](../FINDINGS.md), under the heading
named beside it. `tools/check_numbers.py` fails if a number here is not in the log.
**Nothing goes on a slide that is not on this page.**

---

## The headline

*The headline bake: 325.24 s against home's 388.63 s*

| Bucket | Home | Runpod | Change |
|---|---:|---:|---:|
| Text steps | 162.20 s | 161.36 s | −0.84 s |
| Image rendering | 123.34 s | 59.74 s | −63.60 s |
| Model loading | 31.19 s | 23.22 s | −7.97 s |
| Orchestration | 71.89 s | 80.92 s | +9.03 s |
| **Wall clock** | **388.63 s** | **325.24 s** | **−63.39 s** |

- **1.195× end to end** — and Runpod produced **18 images against home's 16**, so the
  faster run also did more work.
- Of the ~65 s the render bucket saved, **72% is the faster card, 28% is the fan-out**:
  46.7 s from silicon, 18.4 s from overlapping.
- **Amdahl's floor is 251.5 s** — `325.24 − 59.74 − 14.02`. Text and orchestration are
  **74%** of the run. (`14.02` is SDXL's share of the model-loading bucket; ollama is the
  other 9.2 s.)

## The fan-out is not ours to set

*The showcase book: 91 renders, the fleet finally opened*

| | `pg-41` | `pg-120` |
|---|---:|---:|
| Renders | 18 | 91 |
| Work the workers reported | 92.13 s | 456.36 s |
| Wall clock it occupied | 73.76 s | 242.67 s |
| **`overlap_factor`** | **1.249** | **1.881** |

Concurrency was configured to **4** both times. Same image, same pin, same code. **Two
runs, two answers** — whether Runpod's scaler opens the workers is not something the
caller controls, and the deployed configuration does not predict it.

## Render latency

| | |
|---|---:|
| Home, warm median, 832×1216 | **7.595 s** (n=8) |
| Runpod 4090, `pg-120` warm median | **4.3080 s** (n=91) |
| Runpod 4090, `pg-41` warm-only median | 4.2790 s (n=16) |
| Runpod 4090, `pg-41` bake median | 4.7725 s (n=18) |
| Runpod 24 GB tier, corrected | 11.937 s |

**Say which median.** 4.7725 s is the median of all 18 renders in the headline bake, two
of which carried a cold model load. Excluding those, it is 4.2790 s. The published
**1.59×** per-image speedup uses the conservative figure; warm to warm it is **1.78×**.

**Do not cite raw:** 12.381 s and 4.406 s (superseded by 11.937 s and 4.2175 s); 5.023 s
(superseded by 4.7725 s); the render `summary.json` `cost_usd` values.

## Cold start and image size

| | |
|---|---:|
| Cold start, wall | **489.82 s** |
| of which image pull + worker start | 478.2 s |
| ComfyUI boot | 2.51 s |
| **What Runpod pulls** | **17.72 GB** |
| What it unpacks to | 24.26 GB |
| What `docker images` reports | 42.0 GB — blobs **and** snapshot, added together |
| Measured pull rate | 37.1 MB/s |

A cold start is **seven to eight minutes**. **Image pull is not billed** — 775 s of
pulling across two passes appears in no billed time.

The image ships **two complete CUDA stacks** and PyTorch opens neither of the apt ones:
`ldd` resolves every CUDA library into the pip wheels. Available diet **4.94 GB / 133.2 s**,
of which **3.62 GB / 97.6 s** carries no fidelity risk. That takes cold start to
**~357 s** — 8.2 minutes to 5.9. **Not done, by decision: it shortens the cold start, and
the warm-up removes it.**

## Warm, and what warm looks like

| | |
|---|---:|
| Live-demo request, `pg-41`, 832×832 | **5.06 s** end to end, **3.897 s** render |
| Live-demo request, `pg-120`, 832×832 | **7.19 s** end to end, **3.559 s** render |
| `delayTime` on the `pg-41` demo | **23 ms** |
| `model_load_s` on both | **0** |
| Pre-warm render, **512 px** | ~1.51 s |

**~1.51 s is a 512-pixel warm-up render, not a plate.**

## Cost

| | |
|---|---:|
| Per warm plate, pinned 4090 | $0.001742 |
| Rates | $1.10/hr (4090), $0.69/hr (24 GB), $0.58/hr (16 GB) |
| `pg-41`, 18 renders, all in | **$0.1037042686** |
| `pg-120`, 91 renders, all in | **$0.4282544446** |
| Project total | **$1.1320333838** |

Ledger and billing history agree to **3×10⁻¹⁰, 3×10⁻¹⁰ and 5×10⁻¹⁰**. Billing history
lags about a day. Query **all three** categories — a serverless charge posted under
`pods`.

**Idle costs nothing.** `workersStandby` measured **$0.00** across 11 m 13 s and again
across 2 h 59 m 37 s, and a fourth time across a 45-minute stall in Cycle 5.

## Fidelity

| | |
|---|---:|
| Total pixels per plate | 1,011,712 |
| Container against home, correct conditioning | **0 differing pixels**, all nine plates |
| Cold-load render against warm | **842,339** (83.3%), max abs **221** |

A plate re-renders identically only when the card **and** the model-residency state
match. Conditioning alone accounted for **26.9** and **45.0** points of Cycle 3's
divergence.

## The one nobody expects

*The home baseline assumes an uncontended GPU*

The text model, sharing the home card with another workload, kept **0.13 GB of its
6.19 GB** in VRAM and ran the rest on CPU. `illustration-prompt` went from **2.523 s** to
**26–155 s**. Given the card back, it returned to **1.9–2.8 s**.

**37× on the text steps, against 1.59× on the renders.** The rented GPU is not competing
with a browser. Isolation is the third thing serverless buys, after faster silicon and
fan-out, and on this evidence it is worth more than either.

---

# Demo day

## Warm-up — 10 to 15 minutes before speaking

1. **Send one warm-up render.** A cold worker is **~490 s**, of which 478.2 s is pull.
2. **Verify warmth by `model_load_s: 0` and the render-time signature. Never by
   `COMPLETED`.** Cycle 4's pre-warm checked status alone: all four requests returned
   COMPLETED and exactly one worker had loaded a model. Cycle 5 reproduced it exactly.
3. **Corroborate with `GET /v2/<id>/health`** — want `idle`/`ready`/`running`.
   `initializing` and `throttled` are not warm. And `ready` does not predict latency: the
   health route reported `idle: 1, ready: 1` before a request that still paid a 31.387 s
   cold start.
4. **Then leave it alone.** `workersStandby` tracks `workersMax`, so the fleet stays warm
   by itself at a measured $0.00. On stage the defect is an advantage — and it is the
   same defect reported as [runpod/flash#364](https://github.com/runpod/flash/issues/364).

## If it goes wrong, in this order

1. **Live bake** — the whole thing, end to end.
2. **Warm single render** — one request, ~5 s, against the already-warm worker.
3. **The showcase book** — <https://scriptorium-reader.vercel.app>. Static, no server,
   nothing live to fail. Reading, search, cast and every illustration work offline;
   highlights and reading position do not persist, because sync needs a PUT.

## Two things not to claim

- The `pg-120` **wall clock** is contaminated by the GPU-contention stall and by foreign
  renders inside its window. The per-render numbers are sound; the end-to-end figure is
  not a comparison.
- **88 of the 91 shipped images are verified warm** from their own echoes. Three were
  regenerated and are warm by inference, because the regen route does not record the
  worker's echo.
