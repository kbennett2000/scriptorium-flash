# runs/ — the evidence behind FINDINGS.md

Every number in [FINDINGS.md](../FINDINGS.md) that came from a measurement points
at something in here. These are raw artifacts: they are not summarised, and where
one carries a known error it keeps it (see "Two artifacts that carry their own
errors" below).

Raw journal snapshots are **not** committed — they are bulky and contain log text
from every service on the machine. The derived timing JSON and run logs are.

## What each directory holds

| Directory | Book | What it is |
|---|---|---|
| `pg-41/` | Sleepy Hollow | **The home baseline.** 388.63 s end to end, all work on the desktop RTX 5070. |
| `pg-41-runpod/` | Sleepy Hollow | **The headline bake.** 325.24 s, text at home, 18 plates on a pinned RTX 4090. |
| `pg-120/` | Treasure Island | Home probe, stopped before rendering, plus the ingest audit. |
| `pg-120-runpod/` | Treasure Island | **The showcase bake.** 91 renders, 1.881 wide, $0.4282544446. The book this produced is the one published to Vercel. |
| `pg-1952/` | The Yellow Wallpaper | A second home reference: 289.39 s, warm median 7.615 s (n=6). |
| `reference/` | two long books | Two large historical home bakes, re-derived by `bake_timing.py`. Their value is the home warm-render constant across four books. |
| `runpod-render/` | — | Cycle 3/4 render-bench passes, one directory per GPU tier, with the pixel comparisons against home. |
| `public-endpoint/` | — | Cycle 3 probes of Runpod's hosted per-token text models. 26 calls, 0 clean parses. |
| `image-diet.txt` | — | Layer-by-layer analysis of what the container image pulls, and what a diet would save. |

## The files inside a bake directory

| File | What it is |
|---|---|
| `run.json` | The driver's own record: start and end, state transitions, gates, plate count. |
| `timing.json` | `bake_timing.py`'s decomposition of the wall clock into text / rendering / model loading / orchestration, plus per-plate render seconds. |
| `prewarm.json` | Every pre-warm request, with each worker's `delayTime`, `model_load_s` and `render_s`. This is where you can see whether the fleet actually opened. |
| `warm-demo.json` | One request against an already-warm worker — the live-demo configuration. |
| `health-samples.json` | Periodic `/health` reads across the bake (`pg-41-runpod` only). |
| `bake-console.log` | The driver transcript, as it was printed. |
| `balance-settle.log` | Consecutive balance reads until the charge stopped moving. |

## Two artifacts that carry their own errors

Neither is corrected in place. A measurement artifact that is quietly edited
after the fact is worth less than one that carries its own error, and in both
cases the error is the more useful record.

**1. `runpod-render/`'s `cost_usd` fields are wrong.** They were read off a
balance that was stable but not settled. See
[runs/runpod-render/README.md](runpod-render/README.md) for the full account and
the right figures. Cite FINDINGS.md for cost.

**2. `pg-41-runpod/run.json` names the wrong book.** Its `request.title` reads
`"The Fall of the House of Usher"` by `"Poe, Edgar Allan"`. The bake is
demonstrably *The Legend of Sleepy Hollow*: the home baseline of the same
`book_id` records the right title, and the portraits this run rendered are
`portrait-ichabod`, `portrait-brom-bones`, `portrait-katrina-van-tassel`,
`portrait-hans-van-ripper` and `portrait-old-baltus-van-tassel`.

The cause is not a mystery. `run_baseline.py` defaults `--title` and `--author`
to Usher/Poe, and `headline_bake.sh` never overrode them — the defect is recorded
at [tools/showcase_bake.sh:20-23](../tools/showcase_bake.sh#L20), which is where
it was found and fixed for the showcase run. **Nothing in this repo quotes a book
title from this file**, and the timings it records are unaffected: the title is
request metadata, not a measurement.
