# tools/

Measurement scripts. Every one has a docstring that explains *why* it exists —
usually because something was measured wrong first. This page is the index, so
you do not have to open all twenty-one to find the one you want.

**Runs anywhere?** means: does it work in a fresh clone with only a Runpod
account? A **no** means it reads `~/scriptorium-data` or imports from
Scriptorium's server — a separate private repository — or drives the local
bakery on `localhost:8720`. Those are not part of this repo and are not
distributable. See [../GETTING-STARTED.md](../GETTING-STARTED.md).

## The credential boundary

| Tool | Runs anywhere? | |
|---|---|---|
| `runpod_http.py` | **yes** | Make authenticated Runpod HTTP calls without ever handling the key in a shell. |

Everything below that talks to Runpod goes through it. It opens
`~/.runpod/config.toml` inside the process and never yields the key: there is no
`--api-key` flag, no environment variable is read, and anything key-shaped is
redacted on its way to stdout, to a saved response, or into a traceback. Read its
docstring before adding a tool that needs auth.

## Endpoint lifecycle

| Tool | Runs anywhere? | |
|---|---|---|
| `endpoint_id.py` | **yes** | Resolve the endpoint id from `runpodctl`, so no command in the runbook has to be edited before it is pasted. Refuses to guess when there are zero or several. |
| `provision_client_endpoint.py` | **yes** | Provision a Flash client-mode (`image=`) Endpoint and print its id. `flash deploy` does not do this and does not say so. |
| `prewarm.py` | **yes** | Bring every worker on an endpoint to a warm, model-resident state — and report honestly when it only managed some of them. |
| `settle_balance.py` | **yes** | Read the account balance until it stops moving, and say so only when it has. |

## Measurement

| Tool | Runs anywhere? | |
|---|---|---|
| `check_numbers.py` | **yes** | Refuse to let a number onto the card that is not in the log. Free, offline, and the fastest way to see what this repo is about. |
| `image_diet.py` | **yes** | Cost out a container-image diet in the only unit that matters: bytes pulled. |
| `render_bench.py` | no | Measure plate renders on a Runpod serverless endpoint against the home baseline. Needs the home plates to compare against. |
| `bake_timing.py` | no | Attribute one Scriptorium bake's wall-clock time to where it actually went. Reads the systemd journal. |
| `run_baseline.py` | no | Drive one Scriptorium bake end to end and record exactly when things happened. |
| `verify_ingest.py` | no | Check an ingested book against its Project Gutenberg source before any GPU time. |
| `replay_prompts.py` | no | Re-derive every `pg-41` plate's request strings with today's code. |
| `public_endpoint_probe.py` | no | Ask a Runpod hosted text model to do a real Scriptorium job, and count the parses. |

## Fidelity

| Tool | Runs anywhere? | |
|---|---|---|
| `cold_load_plates.py` | no | Find the plates a worker rendered as its first render after a model load. Those do not match a warm render. |
| `remediate_cold_plates.py` | no | Re-render every cold-load image against a warm worker, before the book ships. Must run **before** the endpoint is torn down. |
| `prune_cast.py` | no | Fold duplicate cast entries into one character, at the cast review gate. |

## Publishing the showcase book

| Tool | Runs anywhere? | |
|---|---|---|
| `export_static_reader.py` | no | Freeze a published Scriptorium book into a static site the real reader can read. |
| `serve_static_mirror.py` | no | Serve an exported static mirror the way Vercel will, so it can be checked first. |
| `verify_reader.mjs` | no | Drive the deployed reader in real Chromium — profile, shelf, checkout, page turns, an illustrated page — failing on any console error or failed request. Imports Playwright from the reader repo. |

## The two bake scripts

`headline_bake.sh` and `showcase_bake.sh` run a whole measured bake end to end:
point the bakery at Runpod, clear the book, pre-warm, bake, take the live-demo
render, tear down, revert, attribute the time. Neither runs outside this machine
— they write a systemd drop-in and drive `localhost:8720`.

Both print `done -- balance still needs to settle before any cost is recorded`,
because they cannot know what they spent. `settle_balance.py` is the next step,
always.

Two things to know before running either:

- **`OUT` is overridable and should be overridden** for anything that is not the
  original run. The default paths hold committed evidence.
- **`KEEP_ENDPOINT=1`** skips the teardown step, for when the endpoint is wanted
  afterwards — a rehearsal, or a demo.
