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
