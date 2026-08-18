# scriptorium-flash

Moving the AI steps of a working app onto Runpod, and writing down what it
actually cost and how long it actually took.

Status: **in progress.** Cycle 3 of several — the first cycle with real Runpod numbers in it.

## What this is

I have an app called Scriptorium. It takes a public-domain book and turns it
into an illustrated edition. It does that with two kinds of AI work:

- **Text steps** — a language model reads each page and decides who is in it,
  what is happening, and what an illustration of it should look like.
- **Image steps** — an image model turns each of those descriptions into a
  832×1216 plate.

Today both run on one desktop machine with one consumer GPU. Every plate waits
for the one before it. This repo is the record of moving that work to Runpod and
measuring the difference.

It exists because of a Runpod interview assignment: build something real on the
platform and talk about it for 20 minutes. The talk cites this repo.

## What's in here

| File | What it holds |
|---|---|
| [FINDINGS.md](FINDINGS.md) | **Every number this project produces.** Timings, costs, cold starts. Dated. |
| [AI-ASSIST.md](AI-ASSIST.md) | How Runpod's own AI tooling performed — what it got right, what it got wrong. |
| [docs/adr/](docs/adr/) | Architecture decision records. Start at [0001](docs/adr/0001-architecture.md). |
| `hello-flash/` | The smallest Flash app that deploys and answers one request. Deployed and measured. |
| [flash-imagegen/](flash-imagegen/) | The production plate renderer. Built, pushed private, and measured on two Runpod GPU tiers. |
| `tools/` | Measurement scripts, and the small HTTP client that reads its own credential file rather than exporting a key. |
| `runs/` | The raw evidence behind the numbers — timings, model responses, rendered plates. |

## The one rule about numbers

`FINDINGS.md` is the only place a measured number is written down. The README,
the slides, and the ADRs cite it. Nothing gets retyped by hand, because retyped
numbers drift.

## Scope

Scriptorium itself is a separate, private repo. It is not being rewritten. It
keeps orchestrating the work locally and will get one small change in a later
cycle: pointing at Runpod endpoints, and asking for illustrations in parallel
instead of one at a time. See [ADR 0001](docs/adr/0001-architecture.md) for why
the split is drawn there.

## License

MIT. See [LICENSE](LICENSE).
