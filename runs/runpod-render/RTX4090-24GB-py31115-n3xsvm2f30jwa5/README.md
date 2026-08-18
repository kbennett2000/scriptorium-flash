# The Cycle 4 comparison set: what these four PNGs are for

Six renders ran on endpoint `n3xsvm2f30jwa5`, a single pinned RTX 4090, on the
rebuilt image `sdxl-base-1.0-py31115` (real Python 3.11.15, no `PYTORCH_JIT=0`).
Four PNGs are kept. The other two were deleted, and that is the point of this note.

## Kept: the two A/B pairs, which are the whole argument

| File | Plate | Figures | IP-Adapter conditioning sent | Differs from home |
|---|---|---:|---|---:|
| `0008-nocond.png` | 0008 | 2 | **omitted** → worker default 0.5 / 0.3 | 993,300 (98.2%) |
| `0008.png` | 0008 | 2 | **0.35 / 0.4**, what home sent | **721,810 (71.3%)** |
| `0013-nocond.png` | 0013 | 3 | **omitted** → worker default 0.5 / 0.3 | 989,906 (97.8%) |
| `0013.png` | 0013 | 3 | **0.35 / 0.4**, what home sent | **533,994 (52.8%)** |

Same worker, same card, same seed, minutes apart. The only variable is two floats,
and they account for **26.9** and **45.0** points of divergence. What remains is
silicon, and it sits inside the band the single-figure plates already occupied.

Scriptorium gives a plate with more than one figure a weaker, later identity anchor
(`reference_conditioning`, `p7_render.py:333-340`). Before Cycle 4 this port had no
input for it, so every multi-figure plate rendered here was a computation home never
ran. See FINDINGS.md.

## Deleted: `0001.png` and `0003.png`, because they were byte-identical to Cycle 3's

Both returned exactly the pixel counts the Cycle 3 container returned for the same
requests on the same card — 637,911 and 633,047 — and `0001.png` was verified
byte-identical to `../RTX4090-24GB-h4rz8tmjkq35fu/0001.png` before being removed.

That identity is the finding: **the interpreter fix moved no pixels.** Keeping a
second copy of an image this repo already stores would add 3.1 MB and no evidence.
The number is in `summary.json` and the comparison is in FINDINGS.md.
