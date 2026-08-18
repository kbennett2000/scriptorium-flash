# Getting started

For someone who is not me, with their own Runpod account and about $5 of credit.

This repo is a measurement record, not a product. Some of it you can run in a
fresh clone; some of it reads a private repository and will not run anywhere but
my desk. This page says plainly which is which, because discovering that halfway
through is worse than being told.

Three paths, cheapest first:

| Path | Needs | Costs |
|---|---|---|
| **A — read the numbers** | nothing. No account, no network. | $0.00 |
| **B — deploy `hello-flash`** | a Runpod account with credit | $0.02–$0.03 |
| **C — build the renderer** | a Runpod account, ~11 GB of downloads, a private registry | build time, plus whatever you render |

---

## Path A — read the numbers, and check them

No account needed. From a fresh clone:

```bash
git clone https://github.com/kbennett2000/scriptorium-flash
cd scriptorium-flash
python3 tools/check_numbers.py
```

That reads [docs/NUMBERS.md](docs/NUMBERS.md) — the one-page card for the talk —
and fails if any number on it does not appear verbatim in
[FINDINGS.md](FINDINGS.md). It needs only Python 3 from the standard library.

It is also the fastest way to understand what this project is: the card is one
page and every figure on it is checkable.

Reading order for a reviewer:

1. [README.md](README.md) — what was built and what it measured.
2. [docs/NUMBERS.md](docs/NUMBERS.md) — the figures, on one page.
3. [FINDINGS.md](FINDINGS.md) — every number, dated, sourced, with the
   corrections left in.
4. [AI-ASSIST.md](AI-ASSIST.md) — how Runpod's own AI tooling performed.
5. [docs/adr/](docs/adr/) — the two architecture decisions.
6. [docs/DEMO-RUNBOOK.md](docs/DEMO-RUNBOOK.md) — the live demo, minute by
   minute.

---

## Before Paths B and C: credentials

**Nothing in this repo takes an `--api-key` flag, and nothing reads
`RUNPOD_API_KEY` from the environment.** That is deliberate.
[tools/runpod_http.py](tools/runpod_http.py) opens `~/.runpod/config.toml` inside
the process, and the value never leaves it — there is no way to make any tool
here print your key, and anything key-shaped is redacted on its way to stdout, to
a saved response file, or into a traceback.

So do **not** use the one-liner that Runpod's own tooling and documentation reach
for:

```bash
# Don't. This puts a long-lived plaintext credential in a shell variable, the
# process table and your shell history, and all three outlive the command.
KEY="$(grep '^apikey' ~/.runpod/config.toml | sed ...)"
```

Let each tool read its own credential file.

### You need two logins, not one, and this is the trap

`runpodctl` and `flash` both keep credentials in `~/.runpod/config.toml` and read
**different keys out of it**. Runpod's guidance says one login serves both. It
does not.

- `runpodctl` writes and reads a **top-level `apikey`**.
- `flash` goes through `runpod-python`'s `get_credentials(profile="default")`,
  which returns nothing unless there is a **`[default]` table containing
  `api_key`**.

Given only the first, `runpodctl user` works and every `flash` subcommand dies
with `RunpodAPIKeyError: No RunPod API key found` — an error that suggests the
environment variable and `.env` as remedies, and never mentions that the file it
just read was the wrong shape. That is how people end up reaching for the
one-liner above.

**The fix is to run `flash login` once.** It appends the `[default]` table and
preserves runpodctl's existing entry, because it parses the file with `tomlkit`
and only assigns its own profile. After that both CLIs work from one file and
neither needs anything in the environment.

Filed as [runpod/flash#363](https://github.com/runpod/flash/issues/363).

### Install

```bash
# The Flash CLI. 1.19.0 requires Python <3.14, hence the explicit --python.
uv tool install --python 3.13 runpod-flash

# The other CLI, from runpod.io/console — needed for billing, endpoint listing
# and teardown, none of which flash can do.
runpodctl user            # confirms it can read your key

flash login               # once. See above for why this is separate.
```

Versions this was written against: `runpodctl 2.9.0-c094cac`, `Runpod Flash CLI
v1.19.0`.

---

## Path B — deploy `hello-flash` end to end

The smallest Flash app that deploys and answers one request. It echoes its input;
the point is three numbers, not the computation.

```bash
cd scriptorium-flash
flash deploy --app hello-flash
```

**`flash deploy` prints the endpoint's base URL when it finishes.** That is where
`<base-url>` comes from below. If the terminal has scrolled, read it back with
`flash app get hello-flash`, or `flash env get production --app hello-flash` for
the environment detail — note that `env get` takes the environment name as a
positional argument, not a flag. `runpodctl serverless list` shows the endpoint
id it was built from.

```bash
curl -s "<base-url>/main/predict" -H 'content-type: application/json' \
     -d '{"data": {"hello": "runpod"}}'
```

Send it twice. The reply carries `worker` — the hostname of the machine that ran
it — and the same hostname on the second call is how you know the second request
was warm rather than a second cold start.

What I measured, so you know what to expect:

| | |
|---|---:|
| First request, from zero workers | **31.387 s** |
| Warm request | **0.354 s** |
| Whole exercise: 4 requests, 458 s of endpoint life | **$0.0066245833** |

Then tear it down **by name**:

```bash
flash app delete hello-flash
runpodctl serverless list          # confirm. Never trust a delete's exit code.
```

**Never run `flash undeploy --all`.** It is account-wide and will remove
endpoints this project did not create.

### Three things that cost me time

**`flash dev` costs money.** It presents as a local development server, but the
decorated functions execute on remote workers. Its documentation never mentions
billing. Treat it exactly like `flash deploy`.

**Only the function body ships under `flash dev`.** Imports and constants a
remote function uses must be written *inside* it. `flash deploy` imports the
whole module, so module-level names work there — meaning code can work deployed
and fail in development, which is a confusing direction for a bug to travel.

**`idle_timeout` is in seconds**, and the Flash SDK's defaults differ from the
platform's own defaults for the same settings. A worker stays alive that long
after each request, and **that time is billed** — it was the dominant cost of the
headline bake.

More in [hello-flash/README.md](hello-flash/README.md).

---

## Path C — build the renderer, up to the weights caveat

[flash-imagegen/](flash-imagegen/) is the real thing: a container running ComfyUI
that renders one 832×1216 plate per request, reproducing the home render stack
exactly enough that the comparison means something (**0 differing pixels** of
1,011,712, on all nine plates).

You can read all of it, and build it. **You cannot pull my image**, and the
reason is a licence.

### The weights, stated plainly

> **This repository never distributes model weights. None is in it, none may be
> committed to it, and none may be baked into any publicly pullable image.**
>
> The renderer needs five files, about 11 GB. They are downloaded at container
> build time from their own sources and verified against the byte counts and
> SHA256 digests in [flash-imagegen/MODELS.md](flash-imagegen/MODELS.md) — the
> build fails closed on any mismatch.
>
> **You must fetch your own copies.** The reason is the style LoRA:
> **ClassipeintXL v2.1 by eldritchadam** is licensed for private, free,
> single-user use, and its terms **forbid redistribution** and **prohibit running
> it on any service that monetizes image generation**. That is why
> `ghcr.io/kbennett2000/scriptorium-imagegen` is private and will stay private,
> why the endpoint here is single-user, and why you must build and push to **your
> own private registry**.
>
> Fetch the LoRA from the creator's own repository, `EldritchAdam/
> SDXL_Eldritch_LoRAs` — not from the third-party re-uploads other installers
> fall back to. A mirror cannot grant rights the original licence withholds.
>
> Read [flash-imagegen/MODELS.md](flash-imagegen/MODELS.md) in full before you
> build or publish anything. It also documents two traps in the file list that
> will silently change your output if you get them wrong.

None of the five files is gated and none needs a token, so the download itself
needs no credentials.

### Check what you have, before downloading 11 GB

```bash
cd flash-imagegen
python3 fetch_models.py --check-only --dest /path/to/your/comfyui/models
```

Free, and it is the difference between a short build and an 11 GB download. If
you already run ComfyUI locally, point `--dest` at its models directory.

### Build

```bash
# --build-context replaces the empty `modelcache` stage with a local ComfyUI
# models directory. Without it, every file is fetched from HuggingFace instead.
# Point it at YOUR models directory.
docker build \
  --build-context modelcache=/path/to/your/comfyui/models \
  -t <your-registry>/scriptorium-imagegen:sdxl-base-1.0-py31115 \
  flash-imagegen/
```

Then boot it locally **before** it reaches a paid worker. That step caught a
segfault in twenty local minutes instead of as a cold start in a crash loop —
see [flash-imagegen/README.md](flash-imagegen/README.md) for the exact command
and the `--runtime=nvidia` note.

### Deploying it needs two things this repo cannot give you

1. **`RUNPOD_REGISTRY_AUTH_ID`** — a registry credential, created in the Runpod
   console. Create it there rather than with
   `runpodctl registry create --password <string>`, which would put a registry
   password in your process table and shell history. The id is not a secret;
   [flash-imagegen/app.py](flash-imagegen/app.py) reads it from the environment
   so a missing one fails loudly rather than silently pulling nothing.

   The `containerRegistryAuthId` field this uses is undocumented — absent from
   Runpod's custom-image docs and from the Flash skill's `PodTemplate` reference.
   It was found by reading the SDK. Filed as
   [runpod/docs#800](https://github.com/runpod/docs/issues/800).

2. **`flash deploy` will not provision it.** A client-mode endpoint — one that
   supplies `image=` rather than shipping a Python function body — provisions on
   *first use*, inside `Endpoint._ensure_endpoint_ready()`. `flash deploy` builds
   an artifact, creates the app, reports "deployed to production", writes a
   manifest containing `"resources": {}`, and creates nothing. `flash env get`
   then says "no resources". Nothing warns.

   [tools/provision_client_endpoint.py](tools/provision_client_endpoint.py) calls
   that path directly so provisioning is a separate, timed step:

   ```bash
   RUNPOD_REGISTRY_AUTH_ID=<id> python3 tools/provision_client_endpoint.py \
       --app-dir flash-imagegen
   runpodctl serverless list      # ALWAYS. See below.
   ```

   **Always verify with `serverless list`.** The Flash SDK caches provisioned
   resources in a `.flash/resources.pkl` written relative to the *current working
   directory*, not `--app-dir`. Run it from the wrong directory with a stale
   cache and it will print a plausible endpoint id and create nothing at all,
   with no error. The tell is timing: a genuine provision takes about 3 s, a
   cache-satisfied no-op about 0.4 s. `find . -path '*/.flash/resources.pkl'
   -delete` clears them.

---

## What you cannot run, and why

These read `~/scriptorium-data` or import from Scriptorium's server — a separate,
private repository — or drive the local bakery. They are here because they are
how the numbers were produced and you should be able to audit them, not because
they will run for you.

| Tool | Needs |
|---|---|
| `run_baseline.py`, `headline_bake.sh`, `showcase_bake.sh` | the bakery on `localhost:8720`, plus a systemd user unit |
| `bake_timing.py` | the systemd journal of three local services |
| `verify_ingest.py`, `replay_prompts.py`, `prune_cast.py` | `~/scriptorium-data` and the server's Python package |
| `cold_load_plates.py`, `remediate_cold_plates.py` | a book's rendered artifacts, and the bakery's regen route |
| `render_bench.py` | home's stored plates, to compare against |
| `export_static_reader.py`, `serve_static_mirror.py` | the server's `resolve_reader_files`, and a built reader bundle |
| `verify_reader.mjs` | Playwright, imported from the reader repo by absolute path |
| `public_endpoint_probe.py` | the text-transform service's prompt-building source |

**What `localhost:8720` is:** Scriptorium's own orchestrator — the "bakery". It
owns the job state machine, the artifacts on disk and the human review gates. It
is not part of this repo and is not being distributed. [ADR
0001](docs/adr/0001-architecture.md) explains why the split is drawn there.

**A note on ADR numbers.** This repo contains ADRs 0001 and 0002. References
throughout the code and findings to ADR-0007, ADR-0028, ADR-0036, ADR-0037 and
ADR-0038 are to Scriptorium's and imagegen-service's own decision records, in
those private repos. They are cited for provenance; you cannot open them, and
nothing here depends on your being able to.

Everything in `tools/` is indexed in [tools/README.md](tools/README.md) with a
"runs anywhere?" column.

---

## Costs, before you run anything

Rates, from runpod.io/pricing: **$1.10/hr** (RTX 4090), **$0.69/hr** (24 GB
tier), **$0.58/hr** (16 GB tier).

Three things worth knowing before you spend:

- **An endpoint at zero workers costs nothing.** Measured at exactly $0.00 across
  four separate windows, including one of nearly three hours. Scale-to-zero is
  what makes this cheap.
- **A network volume does not.** It bills whether or not a worker runs — roughly
  $7/month for the 100 GB default. This project puts the weights in the image
  instead, and that decision is why the idle number is zero.
- **Serverless spend has to be read off the account balance**, and the balance
  lags the charge by minutes. `runpodctl billing serverless` returned `[]` for a
  charge that demonstrably happened. [tools/settle_balance.py](tools/settle_balance.py)
  waits for six consecutive identical reads 45 s apart, because a stable balance
  is not a settled one — that mistake produced a wrong published figure here
  once, and the tool caught a late posting the first time it ran.
