# AI assistance log

A running record of how Runpod's own AI tooling performs on this project: their
agent skills now, their MCP server in a later supervised session. What it got
right, what it got wrong, and the moments worth quoting verbatim.

This is the talk's AI-disclosure material. It is also the honest part — a vendor
demo that only reports the parts that worked is not worth 20 minutes of anyone's
time.

Two other things get logged here:

- **Friction**, as it happens. Not summarized afterward.
- **Draft issue text** for genuine Runpod bugs or documentation gaps, with
  reproduction steps. Nothing is filed on Runpod's repositories without Kris's
  approval first.

Separately: this repo is built with Claude Code (Anthropic's coding agent). That
is disclosed but not the subject — the subject is Runpod's tooling.

Entries below, newest first.

---

## 2026-08-17 — Getting a private image onto Runpod

Everything needed to deploy a private container image exists. None of it is
written down together, and one essential field is not written down at all.

### The field that makes it work is undocumented

A private image needs Runpod to hold a registry credential, and the endpoint
needs to reference it. `docs.runpod.io/flash/custom-docker-images` says only:

> Configure Docker registry authentication in Runpod console for private images.

It never says how the endpoint picks that credential up. The flash skill's
`reference/api.md` documents `PodTemplate` with four fields —
`containerDiskInGb`, `dockerArgs`, `ports`, `startScript` — and none of them is
it.

The answer is `PodTemplate(containerRegistryAuthId=...)`. It exists at
`runpod_flash/core/resources/template.py:25` and is threaded into the deploy
manifest at `cli/commands/build_utils/manifest.py:273-276`. It works. It is
documented in neither the docs nor the skill, and was found by reading the SDK.

This is a **draft issue**, unfiled, pending Kris's approval:

> **Title:** `PodTemplate.containerRegistryAuthId` is required for private
> images and is documented nowhere
>
> `docs.runpod.io/flash/custom-docker-images` tells the reader to "configure
> Docker registry authentication in Runpod console for private images" but never
> states how a Flash endpoint references the resulting credential. The
> `PodTemplate` example on that page shows only `containerDiskInGb`.
>
> The mechanism is `PodTemplate(containerRegistryAuthId="<id>")`, present in the
> SDK (`core/resources/template.py`) and honoured by the deploy manifest builder
> (`cli/commands/build_utils/manifest.py`). Nothing in the documentation or in
> the published `flash` agent skill mentions the field.
>
> **Suggestion:** add it to the `PodTemplate` reference and show it in the
> private-image section of `flash/custom-docker-images`, alongside how to obtain
> the id (`runpodctl registry list`, or the console).

### `runpodctl registry create` has only one way in, and it is the wrong one

```
Flags:
      --name string       registry auth name (required)
      --password string   registry password (required)
      --username string   registry username (required)
```

A registry password as a command-line argument lands in the process table and
the shell history, and stays in both after the command finishes. There is no
`--password-stdin`, no `--password-file`, and no prompt — which is notable
because `docker login` has offered `--password-stdin` for years and warns when
you use `--password`.

This project did not use the command. The credential was created in the console
instead and only its **id** read back with `runpodctl registry list`, which is
not a secret. Least privilege applied on the other side too: the token Runpod
stores is scoped `read:packages` only, so a leak of Runpod's copy cannot publish.

> **Draft issue — Title:** `runpodctl registry create` accepts a registry
> password only as a command-line flag
>
> The only interface is `--password <string>`, which puts a long-lived registry
> credential in the process table and the shell history. There is no
> `--password-stdin`, `--password-file`, or interactive prompt.
>
> **Suggestion:** add `--password-stdin`, matching `docker login`, and warn when
> `--password` is used.

### `flash build` imports every `.py` in the directory, and `.gitignore` is the only way out

`flash build` failed on an app it should not have cared about:

```
Failed to load:
  verify_port.py: ModuleNotFoundError: No module named 'numpy'
```

`verify_port.py` is a local development tool. It is not the app, not imported by
the app, and not deployed. But Flash imports every `.py` file in the project
directory to discover `Endpoint` objects, so a module-level `import numpy` in a
file that has nothing to do with the deployment fails the whole build — because
the flash CLI's own environment has no numpy, and no reason to.

**The escape hatch used to be `.flashignore`, and it was removed in v1.4.**
`cli/utils/ignore.py:53-59` still warns if it finds one:

> `.flashignore` is no longer supported; patterns are now built-in. Move any
> custom patterns to `.gitignore` and delete `.flashignore`.

So the only remaining way to keep a file out of the build is to put it in
`.gitignore`, which conflates two unrelated things: "not in version control" and
"not part of this app". A checked-in tool that lives beside the app cannot be
excluded without untracking it.

Worked around by deferring the numpy and PIL imports into `main()`, which is the
smaller change. Recorded because the failure mode is confusing — the error names
a file the user was not deploying, for a dependency the app does not have.

> **Draft issue — Title:** `flash build` imports every `.py` in the project
> directory, and since v1.4 the only way to exclude one is `.gitignore`
>
> Flash imports each `.py` file under the project directory to discover
> `Endpoint` objects. A module-level import in an unrelated local script — a
> test, a development tool — fails the build with `Failed to load: <file>:
> ModuleNotFoundError`, even though the file is not part of the app and is never
> deployed.
>
> `.flashignore` was removed in v1.4 (`cli/utils/ignore.py:53-59`), and the
> suggested replacement is `.gitignore`. That conflates "not in version control"
> with "not part of the app": excluding a checked-in helper script requires
> untracking it.
>
> **Suggestion:** treat a failed import of a file that declares no `Endpoint` as
> a warning rather than an error, or restore a build-scope ignore file separate
> from `.gitignore`.

### Credit: `--build-context` and a bind mount solved the slow part cleanly

Not a Runpod feature, but worth recording because it changed the shape of the
work. The five model files were already on the build machine. Docker's named
build contexts let an optional local cache override a `FROM scratch` stage, so
the same Dockerfile copies from disk when the cache is offered and downloads
~11GB from HuggingFace when it is not. Staging took **127 s** instead of a long
download, with the identical hash check on both paths.

### The thing that actually saved money was not a Runpod tool at all

The first build of the image **segfaulted on boot** and could never have served
a request. It was caught by running the container on the machine that built it,
which cost nothing. Had it gone straight to a Runpod endpoint, the finding would
have been a paid cold start ending in a crash loop, diagnosed through worker
logs.

Runpod's own guidance points the other way. Cycle 1's audit noted that
`runpod-usage/reference/development-loop.md:9` puts verification after
deployment — `→ run/deploy → VERIFY with a real request → deliver → cost-guard +
teardown` — and that no skill in the pack asks before spending money. A "boot
the image locally first" step costs nothing and belongs ahead of the first
deploy in that loop. Details of the crash itself are in
[FINDINGS.md](FINDINGS.md); it was our defect, not Runpod's.

---

## 2026-08-17 — The public-endpoint catalogue, and four opaque 500s

Numbers in [FINDINGS.md](FINDINGS.md). This is what the documentation and the API
did around them, and one mistake of my own.

### A documented model was withdrawn the same day it was priced

Cycle 2 read the docs, tabulated seven text endpoints, and picked
**Cogito 671B v2.1** at $0.50/1M — twenty times cheaper than the alternatives —
as the value pick. This cycle's plan named it as the model to test.

`https://api.runpod.ai/v2/cogito-671b-v2-1-fp8-dynamic/openai/v1/...` returns:

```
{"status":404,"title":"Not Found","detail":"endpoint not found"}
```

Its documentation page is still up and still gives that exact slug. So is the
pricing. The endpoint is gone.

This is logged here as tooling friction, but it belongs in the talk as an
architecture point: a per-token dependency whose cheapest model can vanish
between one day and the next has no price floor to build a cost model on, and
the only notice you get is a 404 at request time.

### Two of the three text slugs on the live reference page are dead

`docs.runpod.io/public-endpoints/reference` lists its text models as
`granite-4`, `moonshot-kimi`, `qwen3-32b`. Live: `granite-4` **404**,
`qwen3-32b` **404**, `moonshot-kimi` 200. And `qwen3-32b-awq`, which works and is
the only endpoint that can do constrained decoding, **is not on the page at
all**.

The page also puts two different identifiers in one column headed "model slugs".
`kimi-k2.6` is a *model id* for the request body; the *endpoint slug* serving it
is `moonshot-kimi`. Use the documented value in the URL and you get a 404. The
distinction is never stated.

### Four opaque 500s, and what each turned out to be

Every one of these returns the same body — `{"status":500,"title":"Internal
Server Error","detail":"internal server error"}` — with nothing naming the
offending field. All four were found by bisection, not by reading an error.

**1 and 2: `temperature` and `top_p`, independently, on `moonshot-kimi`.** Two of
the most basic OpenAI parameters, on a route advertised as OpenAI-compatible.
Remove either and the identical request succeeds. Home runs every transform at a
deliberate temperature, so this endpoint cannot reproduce home's sampling at all.

**3: `response_format` with a real-world schema.** Which looked like "public
endpoints do not support structured output" and would have been the wrong
conclusion — see below.

**4: `minLength`/`maxLength` on a string, inside an otherwise fine schema.** This
one hangs for **60 seconds** before returning the 500, which reads like a
timeout rather than a rejected parameter.

### Credit where it is due: structured output works, and nothing says so

Having got a 500 from `response_format`, the obvious conclusion was that public
endpoints have no constrained decoding — consistent with Cycle 2's finding that
no Runpod page documents any. That conclusion was wrong.

On `qwen3-32b-awq`, against a simple schema, **all four mechanisms work**:
`response_format: {type: json_object}`, `{type: json_schema}`, the same with
`strict: true`, and vLLM's native `guided_json`. Every one returns exactly
`{"ok":true}`.

So the capability Scriptorium needs is there and is genuinely good. It is
documented nowhere — not on the reference page, not on the per-model pages, not
in the flash skill. Working it out took a bisection over five request shapes and
six schemas.

### The mistake I made, and how the tool changed

The probe originally read `clientBalance`, waited for it to stop changing, and
reported the delta as the cost. It reported that this account was billed **3.26×
below list price** — a striking claim, stated confidently, and wrong.

Runpod's balance lags charges by several minutes. A reading taken a minute after
the last call reports a fraction of the spend, and because nothing has posted
yet, it does not move on re-reads either — so a lagging number passes a
stability check. The real spend showed up later and matched list price to the
cent.

`tools/public_endpoint_probe.py` now treats the endpoint's own `cost` field as
authoritative — it is exact, `total_tokens ×` the published rate on both models
tested — and prints the balance only as a lagging cross-check, with the reason
written into the code so the next person does not redo it.

The general lesson is the useful one: **a stable reading is not a settled one**,
and on this platform the two instruments disagree in opposite directions —
serverless spend appears in the balance and never in the billing history, while
per-token spend appears in the response and only slowly in the balance.

### Smaller things

**Public endpoints have cold starts too.** The first call to `qwen3-32b-awq`
took **59.66 s**; the next took 0.33 s. The selling point is that there is no
worker to manage, which is true, but "no cold start" is not — you simply do not
own it and are not billed for it.

**`kimi-k2.6` is a reasoning model and nothing says so.** Neither the reference
page nor the model list marks it. It returns `reasoning_content`, and on a
700-token budget it spent 699 tokens thinking and returned an empty `content`
ten times out of ten — billed in full. A caller sizing `max_tokens` from a
non-reasoning model's needs gets nothing back and pays for it.

---

## 2026-08-17 — Deploying the first app: what the tools told us, and what they did not

Friction from the first real deployment. The numbers are in
[FINDINGS.md](FINDINGS.md); this is what the tooling did around them.

### The one that costs money: `runpodctl` cannot see the setting that bills

`flash`'s `Endpoint(workers=(0, 1))` deploys `workersStandby: 1`. That field is
what the console calls an **active worker**, and Runpod's own configuration page
says active workers "incur charges continuously, including when idle."

Neither `runpodctl serverless list` nor `runpodctl serverless get <id>` returns
`workersStandby`. Both return `workersMax` and omit both `workersMin` and
`workersStandby` entirely. So the CLI shows you a `workersMax: 1` endpoint and
gives you no way to learn that a worker is being held warm.

Seeing it required going outside both CLIs, to
`GET https://rest.runpod.io/v1/endpoints`, which returns all three fields.

**And there is no CLI route to fix it either.** `runpodctl serverless update`
offers `--workers-min` and `--workers-max` and no standby flag. A `PATCH` to
`rest.runpod.io/v1/endpoints/<id>` with `{"workersStandby": 0}` is rejected:

```
HTTP 400 {"error":"Extra input keys provided in request body",
 "problems":["key provided in request body which is not in input schema: 'workersStandby'"]}
```

So the v1 REST API will *report* the field and will not *accept* it. The only
remaining lever found was deleting the endpoint.

This is the material for draft issue 5, which is **not written yet and not
filed** — it waits on the longer measurement, per the same rule as drafts 2
and 3.

### The CLI prints a request example that cannot work

`flash deploy` finished by printing the app's routes and then a ready-to-paste
curl:

```
  hello-flash  https://qb4qjquyist574.api.runpod.ai
               GET   /health
               POST  /predict

curl -X POST https://qb4qjquyist574.api.runpod.ai/predict \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $RUNPOD_API_KEY" \
  -d '{"input": {}}'
```

Two problems in four lines, on the endpoint the command just created.

It is a **load-balanced** endpoint — the CLI says so immediately above, listing
`GET /health` and `POST /predict`. A load-balanced route takes the handler's
argument at the top level, so this app wants `{"data": {...}}`. The printed body
is the **queue-based** shape.

And `{"input": {}}` is specifically the payload Runpod's own flash skill
documents as always failing: *"Never send an empty `input`. A QB request with
`{"input": {}}` is rejected by the worker SDK as `Job has missing field(s): id or
input`."* The CLI prints it as the suggested first call.

The third line also assumes `RUNPOD_API_KEY` is exported, which it is not on a
machine set up with `flash login` — the auth method the docs recommend.

### Three transient GraphQL failures inside one deploy

The redeploy retried three times before succeeding:

```
WARNING | Retrying GraphQL request after transient failure (attempt 1/3): GraphQL errors: Something went wrong. Please try again later or contact support.
WARNING | Retrying GraphQL request after transient failure (attempt 2/3): GraphQL errors: Something went wrong. Please try again later or contact support.
WARNING | Retrying GraphQL request after transient failure (attempt 3/3): GraphQL errors: Something went wrong. Please try again later or contact support.
WARNING | LiveLoadBalancer:qb4qjquyist574 is no longer valid, redeploying.
```

**Credit where due: the retry worked and the deploy succeeded.** The last line is
also genuinely good behaviour — the previous endpoint had been deleted out from
under the app, and Flash detected the stale load balancer and provisioned a new
one instead of failing. The deploy took 14.6 s instead of 2.4 s and produced a
new endpoint id.

The complaint is only that "Something went wrong. Please try again later or
contact support." is what the server said three times about a stale-resource
condition that Flash then diagnosed correctly by itself.

### `ready` does not mean ready, and `completed` never moves

Two observations about the platform health route, both of which would mislead
someone building a dashboard on it.

`GET /v2/<id>/health` reported `workers: {idle: 1, ready: 1}` *before* the first
request. That request still paid a **31.387 s** cold start. Whatever `ready`
counts, it is not "will answer promptly".

And `jobs: {completed: 0, …}` stayed at zero through four successful requests,
because load-balanced routes are not queue jobs. On a Flash LB endpoint the job
counters are permanently zero and cannot be used to confirm traffic.

### Building an `Authorization` header without touching the key

Worth recording as the answer to a problem Cycle 2 deferred rather than solved.

Calling any endpoint needs a Bearer header. `runpodctl` has no subcommand that
invokes one, so Cycle 2 skipped its test call rather than reach for the
key-extraction one-liner it had flagged in Runpod's own skills:

```
KEY="${RUNPOD_API_KEY:-$(grep '^apikey' ~/.runpod/config.toml | sed ...)}"
```

`tools/runpod_http.py` does it instead: it reads `~/.runpod/config.toml` inside
the process, builds the header there, and has no flag that can print a key. Every
byte it emits or saves passes through a redactor, and its error path drops the
original exception so a urllib `HTTPError` cannot carry request headers into a
traceback. The difference from the one-liner is not cosmetic — that version
leaves the key in a shell variable, the process table, and the shell history,
all of which outlive the command.

It accepts either key name, because after `flash login` the file has both.

---

## 2026-08-17 — Cycle 3: the credential issue, filed

**Filed: [runpod/flash#363](https://github.com/runpod/flash/issues/363)** —
"flash cannot read a `~/.runpod/config.toml` written by runpodctl; the error
suggests exporting the key instead".

Filed on `runpod/flash`, which is the public repository behind the `runpod-flash`
package (`src/runpod_flash/…`), has issues enabled, and had no duplicate —
searched `RunpodAPIKeyError`, `get_credentials default profile` and
`apikey config.toml` across the whole `runpod` org before filing.

Three things changed between Cycle 2's draft and what was filed. All three are
corrections to Cycle 2, not additions.

**1. The repro is sharper, and the old one was weaker than it looked.** Cycle 2
compared a working `runpodctl user` against a failing `flash app list`. That
leaves a reader able to wonder whether the key itself was the problem. The filed
repro points both tools at an isolated `HOME` holding a one-line config with a
*placeholder* key:

```
$ env -u RUNPOD_API_KEY HOME=/tmp/fakehome runpodctl user
{"error":"api request failed with status 401","code":"unauthorized","status":401}

$ env -u RUNPOD_API_KEY HOME=/tmp/fakehome flash app list
RunpodAPIKeyError: No RunPod API key found.
```

`runpodctl` returning **401** is the whole argument: it read the file and
transmitted what it found. `flash`, against the same file, reports that no key
exists. The difference is isolated to the read path and nothing else. Verified
today against 1.19.0, not quoted from Cycle 2.

**2. The write path already knows, and Cycle 2 missed it.** At upstream HEAD,
`src/runpod_flash/core/credentials.py:23-28` carries a comment naming
runpodctl's top-level `apikey` and explaining that `flash login` must preserve
it. So the project is already aware both schemas share one file — it handles
that when **writing** and not when **reading**. Cycle 2 read this as an
oversight. It is an asymmetry, which is a better-evidenced and more fixable
thing to report.

**3. "The docs say one login serves both" is not accurate, and the issue does
not claim it.** Checked before filing:

| Page | What it actually says |
|---|---|
| `docs.runpod.io/flash/overview` | "`flash login` … This saves your API key securely." Never names the file or its schema. |
| `docs.runpod.io/runpodctl/install-runpodctl` | Names `~/.runpod/config.toml` and an `apiKey` field. Never mentions `flash`. |
| `docs.runpod.io/get-started/api-keys` | Console key management only. |

Runpod's **documentation** never claims the two interoperate. Runpod's shipped
**agent skills** do — `runpod-usage/reference/getting-started.md` ("one login
serves both") and `runpod/SKILL.md` ("runpodctl + flash read it"). Those are a
different artifact in a different repository, and the issue attributes the claim
to them by name rather than to the docs. Cycle 2's own entry got this right; the
loose phrasing crept in afterwards, and it is corrected here.

**One suggestion in the issue is worth repeating, because it costs nothing.**
runpod-python already computes the exact diagnostic the error should print.
`check_credentials()` returns *"~/.runpod/config.toml is missing default
profile."* `get_api_key()` calls `get_credentials()` instead, which returns a
bare `None`, so that string is thrown away and the user gets three remedies that
all begin with obtaining the plaintext key.

Versions on the report: `runpod-flash` 1.19.0, `runpod` (runpod-python) 1.12.0,
`runpodctl` 2.9.0-c094cac, Python 3.13.

---

## 2026-08-17 — Where the billing documentation leaves you guessing

Answering one question — does an idle Flash app with zero workers bill anything —
took reading five pages, and the answer is on none of the two you would look at
first. The answer itself is in [FINDINGS.md](FINDINGS.md). What follows is what
the documentation did to get there.

Three gaps, in descending order of how much money a reader could lose to them.
Draft issue text for each; **nothing has been filed.**

### Gap 1 — the serverless pricing page never says container disk needs a worker

`docs.runpod.io/serverless/pricing` lists three cost components. One of them is:

> | **Container disk** | Worker storage (5-min intervals) | ~$0.10/GB/month |

That is the whole entry. A standalone line item, a per-month rate, and a
parenthetical implying a recurring meter. Flash's default container disk is 64 GB
(`flash/reference/api.md:58`, `containerDiskInGb=64`), so a reader who stops at
this page reasonably concludes that a deployed app accrues about **$6.40 a month
forever**, and tears it down to avoid that.

The correction is on a page they have no reason to open,
`serverless/storage/overview`: container disk is "Temporary storage that exists
only while a worker is running", and its cost is "included in the worker's running
cost." Not a separate meter at all.

> **Draft issue — Title:** Serverless pricing page implies container disk bills
> independently of workers; it does not
>
> **Page:** `docs.runpod.io/serverless/pricing`
>
> The cost-components table lists **Container disk** as its own line at
> ~$0.10/GB/month with the qualifier "Worker storage (5-min intervals)", and the
> page never states whether that charge requires a worker to exist. Since Flash
> defaults to a 64 GB container disk, a reader of only this page concludes a
> deployed, idle, scaled-to-zero endpoint accrues roughly $6.40/month.
>
> `serverless/storage/overview` contradicts that reading — container disk "exists
> only while a worker is running" and its cost is "included in the worker's
> running cost" — but a reader comparing deployment costs goes to the pricing
> page, not the storage page.
>
> **Suggestion:** add one clause to the container-disk row, e.g. "billed only
> while a worker is running; nothing accrues at zero workers", and define what
> "(5-min intervals)" means. Right now that parenthetical is the only text on the
> subject and it is undefined.

### Gap 2 — model download time is exempted from billing, image pull is not addressed

`serverless/endpoints/model-caching` is explicit and welcome: "You aren't billed
for worker time while your model is being downloaded", and it holds even on a
cache miss.

But `serverless/development/optimization` names **two** separate cold-start
metrics — "Initialization time: Downloading Docker image" and "Cold start time:
Loading model into GPU memory" — and no page says whether the first one is billed.
For a container carrying an SDXL stack, image pull is a large fraction of cold
start, so this is not a rounding question.

> **Draft issue — Title:** Docs exempt model download time from billing but never
> say whether Docker image pull time is billed
>
> `serverless/endpoints/model-caching` states you are not billed for model
> download time. `serverless/development/optimization` treats "Initialization
> time: Downloading Docker image" as a metric distinct from "Cold start time:
> Loading model into GPU memory". Neither page, nor `serverless/pricing`, says
> whether image pull falls inside the billable "start time" phase.
>
> Since the docs went out of their way to carve out model downloads, the silence
> on image pulls reads as deliberate — but a reader cannot tell whether it is
> billed, and the answer changes the cost of every cold start on a large image.
>
> **Suggestion:** state it either way on `serverless/pricing`, next to the
> three billable phases.

### Gap 3 — the skills contradict themselves on whether a warm worker bills

This one is not a gap but a straight conflict, which is worse: one of the two is
simply wrong, and a reader has no way to tell which.

`runpod/golden-paths/15-monitor-and-debug.md:70-76` gives a worker-state billing
table:

> | `idle` / `ready` | up, waiting for work | **no (idle)** |

`runpod/golden-paths/13-autoscaling-tuning.md:229` says the opposite:

> `idle`/`ready` = **warm & billed** (during idle timeout)

and `13-autoscaling-tuning.md:45` reinforces it, calling idle timeout a knob where
"↑ = fewer cold starts on bursty traffic, **more idle $**".

The official documentation sides with `13`: `serverless/endpoints/endpoint-configurations`
says "You're billed during idle time, but the worker remains warm for immediate
processing", and `serverless/pricing` lists the idle-timeout tail as one of three
billable phases.

**So `15-monitor-and-debug.md:73` is wrong**, and it is wrong in the expensive
direction. An agent that trusts it concludes a long `idle_timeout` is free and
sets it high. At the 24 GB tier's $0.69/hr, a 300-second idle timeout on a bursty
workload is real money spent on an idle GPU.

> **Draft issue — Title:** Two golden paths give opposite answers on whether
> `idle`/`ready` workers are billed
>
> `runpod/golden-paths/15-monitor-and-debug.md:73` lists `idle`/`ready` as **not**
> billed. `runpod/golden-paths/13-autoscaling-tuning.md:229` lists the same states
> as "warm & billed (during idle timeout)", and `:45` describes idle timeout as a
> cost knob.
>
> `docs.runpod.io/serverless/endpoints/endpoint-configurations` ("You're billed
> during idle time") and `serverless/pricing` (idle-timeout tail is one of three
> billable phases) both support `13`, which makes `15` incorrect.
>
> The error favours overspending: a reader who believes idle is free will raise
> `idle_timeout` to avoid cold starts.
>
> **Suggestion:** correct the table in `15-monitor-and-debug.md` to mark
> `idle`/`ready` as billed for the duration of the idle timeout, and cross-link
> the pricing page's three billable phases.

### One more thing, not a gap but worth saying

The **skills' public-endpoint model list is stale, and stale in a way that costs
money.** `runpod/golden-paths/11-public-endpoints.md:43-52` is dated "as of
2026-07-13" and offers exactly two text models, `qwen3-32b-awq` and `granite-4`,
both at a single blended "$10.00 / 1M tokens" with no input/output split. The live
catalogue has considerably more, including one at **$0.50/1M** — a twentieth of
what the skill recommends — and the Kimi models publish separate input and output
rates. An agent following the skill would pick a model 20× more expensive than
necessary and would model its costs with the wrong rate shape. Dated content
presented as a table is read as a table.

---

## 2026-08-17 — The two CLIs do not share the credential file they share

Cycle 2 opened by checking that both Runpod command-line tools can read the
installed API key. One can. The other cannot, and the reason is a format
mismatch inside a single file that both tools own.

Nothing was deployed for this. Both checks are read-only account queries.

### What happened

`runpodctl user` works first time. It reads `~/.runpod/config.toml`, returns the
account record, and needs nothing in the environment. That is the documented
behaviour and it is accurate.

Every `flash` subcommand that touches the account fails:

```
RunpodAPIKeyError: No RunPod API key found. Set one with:

  flash login                              # interactive setup
                 or
  export RUNPOD_API_KEY=<your-api-key>     # environment variable
                 or
  echo 'RUNPOD_API_KEY=<your-api-key>' >> .env
```

`flash app list` and `flash env list` both exit 1 with a full Python traceback
above that message.

### Why

The two CLIs read different keys out of the same file.

`runpodctl` uses a **top-level `apikey`** — documented at
`runpodctl/reference/output-and-errors.md:201`, and the shape the skills' own
extraction one-liner greps for (`grep '^apikey'`).

`flash` delegates to `runpod-python`. `runpod_flash/core/credentials.py:46` reads
`creds.get("api_key")`, where `creds` comes from
`runpod.cli.groups.config.functions.get_credentials(profile="default")` — and
that function returns `None` outright if the parsed TOML has no `default` table:

```python
if profile not in credentials:
    return None
```

So `flash` needs a **`[default]` table containing `api_key`**. Given a file with
only the top-level `apikey`, `get_credentials()` returns `None`,
`get_api_key()` returns `None`, and `flash` reports "No API key found" about a
file it successfully read.

The header of `credentials.py` states the intended contract as *"Resolution
priority: RUNPOD_API_KEY env var > .env > ~/.runpod/config.toml"*. The file is in
the priority list; the format it must be in is not stated anywhere.

### Why this one matters more than the usual doc nit

The error message lists three remedies and every one of them puts the plaintext
key somewhere new — an environment variable, a `.env` file, or an interactive
prompt. None of them says "the file you already have is in the wrong shape."
An agent or a person following that message lands exactly on the
credential-extraction one-liner this project flagged in Cycle 1 at
`runpod-usage/reference/getting-started.md:43`. The bad practice is not just
documented in the skills; the CLI's own error text steers you into it.

And the skills assert the opposite of the truth. `runpod-usage/reference/getting-started.md:49`:

> Or `flash login` — browser OAuth that **saves a real API key to
> `~/.runpod/config.toml`**, which runpodctl reads too, so one login serves both.

`runpod/SKILL.md:48-49` repeats it: *"saves a real key to `~/.runpod/config.toml`
(runpodctl / + flash read it; reuse it for the MCP Bearer). One step, unlocks
all."* Neither direction of that claim holds — `flash` cannot read runpodctl's
entry, and runpodctl does not read flash's.

**Credit where due:** the fix is safe. `set_credentials` parses the existing file
with `tomlkit` and assigns only its own profile, so `flash login` appends the
`[default]` table and leaves the top-level `apikey` intact. One file ends up
serving both tools. That is the behaviour the docs promise; it just needs both
entries present, and nothing tells you so.

Versions: `runpodctl 2.9.0-c094cac`, `Runpod Flash CLI v1.19.0`,
`runpod-flash` 1.19.0 on Python 3.13.

### Draft issue — FILED 2026-08-17 as [runpod/flash#363](https://github.com/runpod/flash/issues/363)

> **Superseded by what was actually filed.** Kept verbatim as the record of what
> was drafted. Three corrections were made before filing — a sharper repro, the
> write-preserves/read-ignores asymmetry, and precise attribution of the "one
> login serves both" claim to the skill pack rather than to the documentation.
> See "Cycle 3: the credential issue, filed" at the top of this file.

> **Title:** `flash` cannot read a `~/.runpod/config.toml` written by `runpodctl`, and the error suggests exporting the key instead
>
> **Where:** `runpod_flash/core/credentials.py`, plus
> `docs.runpod.io` credential guidance.
>
> **Versions:** `runpod-flash` 1.19.0, `runpodctl` 2.9.0.
>
> **What happens:** with a `~/.runpod/config.toml` containing a top-level
> `apikey` — the form `runpodctl` itself writes and reads — every `flash`
> subcommand that contacts the account fails with `RunpodAPIKeyError: No RunPod
> API key found`. `runpodctl user` against the same file succeeds.
>
> **Cause:** `credentials.py:46` reads `creds.get("api_key")` from
> `runpod-python`'s `get_credentials(profile="default")`, which returns `None`
> when the file has no `[default]` table. `runpodctl` uses a top-level `apikey`
> instead. Both tools document `~/.runpod/config.toml` as the shared credential
> file, and Runpod's guidance says one login serves both, but the two use
> incompatible schemas.
>
> **Reproduce:**
> 1. Put `apikey = '<key>'` at the top level of `~/.runpod/config.toml`.
> 2. `runpodctl user` → succeeds.
> 3. `flash app list` → traceback, `RunpodAPIKeyError`.
>
> **Two suggestions, either sufficient:**
> - Have `credentials.py` fall back to a top-level `apikey` when the `default`
>   profile is absent, so the two CLIs interoperate as documented.
> - Failing that, make the error distinguish "no credential file" from
>   "credential file present but no `[default]` profile", and have it name
>   `flash login` as the fix for the second case rather than leading with
>   `export RUNPOD_API_KEY=`. Suggesting that a user extract a plaintext key into
>   an environment variable should not be the first remedy offered when a
>   perfectly good credential file already exists.

### Smaller friction from the same session

**`runpodctl` had to be installed, and the documented way is a pipe to a shell.**
`runpodctl/SKILL.md:23` and `reference/install.md:4` both give
`curl -sSL https://cli.runpod.net | bash` — unpinned, unverified. Cycle 1's audit
ranked that line as the most likely of the three security alerts that fired at
install time. It was not used. The release is published on GitHub **with a
`checksums_<version>_sha256.txt` file**, so a pinned, verified install is
available and takes three commands. The skills never mention it exists.

**`runpodctl billing` is invisible if you read the SKILL.** The billing
subcommands — `pods`, `serverless`, `network-volume` — appear only in
`runpodctl/reference/command-reference.md:112-122`, not in
`runpodctl/SKILL.md`'s command listings. An agent that reads the SKILL and stops
there never learns the account can be asked what it actually spent, which is the
one command that turns a cost estimate into a cost.

**There is no `runpodctl billing public-endpoints`.** The three subcommands cover
pods, serverless and network volumes. Per-token public-endpoint spend has a
first-class REST endpoint (`get-public-endpoint-billing-history`) but no CLI
route, so the only no-key way to read the account's own billing history cannot
see that category at all.

**One correction to Cycle 1's own note.** The audit said `flash` has "no
`flash version`". It has `flash --version` / `-v`, which prints
`Runpod Flash CLI v1.19.0`. The subcommand does not exist; the flag does.

---

## 2026-08-17 — Installing the Flash CLI, following the skill

Friction log from doing exactly what `flash/reference/setup-and-cli.md` says, on
a clean machine. Four things, none fatal, all worth a sentence in the docs.

**1. The documented install command fails on a current machine — and the skill
already knows.** This box runs Python 3.14.4 as its default. `runpod-flash`
1.19.0 declares `requires_python <3.14`, so the headline command
`uv tool install runpod-flash` cannot work here. The skill's quick start at
`flash/SKILL.md:28` gives that bare command. The correct one is three lines
further down in `reference/setup-and-cli.md:9`:

```
uv tool install --python 3.13 runpod-flash
```

Credit where due: the reference file *does* call this out — *"on Python 3.14+
the install fails — pin an older interpreter for the tool."* The gap is that the
top-level quick start, which is what gets read first and copied, does not. Cost:
one failed install. Verdict: **documented, badly placed.**

**2. `flash` writes into whatever directory you run it in.** Running
`flash --version` created `.flash/logs/activity.log` in the current working
directory. Zero bytes, but it appeared from a command that only prints a version
string, in a directory that is a git repository. Nothing in the skill mentions
`.flash/`. It is now in this repo's `.gitignore`. Verdict: **undocumented, minor,
would be surprising in someone's home directory.**

**3. The CLI has a large dependency surface, including a third-party crash
reporter.** The install pulled in ~60 packages, among them `sentry-sdk`. To be
accurate about it: that arrives transitively via `fastapi-cloud-cli`, it is not
Runpod's telemetry, and nothing in `runpod_flash` initializes it — `grep` for
`sentry_sdk.init` across the package finds only `fastapi_cloud_cli`'s own
module. So this is **not** a phone-home. It is worth noting only as supply-chain
surface for a CLI whose job is to upload a Python file.

**4. `flash login` is unusable by an agent, and the skill says so.** It is
browser OAuth, marked *"Human-only (needs a browser)"*. The documented
alternative is `export RUNPOD_API_KEY=...`. Worth flagging that
`flash/SKILL.md:203-206` describes a genuinely nasty consequence of having both:
a set environment variable silently overrides a good saved login, and the
failure is quiet — provisioning logs a 401 while `flash dev` still prints its
normal ready line. That is a good gotcha, well written, and it is gotcha number
13 of 15 rather than a warning next to the auth instructions.

### What the skill got right

Worth saying, because a log of only complaints is not useful:

- The `Endpoint` constructor reference (`flash/reference/api.md:5-29`) is
  complete and accurate — every parameter used in `hello-flash/main.py` came
  from it and behaved as described.
- `flash/SKILL.md:175`, gotcha #1, is the single most valuable line in the
  skill: only the function body ships to the worker under `flash dev`, so a
  module-level constant raises `NameError` remotely, while `flash deploy`
  imports the whole module and works. Code that fails in development and
  succeeds in production is a confusing direction for a bug to travel, and being
  warned in advance saved real time.
- The teardown guidance is honest about its own tooling being unreliable
  (`flash undeploy list` can report "no endpoints" for an app that is deployed),
  and it names the command that actually works.

### Still open

The app is written and not deployed, because no API key exists on this machine.
No Runpod resource has been created and nothing has been spent. Deployment
numbers — cold start, request time, cost — go in `FINDINGS.md` when it runs.

---

## 2026-08-17 — Security audit of the six Runpod agent skills

**Why:** the skills were installed to help build on Runpod, and an install-time
security scan reported 3 alerts on one of them. Before leaning on the `flash`
skill to build and deploy something, the skills needed reading. Nothing in the
skill tree was executed for this audit — only `find`, `grep`, `ls`, and file
reads.

### What was audited

97 files under `~/.agents/skills/`, installed `2026-08-17T14:18:57Z` from
`runpod/runpod-plugins-official` (per `~/.agents/.skill-lock.json`). Six skills:
`runpod` (a router), `flash`, `runpodctl`, `runpod-mcp`, `runpod-usage`,
`companion-clis`. A seventh skill, `find-skills`, is present but comes from
`vercel-labs/skills` and is not Runpod's; it is noted separately below.

**Zero of the 97 files are executable.** `find ~/.agents/skills -type f -perm -u+x`
returns nothing. 12 files are not markdown: 4 `Dockerfile`, 3 `start.sh`, 2
`handler.py`, 1 `main.py` test fixture, 2 `requirements.txt`. All 12 are template
content meant to be copied into a container image. All 12 are in `runpod`,
except the one `main.py` fixture in `flash`.

### Does anything phone home?

**No.** Grepping all 97 files for
`telemetry|analytics|posthog|segment.io|sentry|mixpanel|beacon|phone.?home`
returns exactly one hit, and it is a false positive:
`runpod-usage/reference/gotchas.md:80` says to "check the **Telemetry** tab",
meaning a tab in Runpod's own web console. Every URL in the tree is a
documentation page, a GitHub repository, the Runpod API, or PyPI/npm. There is
no analytics, no tracking, and no hidden network call.

### Does anything run unexpected commands?

Yes, in three places.

1. `runpod/SKILL.md:30-40` makes an authenticated API call a precondition of any
   Runpod task, before the user's actual request:
   ```
   ## First run — check auth before the first infra action
   ...
   runpodctl user            # succeeds ⇒ a key is set and valid
   ```
   If it fails, the skill's remedy is to install software (see below).

2. `runpodctl/SKILL.md:38` — an unconditional self-update:
   ```
   runpodctl update                    # FIRST: get on the latest build — old versions cause confusing errors
   ```
   That silently replaces a binary the user did not ask to have replaced.

3. `flash/SKILL.md:53` — launch a long-lived detached process:
   ```
   flash dev > /tmp/flash-dev.log 2>&1 &                          # background; never run it blocking
   ```
   This one matters for cost, not security. See "the thing the skills never
   say" below.

### Does anything write outside the project?

Yes, routinely:

- `~/.runpod/config.toml` — a long-lived API key (`runpod/SKILL.md:48`).
- `~/.local/bin` plus an edit to `~/.bashrc` or `~/.zshrc`
  (`runpodctl/reference/install.md:11,20`).
- User-scope MCP client configuration, i.e. `~/.claude.json`
  (`runpod-mcp/reference/connect.md:11,29`) — including, in one variant, the API
  key written literally into that global file.
- `/tmp/flash-dev.log` (`flash/SKILL.md:53`).
- `~/.ssh/id_ed25519` and `~/.ssh/config` (`companion-clis/reference/github-setup.md:38-59`).
- **`flash init` writes `AGENTS.md` and a `CLAUDE.md` symlink**
  (`flash/reference/setup-and-cli.md:22`). That is vendor-authored text landing
  in a file coding agents read as authoritative instructions. Worth avoiding on
  principle regardless of what the text says.

### The 3 alerts — best guess

The scan output does not persist anywhere on disk. `~/.agents/` contains only
`.skill-lock.json` and `skills/`, and the lock file records source and
timestamps with no security fields. The alerts were printed to the terminal at
install time. Ranked by how likely each is to have been one of the three:

**1. Remote code piped to a shell.** `runpod/SKILL.md:55`:
```
before any CLI-only step. Missing a CLI? `curl -sSL https://cli.runpod.net | bash` (runpodctl) ·
```
Downloading a script from a bare domain straight into a shell is on every
scanner's rule list. It is in the top-level file scanners always read, and it is
phrased as an action to take mid-task, not a passive mention. The same line also
carries `uv tool install runpod-flash` and `npx @runpod/mcp-server@latest add`,
so a rule counting install commands rather than lines fires more than once here.

**2. Credential handling.** `runpod/SKILL.md:36`:
```
**Check** (credential resolution order: `RUNPOD_API_KEY` env → `.env` → `~/.runpod/config.toml`):
```
and `runpod/SKILL.md:42`:
```
**Rule: get a key first — do not default to MCP OAuth.** The reason: one `RUNPOD_API_KEY`
```
A secret's name, plus the file paths it lives in, plus a `Bearer` header
construction, is a near-certain "handles credentials" alert.

**This is also the finding that matters most in substance**, and it is not a
false positive. The skill actively steers the user off the more secure option.
OAuth gives a scoped, revocable session with no key on disk. The skill calls
that "a half-setup" (`runpod/SKILL.md:46`) and pushes toward a long-lived
plaintext key which, by its own explanation, unlocks three separate tools at
once. That is a real widening of blast radius, argued for on convenience
grounds.

**3. SSH backdoor signature.** Three shipped shell scripts contain:
```
echo "$PUBLIC_KEY" >> ~/.ssh/authorized_keys
```
at `runpod/golden-paths/22-minimal-pod-image/template/start.sh:11`,
`25-bake-vs-mount/template/start.sh:7`, and
`09-custom-serverless-dev-loop/template/start.sh:15` — the last followed by
`ssh-keygen -A` and `service ssh start`. "Append an environment-supplied public
key to authorized_keys, then start sshd" is textbook backdoor shape.

**This one is a false positive in substance.** These are container entrypoints
that run on a remote Runpod pod, never on the user's machine. They reproduce
what Runpod's own `runpod/pytorch` image does, and
`22-minimal-pod-image/template/start.sh:2-5` says so. They are not executable
and nothing invokes them locally. But `runpod` is the only skill that ships
`.sh` files at all, so a scanner weighting "this skill contains shell scripts"
concentrates entirely on it.

**Close runners-up**, any of which could displace #3 depending on the rules:

- `runpod/golden-paths/16-serverless-webhooks.md:52` provisions a receiver at
  `webhook.site` and routes real job output through it. That is a well-known
  exfiltration and canary domain, and likely on a blocklist. It is used honestly
  here — a tutorial, with a production alternative given at line 57 — but it is
  a live, copy-pasteable command in a document the router tells agents to open
  and copy from.
- `runpod/golden-paths/10-multi-region-ha-serverless.md:325-329` clones an
  unpinned third-party repository, installs its dependencies, and exports three
  secrets into its process. No commit pin, no integrity check.
- `runpod/golden-paths/README.md:110` tells the agent to edit its own skill
  files: *"If the skills fall short, fold the fix back into the relevant
  `SKILL.md`."* Self-modifying instructions are a recognized injection vector.

### Two things worth saying plainly

**The worst single line in the tree is not in the skill that got flagged.** It is
`runpod-usage/reference/getting-started.md:43`:
```
`KEY="${RUNPOD_API_KEY:-$(grep '^apikey' ~/.runpod/config.toml | sed "s/apikey = '//;s/'//")}"`.
```
That is a ready-to-run one-liner for extracting a plaintext API key out of a
credential file into a shell variable. The intent is benign — it is offered for
building an `Authorization` header — but it is a credential-harvesting primitive
verbatim. If `runpod-usage` scanned clean while `runpod` got three alerts, the
scanner is reading prose shallowly and a clean result on any skill should not be
treated as meaningful.

**No skill anywhere asks before spending money.** Grepping all six for
confirmation language turns up seven "stop and ask" instructions, and every one
is about *blocked* work — a missing credential, a license click, a quota
increase — never about spend:

> `runpod-usage/reference/development-loop.md:70` — "license, a missing
> credential, a payment issue — **stop and say exactly what's blocked**. Don't
> spin or fake progress."

Cost is handled after the fact. `runpod-usage/reference/development-loop.md:9`
puts it last in the pipeline: `→ run/deploy → VERIFY with a real request →
deliver → cost-guard + teardown`. An agent following these skills faithfully
will provision billable GPUs and only then think about the bill.

The one genuinely good cost warning in 97 files is `runpodctl/SKILL.md:123`:

> ⚠️ **A min-1 worker bills continuously, even while idle** (it defeats
> scale-to-zero). When you set `--workers-min 1` for dev, you **must** set it
> back to `--workers-min 0` (or delete the endpoint) when done — otherwise it
> quietly runs up cost.

### The thing the skills never say

**The `flash` skill contains no pricing, no dollar figures, and no billing
guidance at all.** Grepping the entire `flash/` directory for
`cost|billing|charge|spend|per hour` returns exactly one line, and it is in a
test file rather than user-facing guidance —
`flash/evals/dev-loop-iteration.eval.md:4`:

> worker and incurs cost. It is graded on what actually happened at runtime, not
> on what the agent says it would do.

That matters because of what `flash dev` actually does.
`flash/SKILL.md:32-34` describes it as the iterate-locally command — but the
decorated functions "execute on **remote GPU/CPU workers**." **`flash dev` spends
money.** Combined with `flash/SKILL.md:53` ("background; never run it blocking")
and the `kill %1` reminder buried at the end of a bullet at line 72, it is easy
to leave GPU workers running after a session ends. A newcomer reading the skill
front to back would not learn that the development command bills.

### Verdict

This reads as a **legitimate, unusually thorough vendor skill pack with
normal-for-2026 hygiene problems** — not as malware. No obfuscation, no encoded
payloads, no telemetry, no hidden network calls, and honest documentation of
what writes where. Two of the three likely alerts are true findings about
posture rather than intent; the third is a scanner artifact.

The real risks are: it installs software and writes to the home directory as a
side effect of helping; it argues the user off OAuth and onto a long-lived key
with a wider blast radius; and it will provision billable GPUs without ever
pausing to ask.

**The `flash` skill is safe to build on**, with three guardrails adopted for this
project:

1. **Treat `flash dev` as billable** and gate it exactly like `flash deploy`. The
   skill does not say this; it is true anyway.
2. **Never run `flash undeploy --all`.** It is account-wide and would delete
   endpoints this project did not create. The skill's own test file warns about
   this twice (`flash/evals/dev-loop-iteration.eval.md:53-55,60-61`). Tear down
   by name.
3. **Do not run `flash init`.** Hand-write the project files instead, so no
   vendor-authored `AGENTS.md` or `CLAUDE.md` lands in a repository where an
   agent will read it as instructions.

Also adopted, outside the skills' advice: the Runpod MCP server is blocked for
this session via `.claude/settings.json`, because it can manage the account and
spend money, and the API key lives at `~/.runpod/config.toml` — outside this
repository, where it cannot be committed.

### Open item

The exact text of the 3 alerts was not recovered; it does not persist on disk.
Kris's terminal scrollback from the install at `2026-08-17T14:18:57Z` would
confirm or correct the ranking above. Worth checking, because being wrong about
which three fired is itself a finding about the scanner.
