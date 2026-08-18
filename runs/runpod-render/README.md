# Runpod render measurements

One directory per tier. `summary.json` is the full record: per-plate wall clock,
`delayTime`/`executionTime`, the handler's own `model_load_s`/`render_s`, the GPU
the worker actually ran on, and the pixel comparison against the plate home
already rendered.

**Only two plates per tier are kept as PNGs**, not all seven. The full set is
20 MB and the numbers that matter — `differing_pixels` and `max_abs` — are in
`summary.json` for every plate. The two kept are the ones an argument rests on:

- **`0001`** — the only plate with **no IP-Adapter reference**. It differs from
  home by 79.6% (24 GB tier) and 63.1% (4090), which is what rules out
  `PYTORCH_JIT=0` as the cause of the difference: kornia and TorchScript are not
  in this path at all.
- **`0008`** — the largest divergence measured, 98.2% on both tiers.

Regenerate any of the rest with `tools/render_bench.py`; the seeds and prompts
come from the plates' own provenance files, so they are reproducible on the same
hardware.

## The `cost_usd` in these two files is wrong; FINDINGS.md has the right number

| File | `cost_usd` recorded here | Ledger (FINDINGS.md) |
|---|---:|---:|
| `A5000-3090-24GB-ugculdhag081uh/summary.json` | 0.0118587491 | **$0.0376933074** |
| `RTX4090-24GB-h4rz8tmjkq35fu/summary.json` | 0.0268797963 | **$0.0439145185** |

`balance_before` in both files matches the ledger exactly. Only the "after" reading
differs, and it differs the same way in both: it was taken while the balance was
still settling.

`render_bench.settled_balance()` waits for two consecutive equal reads 30 s apart.
That is a test for **stable**, and this project's own recorded lesson is that a
stable balance reading is not a settled one — Runpod's balance lags a charge by
minutes, and it can sit still in the middle of that lag. So the field named
`balance_after_settled` holds a reading that was stable and not settled.

The ledger figures are the later reads. On 2026-08-18 the billing-history API
finally showed these charges and independently confirmed the ledger to nine
decimal places (0.0376933077 and 0.0439145190), from an instrument that is not
the balance at all.

**These files are deliberately not edited.** A measurement artifact that is quietly
corrected after the fact is worth less than one that carries its own error, and the
error is the more useful of the two things recorded here. Cite FINDINGS.md for cost.

Everything else in them — per-plate timings, worker states, `delayTime`/
`executionTime`, and the pixel-fidelity records — was measured directly and stands.
