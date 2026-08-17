# hello-flash

The smallest Flash app that deploys to Runpod and answers one request.

**Status: written, not deployed.** No Runpod API key exists on the build
machine, so nothing has been provisioned and nothing has been spent. The
measured result goes in [../FINDINGS.md](../FINDINGS.md) once it runs.

## What it is for

Not the computation — it just echoes its input. The point is three numbers:

1. How long a scaled-to-zero endpoint takes to answer its first request.
2. How long a warm request takes.
3. What that costs, checked against the billing page rather than estimated.

Those numbers set expectations for the real work, which is rendering 832×1216
plates on Runpod instead of on one desktop GPU.

## Running it

```bash
uv tool install --python 3.13 runpod-flash   # 1.19.0 requires Python <3.14
flash login                                  # once; see the note below
flash deploy --app hello-flash
```

**The authentication line used to read the API key out of
`~/.runpod/config.toml` and export it into the environment.** That line is gone.
Extracting a plaintext credential into a shell variable puts it in the process
table and the shell history, and it is the same one-liner this project flagged
as a credential-harvesting primitive when it found it in Runpod's own skill
files. Let the tool read its own credential file.

`flash login` is needed even when `runpodctl` is already working, because the two
CLIs do not read the same thing out of the same file. See "Two CLIs, one file,
two formats" below.

Then one request:

```bash
curl -s "$ENDPOINT/main/predict" -H 'content-type: application/json' \
     -d '{"data": {"hello": "runpod"}}'
```

Teardown, by name:

```bash
flash app delete hello-flash
```

Never `flash undeploy --all` — that is account-wide and would remove endpoints
this project did not create.

## Costs, before you run anything

`GpuGroup.AMPERE_16` is the 16 GB tier — A4000-class — listed at **$0.58/hr** on
runpod.io/pricing, which is $0.000161 per second.

Runpod's serverless documentation says billing covers three phases: container
start and model load, execution, and the idle-timeout tail after a request
finishes. With `workers=(0, 1)` and `idle_timeout=60`, one cold request plus its
idle tail keeps a worker alive roughly 2–3 minutes, so **$0.02–$0.03 per test
run**.

**`flash dev` also costs money.** It presents as a local development server, but
the decorated functions execute on remote workers. Its skill documentation never
mentions billing. Treat it exactly like `flash deploy`.

## Two things that cost time to learn

**Only the function body ships under `flash dev`.** Imports and constants used by
a remote function must be written inside it. `flash deploy` imports the whole
module, so module-level names happen to work there — meaning code can work
deployed and fail in development, which is a confusing direction for a bug to
travel. Everything in `main.py` is written inside the function bodies.

**`idle_timeout` is in seconds**, and the Flash SDK's defaults differ from the
Runpod platform's own defaults for the same settings.

## Two CLIs, one file, two formats

`runpodctl` and `flash` both keep credentials in `~/.runpod/config.toml`, and
Runpod's own guidance says one login serves both. It does not. They read
different keys out of it, so a file written by one is invisible to the other.

`runpodctl` writes and reads a **top-level `apikey`**:

```toml
apikey = '...'
```

`flash` goes through `runpod-python`'s `get_credentials(profile="default")`,
which returns nothing unless there is a **`[default]` table containing
`api_key`**:

```toml
[default]
api_key = "..."
```

Given only the first form, `runpodctl user` works and every `flash` subcommand
dies with `RunpodAPIKeyError: No RunPod API key found` — an error that names the
environment variable and `.env` as remedies and never mentions that the file it
just read was in the wrong shape. Which is how you end up reaching for the
key-extraction one-liner.

The fix is `flash login` once. It appends the `[default]` table and **preserves
the existing top-level `apikey`**, because `set_credentials` parses the file with
`tomlkit` and only assigns its own profile. After that both CLIs work from one
file, and neither needs the key in the environment.

Version this was true of: `runpodctl 2.9.0-c094cac`, `Runpod Flash CLI v1.19.0`.
