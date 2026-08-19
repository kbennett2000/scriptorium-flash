![scriptorium-flash: one illustrated book end to end took 388.63 s on a home
desktop GPU and 325.24 s with plates rendered on a pinned Runpod RTX 4090.
Total spend $1.1320333838, reconciled to ten decimal places. Zero differing
pixels of 1,011,712 against home. $0.00 idle, measured four
times.](docs/img/banner.png)

# scriptorium-flash

Moving the AI steps of a working app onto Runpod, and writing down what it
actually cost and how long it actually took.

**Status: finished.** Six cycles, every number measured rather than estimated,
total Runpod spend **$1.1320333838**.

## What this is

I have an app called Scriptorium. It takes a public-domain book and turns it into
an illustrated edition. It does that with two kinds of AI work:

- **Text steps:** a language model reads each page and decides who is in it,
  what is happening, and what an illustration of it should look like.
- **Image steps:** an image model turns each of those descriptions into a
  832×1216 plate.

Both ran on one desktop machine with one consumer GPU, strictly serially: every
plate waited for the one before it. This repo is the record of moving the image
steps to Runpod and measuring the difference.

It exists because of a Runpod interview assignment: build something real on the
platform and talk about it for 20 minutes. The talk cites this repo.

**You can read the result**: <https://scriptorium-reader.vercel.app>. *Treasure
Island*, 91 illustrations, rendered on Runpod. It is a static export of the real
reader, so reading, search, the cast page and every illustration work; highlights
and reading position do not persist, because saving them needs a PUT and there is
no server behind it.

New here? Start with [GETTING-STARTED.md](GETTING-STARTED.md).

## What it measured

Every figure below is in [docs/NUMBERS.md](docs/NUMBERS.md), which cites
[FINDINGS.md](FINDINGS.md) line by line, and `tools/check_numbers.py` fails if
one of them is not in the log.

**It got faster, and the comparison is honest.** The same book through the same
pipeline took **388.63 s** at home and **325.24 s** with plates rendered on
Runpod, **1.195× end to end**. The faster run also did more work: 18 images
against home's 16. Ship the caveat with the number, though: the home baseline was
measured on an otherwise-quiet machine, so it is home's best case, not its
typical one.

**Most of the win is not the fan-out.** The rendering bucket fell from 123.34 s
to 59.74 s, and of that ~65 s saved, **72% is the faster card and 28% is
overlapping requests**. The text steps stayed at home, so text and orchestration
are **74%** of the run and Amdahl's floor is **251.5 s**. No amount of extra
render workers takes this architecture below that. That ceiling is the most
useful thing the project found.

**It is very cheap, and idle is free.** A warm plate costs **$0.001742** on a
pinned RTX 4090. The whole project (six cycles, two full books, two GPU tiers,
a container built and pushed, 26 hosted text-model calls) cost
**$1.1320333838**, reconciled against the account balance to ten decimal places.
An endpoint with no traffic billed **$0.00**, measured four separate times.

**The renders are the same computation, not a similar one.** The container runs
the same checkpoint, LoRA, IP-Adapter, sampler and step count as home, and
`verify_port.py` proves it: **0 differing pixels** of **1,011,712**, on all nine
plates. A speed comparison between two different computations would not have
meant anything.

**The finding nobody expected: isolation beat both.** The home baseline assumed
an uncontended GPU. Sharing that card with another workload pushed one text step
from 2.523 s to **26–155 s**, because the model was evicted to CPU. That is
**37×** on the text steps, against **1.59×** on the renders. The rented GPU is not
competing with a browser, and on this evidence that is worth more than either the
faster silicon or the fan-out.

## Honest status

| Done | |
|---|---|
| `hello-flash` | Deployed, measured, torn down. 31.387 s cold, 0.354 s warm. |
| `flash-imagegen` | Built, pushed to a private registry, deployed and measured on two GPU tiers. |
| The headline bake | 18 plates, end to end, 325.24 s. |
| The showcase book | *Treasure Island*, 91 renders, published and verified in a real browser. |

| Recorded, deliberately not done | Why |
|---|---|
| **The container diet** | **4.94 GB / 133.2 s** of the image is removable, which would take the cold start from ~490 s to **~357 s**. Not done *by decision*: a warm-up render removes the cold start entirely and costs nothing, so the diet buys a shorter version of a problem that is already solved. |
| **Text steps on hosted endpoints** | Tried and blocked, not skipped. **26 calls across two models produced 0 clean parses** of the structured output the pipeline needs. That is a nameable blocker with a filed issue, not an omission. |
| **The retention metric** | The showcase book's ingest scored **98.80%** against a pre-registered **99.5%** threshold and failed it. The book was baked anyway, and that waiver is recorded as one. The audit then found the threshold was wrong: the shortfall is a table of contents and front matter, not one word of narrative. But the metric was left as it was. Moving a number in the middle of a book it had just failed is indistinguishable from moving a goalpost. |

## What's in here

| File | What it holds |
|---|---|
| [GETTING-STARTED.md](GETTING-STARTED.md) | Clone to running, for someone who is not me. What you can reproduce, and what you cannot. |
| [FINDINGS.md](FINDINGS.md) | **Every number this project produces.** Timings, costs, cold starts, and the corrections. Dated, newest first. |
| [docs/NUMBERS.md](docs/NUMBERS.md) | The one-page card for the talk. Every figure cites FINDINGS.md; `tools/check_numbers.py` fails if one does not. |
| [docs/DEMO-RUNBOOK.md](docs/DEMO-RUNBOOK.md) | The live demo, minute by minute, with a recovery line for every failure this project actually hit. |
| [AI-ASSIST.md](AI-ASSIST.md) | How Runpod's own AI tooling performed: what it got right, what it got wrong, and the seven issues that came out of it. |
| [docs/adr/](docs/adr/) | Architecture decisions: [0001](docs/adr/0001-architecture.md) on what moves, [0002](docs/adr/0002-reproducing-the-home-render-stack.md) on reproducing the render stack exactly. |
| [hello-flash/](hello-flash/) | The smallest Flash app that deploys and answers one request. |
| [flash-imagegen/](flash-imagegen/) | The production plate renderer, and [MODELS.md](flash-imagegen/MODELS.md), listing the five model files, their hashes, and the terms they come with. |
| [tools/](tools/) | Nineteen measurement scripts, indexed in [tools/README.md](tools/README.md). Including the HTTP client that reads its own credential file rather than exporting a key. |
| [runs/](runs/) | The raw evidence behind the numbers, indexed in [runs/README.md](runs/README.md), including two artifacts that carry their own errors on purpose. |

## The one rule about numbers

`FINDINGS.md` is the only place a measured number is written down. The README,
the card, the runbook and the ADRs cite it. Nothing gets retyped by hand, because
retyped numbers drift.

That rule is mechanical, not remembered:

```bash
python3 tools/check_numbers.py --card README.md GETTING-STARTED.md \
  docs/NUMBERS.md docs/DEMO-RUNBOOK.md hello-flash/README.md \
  flash-imagegen/README.md docs/adr/*.md runs/README.md
```

It extracts every numeric literal from each document and fails if one does not
appear verbatim in `FINDINGS.md`. Not "is derivable from." Appears. If a figure
needs arithmetic, the arithmetic goes in the log first, where it can be checked
against the artifact it came from. It needs no Runpod account and no network.

## Scope

Scriptorium itself is a separate, private repo, and it was not rewritten. It
still orchestrates the work locally; the one change it needed was to point at a
Runpod endpoint and ask for illustrations in parallel instead of one at a time.
See [ADR 0001](docs/adr/0001-architecture.md) for why the split is drawn there.

The consequence for a reader: some tools here read that private repo's data and
cannot run in a fresh clone. Which ones, and what you can run instead, is in
[GETTING-STARTED.md](GETTING-STARTED.md).

## License

The **code** is MIT. See [LICENSE](LICENSE). Copyright Twelve Rocks LLC, which
is Kris Bennett.

**No model weights are in this repository, and none may be added to it.** The
five files the renderer needs are downloaded at build time from their own
sources, under their own licences, one of which permits private, free,
single-user use and forbids redistribution. Read
[flash-imagegen/MODELS.md](flash-imagegen/MODELS.md) before building or
publishing anything from here.
