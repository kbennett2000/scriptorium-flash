# ADR 0001 — Which parts of Scriptorium move to Runpod

- **Date:** 2026-08-17
- **Status:** Accepted
- **Context:** Cycle 1

## The app as it stands

Scriptorium turns a public-domain book into an illustrated edition. One process
walks the book through a fixed sequence of stages. Internally that process is
called the bakery, because a run is called a bake; the name carries no meaning
beyond that.

The stages fall into two groups:

- **Text stages.** A language model reads a page and returns structured data:
  which characters are mentioned, what changed in the scene, and what an
  illustration of that page should depict. Roughly one model call per page, plus
  one per selected illustration.
- **Image stages.** An image model turns each of those descriptions into a
  832×1216 plate. Character portraits render at 1024×1024.

Both currently run on one desktop machine with one consumer GPU that has 12 GB
of video memory. Two local HTTP services front the models. The bakery calls
them over the network on localhost.

Two properties of the current design matter here:

1. **It is strictly serial.** One job advances at a time, and within a job one
   unit at a time. This is deliberate, not an oversight: with one GPU, the text
   model and the image model cannot both be resident, so the bakery evicts one
   before running the other. A single worker makes it structurally impossible
   for two GPU stages to overlap.
2. **The two models take turns in video memory.** Each switch costs a reload.

## Decision

**The bakery stays local.** It remains the orchestrator: it owns the job state
machine, the artifacts on disk, the human review gates, and the ordering rules.
It is not being rewritten and it is not moving to Runpod.

Two things move out to Runpod:

1. **Image generation → a Flash app that Kris owns.** Flash is Runpod's
   code-first serverless product: you write Python locally and it executes on
   remote GPUs. The app renders 832×1216 plates using an SDXL-class model — the
   same class of model the local image service runs today, so the output stays
   comparable.
2. **Text stages → a Runpod ready-made hosted endpoint, billed per token.**
   These are Runpod-operated models; nothing to deploy or maintain. Confirming
   which models they offer, and that one of them can do this job, is work for a
   later cycle, not this one.

**The load-bearing change to Scriptorium is one thing:** illustration requests
fan out in parallel instead of waiting for each other. Serial execution was
forced by having one GPU. Once rendering happens on Runpod, that constraint is
gone, and it is the change that turns a platform migration into a visible
difference.

## Why the work splits across two repositories

- **`scriptorium-flash`** — public. The Flash app, the measurement tools, the
  findings, and the AI-assistance log. This is what Runpod receives and grades,
  and it is what the talk cites. It contains nothing that reveals Scriptorium's
  internals beyond what these documents describe.
- **Scriptorium** — private, unchanged for now. It gets one small pull request
  in a later cycle: endpoint configuration, plus the parallel fan-out.

Keeping them apart means the graded artifact is small and readable, and the
working app is not destabilized by an interview exercise.

## What this buys, and what it costs

**Buys:** plates render in parallel rather than in sequence; the two models stop
evicting each other from video memory, because they no longer share a GPU; and
capacity stops being fixed at whatever one desktop can do.

**Costs:** money per render instead of electricity; a cold start on the first
request after an idle period; and image bytes crossing the public internet
instead of localhost.

Whether the trade is worth it is an empirical question, which is the point of
measuring the current system first. Baseline numbers and Runpod numbers both go
in [FINDINGS.md](../../FINDINGS.md).

## Consequences

- The bakery's serial design becomes a per-stage choice rather than a global
  invariant. The GPU-exclusivity rule that justified it only applies to stages
  still running on the local GPU.
- Scriptorium gains a dependency on a network service it does not control.
  Failure handling for that is a later cycle's problem, and it is a real one.
- The comparison is only meaningful if both sides render the same book at the
  same size. The standard comparison story is pinned in
  [FINDINGS.md](../../FINDINGS.md).
