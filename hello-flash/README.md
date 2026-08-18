# hello-flash

The smallest Flash app that deploys to Runpod and answers one request.

**Status: deployed, measured, torn down.** It answered its first request from
cold in **31.387 s**, a warm request in **0.354 s**, and the whole exercise —
four requests and 458 s of endpoint life — cost **$0.0066245833**, read off the
account balance rather than estimated. Full record in
[../FINDINGS.md](../FINDINGS.md).

## What it is for

Not the computation — it just echoes its input. The point was three numbers, and
here they are:

| | Measured |
|---|---:|
| First request from a scaled-to-zero endpoint | **31.387 s** |
| A warm request | **0.354 s** |
| The whole exercise, off the balance | **$0.0066245833** |

Those numbers set expectations for the real work, which is rendering 832×1216
plates on Runpod instead of on one desktop GPU. The lesson that carried furthest
was the third one: the cost had to be read off `clientBalance` minutes later,
because `runpodctl billing serverless` returned `[]` for a charge that
demonstrably happened.

## Running it

```bash
uv tool install --python 3.13 runpod-flash   # 1.19.0 requires Python <3.14
flash login                                  # once; see the note below
cd hello-flash && flash deploy               # from INSIDE this directory
```

**`cd` into this directory first.** Running `flash deploy --app hello-flash` from
the repository root fails before it deploys anything:

```
Failed to load:
  flash-imagegen/app.py: KeyError: 'RUNPOD_REGISTRY_AUTH_ID'
  tools/replay_prompts.py: ModuleNotFoundError: No module named 'jsonschema'
```

`--app` selects which app to deploy but not which files to import: the CLI walks
every `.py` under the working directory first, and one that raises on import
stops the deploy. Neither of those files has anything to do with this app.
Deploying from inside `hello-flash/` scopes the walk and it works.

**The authentication line used to read the API key out of
`~/.runpod/config.toml` and export it into the environment.** That line is gone.
Extracting a plaintext credential into a shell variable puts it in the process
table and the shell history, and it is the same one-liner this project flagged
as a credential-harvesting primitive when it found it in Runpod's own skill
files. Let the tool read its own credential file.

`flash login` is needed even when `runpodctl` is already working, because the two
CLIs do not read the same thing out of the same file. See "Two CLIs, one file,
two formats" below.

Then one request. **`flash deploy` prints the endpoint's base URL when it
finishes** — that is where `<base-url>` below comes from. If the terminal has
scrolled, `flash app get hello-flash` reads it back, and
`runpodctl serverless list` shows the endpoint id:

```bash
curl -s "<base-url>/predict" -H 'content-type: application/json' \
     -H "Authorization: Bearer <your-key>" \
     -d '{"data": {"hello": "runpod"}}'
```

**The path is `/predict`, not `/main/predict`.** An earlier version of this file
said `/main/predict`; it returns `404 {"detail":"Not Found"}`. `flash deploy`
prints the real routes when it finishes — read them off its output rather than
trusting this file.

Better than the curl above, because it never puts your key in a shell:

```bash
python3 ../tools/runpod_http.py "<base-url>/predict" \
    --data '{"data": {"hello": "runpod"}}' --repeat 4
```

That reads `~/.runpod/config.toml` in-process, times each call, and prints the
status and body. Four calls show you the cold start and then the warm ones.

The reply echoes your input back, plus `worker` — the hostname of the machine
that ran it. Send it twice: the same `worker` on the second call is how you know
you measured a warm request rather than a second cold start.

Do not bother reading the `gpu` field. It reports `NVIDIA_VISIBLE_DEVICES`, which
came back as the literal string `void`. That is recorded here because it was
going to be the real render app's only record of which card ran a plate; that app
reads the device name out of ComfyUI's `/system_stats` instead.

## Teardown, and why one command is not enough

```bash
flash app delete hello-flash
runpodctl serverless list                 # ALWAYS. Do not skip this.
runpodctl serverless delete <endpoint-id> # if the list is not empty
runpodctl serverless list                 # confirm it is now []
```

**`flash app delete` reported success and left the endpoint running.** Measured
2026-08-18, on the second deployment of this app:

```
$ flash app delete hello-flash
✓ deleted app hello-flash

$ runpodctl serverless list
[ { "id": "jayf2t4qi40v9r", "name": "hello-flash", "workersMax": 1, ... } ]
```

The app record was deleted. The serverless endpoint behind it was not, and it
was still billable. `runpodctl serverless delete` removed it and the list then
returned `[]`.

So the rule this project already applies to balances applies to teardown too:
**verify by asking, never by a success message.** A checkmark is a claim about
what a command tried to do.

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
