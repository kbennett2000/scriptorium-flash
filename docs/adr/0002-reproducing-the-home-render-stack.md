# ADR 0002 — Reproducing the home render stack on Runpod

- **Date:** 2026-08-17
- **Status:** Accepted
- **Context:** Cycle 2

## The problem

Cycle 1 measured the home bakery and got 7.615 s for a warm 832×1216 plate.
Cycle 2 re-measured on a different book and got 7.595 s. The plan was to stand a
Flash app next to that number.

The number is not what it looks like. The home renders are not plain SDXL. On the
`oil-painting` style — which is what the standard comparison story bakes with —
imagegen-service also applies the ClassipeintXL2.1 LoRA at strength 0.8, and on
plates that have a character portrait it applies IP-Adapter face conditioning at
weight 0.5. Seven of the nine plates in the Sleepy Hollow bake used a reference.

So a Runpod app running base SDXL would be a *different computation*, and printing
its render time beside 7.6 s would be comparing two unlike things while presenting
them as alike.

## Decision

**Reproduce the whole stack.** The Runpod worker runs the same checkpoint, the
same VAE, the same LoRA at the same strength, the same IP-Adapter models at the
same weight and start point, the same sampler, scheduler, step count, CFG and
size.

**Run it under ComfyUI, not diffusers.** ComfyUI is what home runs, and
"euler/normal at 25 steps" is not bit-identical across implementations. A
reimplementation would be a third thing, comparable to neither side.

**Prove the reproduction rather than asserting it.** `verify_port.py` rebuilds a
plate the home bakery already rendered, from that plate's own recorded seed and
prompts, and compares pixel by pixel against the stored output. Both paths pass
with zero differing pixels: LoRA-only, and LoRA plus IP-Adapter.

This was not ceremony. The first version of the port failed it, changing 1,010,483
of 1,011,712 pixels, because it *set* the negative prompt where imagegen-service
*appends* it to a baseline already in the template. The settings table was correct
and the render was wrong. Nothing short of comparing output would have caught it.

## Alternatives rejected

**Base SDXL only, compared against 7.6 s with a footnote.** Cheapest to build and
the least honest. The footnote does not repair a headline that compares different
computations.

**Base SDXL on both sides, re-measuring home with the LoRA and IP-Adapter
disabled.** Genuinely like-for-like and free to arrange, and it was the
recommendation before Kris chose otherwise. Its cost is that the number then
describes a configuration the production pipeline never runs.

**Mounting the weights from a network volume.** Rejected on cost, not on
correctness: a network volume bills continuously whether or not a worker runs,
roughly $7/month for the 100GB default, which would have destroyed the
$0-when-idle result the previous decision rests on. The weights go in the image.

## Consequences

**The container is large and private.** About 11GB of weights, fetched at build
time and hash-verified. It cannot be pushed to a public registry, because the
style LoRA may not be redistributed. That means a private registry and its
credentials become a deployment prerequisite.

**Cold start is dominated by weight loading.** Model *download* time is not billed
by Runpod, but loading into VRAM is. The handler reports `model_load_s` separately
from `render_s` so the two are never conflated in the numbers.

**The style LoRA constrains what this endpoint may ever become.** Its licence
grants `RentCivit` but withholds `Rent` — "run on services that generate images
for money" — and its addendum says "do not use the Model on any service that
monetizes image generation". A private, free, single-user endpoint does not
monetize generation and is permitted. **Monetizing this endpoint, or opening it to
other users, is not, and would need written permission from eldritchadam.** That
sentence is here so a later cycle cannot walk into it unaware. The LoRA is also
never fused into a checkpoint, because sharing merges is prohibited outright.

**Pinning is now load-bearing.** ComfyUI 0.27.0 at `6cc8144`, IPAdapter_plus at
`a0f451a`, torch 2.11.0+cu128. Bumping any of them can move the pixels, at which
point the pixel-equality check stops passing and the comparison needs re-basing
rather than the check being relaxed.

## The measurement this enables

Two GPU tiers, same protocol, same prompts, same seeds: `AMPERE_24` at $0.69/hr
and `ADA_24` at $1.10/hr, each behind its own spend gate. Cold start, warm render
per plate over six renders — matching the home median's n=6 — and cost per plate,
recorded in [FINDINGS.md](../../FINDINGS.md) beside the home number.
