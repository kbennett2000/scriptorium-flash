# Findings

Every number this project produces lives here and nowhere else. The README, the
ADRs, and the talk cite this file. Nothing numeric gets retyped by hand
somewhere else, because retyped numbers drift.

Rules for entries:

- **Measured, not estimated.** If a number is an estimate, it says so and says
  what it is an estimate of.
- **Dated**, newest first.
- **Sourced.** Every number names the file, log, or page it came from, so it can
  be checked.
- Runpod costs are real money. Every cent is logged, including zero.
- Claude Code usage figures are estimates of usage against a Claude Max
  subscription. They are **not charges** and are labelled as such.

---

## Runpod spend ledger

| Date | What | Cost | Source |
|---|---|---|---|
| 2026-08-17 | Cycle 2, entire cycle — read-only account queries only | $0.00 | `runpodctl billing {pods,serverless,network-volume}`, all-time window, all return `[]` |
| 2026-08-17 | Cycle 3, task 1 — `hello-flash` deployed, 4 requests, deleted after 458 s | **$0.0066245833** | `clientBalance` $49.9945861833 → $49.9879616000, settled and re-read |
| 2026-08-17 | Cycle 3, task 3 — 26 hosted text-model calls across two models, plus parameter and schema isolation | **$0.0838488300** | `clientBalance` $49.9879616000 → $49.9041127700; cross-checked against the endpoints' own `cost` fields |

**Total Runpod spend to date: $0.0904734133**

Cycle 2 spent nothing: all three billing categories returned `[]` over an
all-time window and `clientBalance` never moved.

**Two different instruments are needed for Cycle 3's spend, because neither one
works everywhere.**

*Serverless* spend has to be read off the balance. `runpodctl billing serverless`
returns `[]` over both today's window and an all-time window despite a charge
that demonstrably occurred, so the billing-history API cannot corroborate
anything at this scale.

*Public-endpoint* spend is the opposite: the endpoint's own `cost` field in each
response is exact — `total_tokens ×` the published rate, verified to the cent on
two models — while the balance is a poor instrument for it because **it lags
charges by several minutes.**

That lag caused a wrong number earlier in this cycle. A reading taken sixty
seconds after the last call, and confirmed "stable", reported roughly a third of
the real spend and supported a confident claim that this account was billed 3.26×
under list price. It is not; there is no discount. A stable balance reading is
not a settled one, and the only safe balance comparisons in this file are the
ones taken minutes apart with nothing running in between.

Cycle 2's gates were never reached, because `flash` could not authenticate.
Cycle 3's are live.

---

## 2026-08-17 — Cycle 3

### Account baseline, re-read at the start of the cycle

`runpodctl user`, free read-only query. Every Cycle 3 cost is measured against
this line.

| Field | Value |
|---|---|
| `clientBalance` | **$49.9945861833** |
| `currentSpendPerHr` | $0 |
| `spendLimit` | $80 |
| Serverless endpoints (`runpodctl serverless list`) | `[]` |
| Container-registry credentials (`runpodctl registry list`) | `null` |
| Flash apps (`flash app list`) | none |

**Unchanged to the last decimal place from Cycle 2's closing reading.** Both CLIs
now authenticate against one `~/.runpod/config.toml`, which after `flash login`
carries a top-level `apikey` **and** a `[default].api_key`, both 50 characters.
Neither value has been read by this project.

### The credential defect is filed

**[runpod/flash#363](https://github.com/runpod/flash/issues/363)** — `flash`
cannot read a `~/.runpod/config.toml` written by `runpodctl`; the error suggests
exporting the key instead.

Filed on `runpod/flash`, the public repository behind the `runpod-flash` package.
No duplicate existed. Three corrections to the Cycle 2 draft were made before
filing; they are in [AI-ASSIST.md](AI-ASSIST.md) under "Cycle 3: the credential
issue, filed". The one that matters most for the record: **Runpod's
documentation never claims the two CLIs interoperate.** That claim is in Runpod's
shipped agent skills, a different artifact in a different repository, and the
issue attributes it there.

Draft issues 2 (container disk billing at zero workers) and 3 (whether an
`idle`/`ready` worker bills) stay unfiled until their measurements land.

### Hello-world: the first thing this project ever deployed

One Flash app, `hello-flash`, unchanged from Cycle 2 — `GpuGroup.AMPERE_16`,
`workers=(0, 1)`, `idle_timeout=60`, no dependencies, a 0.2 MB artifact of two
files. It echoes its input. The point is the three numbers.

| | Value |
|---|---|
| Endpoint id | `qb4qjquyist574` (first deploy) |
| Deployed | 2026-08-17T19:41:35Z |
| Deleted | 2026-08-17T19:49:13Z |
| **Cold start — first request** | **31.387 s** |
| **Warm request median** | **0.354 s** (n=3: 0.437, 0.320, 0.354) |
| Worker | `d5571d1c3f08` |
| **Verified cost** | **$0.0066245833** |

Cold start is caller-observed wall clock on the first request: the whole
exchange, which is what a caller actually waits for. All four calls returned 200.

**Cost is verified against the account balance, and only against the balance,
because the billing history could not corroborate it.** See "The billing history
API did not show a charge that demonstrably happened" below.

| | |
|---|---|
| `clientBalance` before | $49.9945861833 |
| `clientBalance` after, settled | $49.9879616000 |
| **Difference** | **$0.0066245833** |

At the 16 GB tier's **$0.58/hr** — confirmed live on runpod.io/pricing during
this cycle — that difference is **41.12 billed-equivalent seconds**.

The estimate at the gate was $0.02–0.03 for roughly 90–150 s of worker life. The
actual was **$0.0066**, about a quarter of the low end. The reason is in the next
section, and it is the most useful thing this deployment produced.

### Two separate claims about idle, and the pair is the finding

These get stated apart because conflating them is how the wrong conclusion gets
drawn, and Cycle 2 drew it from documentation alone.

**Claim 1 — the platform claim: an endpoint at zero workers bills nothing.**
Still believed, still consistent with everything measured. Nothing here
contradicts it.

**Claim 2 — the tool behaviour: `flash` does not give you zero workers.**
`Endpoint(workers=(0, 1))` is documented as `(min, max)`, and this repo's entire
scale-to-zero cost argument rests on it. What it actually deploys, read from the
REST API:

```
workersMin: 0     workersMax: 1     workersStandby: 1
```

`workersStandby` is the API field behind what the console calls **active
workers**, which `docs.runpod.io/serverless/endpoints/endpoint-configurations`
describes as "Minimum number of workers that remain warm and ready at all times"
and says "incur charges continuously, including when idle."

**`runpodctl` does not report `workersStandby` at all.** Neither
`runpodctl serverless list` nor `runpodctl serverless get <id>` includes the
field, so nothing in the CLI would reveal it. It took a direct
`GET https://rest.runpod.io/v1/endpoints` call to see it.

**It reproduces.** A second, independent deploy of the same unchanged app
produced `workersStandby: 1` again (endpoint `ivmpm73jnh01jw`, created
2026-08-17T19:57:02Z).

**Observed behaviour matches.** Across four minutes of polling with zero jobs
ever queued, the worker never scaled to zero — it oscillated between `running`
and `idle`/`ready` well past the 60-second idle timeout.

So the honest statement is: **zero workers costs nothing, and `flash
workers=(0, 1)` does not give you zero workers.** Either half alone is
misleading.

### What the 41.12 billed seconds does *not* mean

The endpoint existed for **458 seconds** and billed the equivalent of **41.12
seconds — 9.0% of its lifetime**. Caller-observed request time across all four
calls was 32.498 s.

**So the standby worker did not bill continuously**, and the reading that
Cycle 2 took from the documentation — that a warm worker bills for every second
it is warm — is not what this account was charged. That is a measurement against
one short window, not a law, and what the remaining ~8.6 s covers is not yet
pinned down. A longer window with the phases separated is running now; its result
and the arithmetic go in the idle-billing section.

Until then this is recorded as an open question, not an answer, and **draft issue
3 stays unfiled** — the measurement it was waiting for now points the opposite
way from the draft, which is precisely the case the cycle rules say must not be
filed.

### Hosted text models: 26 real calls, 0 clean parses, and a fixable reason

The question was whether moving Scriptorium's text steps — 41.7% of a `pg-41`
bake and its largest bucket — to a Runpod **public endpoint** is a URL swap or a
bigger change.

**It is a bigger change. It is also achievable, and the blocker is specific
enough to name.**

Home does not ask a model politely for JSON. `text-transform-service/src/tts/llm.py`
passes each transform's full JSON Schema to Ollama's `format` field, which is
grammar-constrained decoding — the model *cannot* emit anything off-schema. The
question was whether any equivalent exists on a public endpoint. No Runpod page
documents one.

Test: the real `cast-mentions` transform v0.3.0, imported from the running
text-transform-service source rather than copied, against ten real `pg-41`
pages. A parse is clean only if the pipeline's own `_attempt_reason()` accepts
it — `json.loads` **and** `jsonschema.validate` against the transform's schema.

#### The catalogue moved under us mid-cycle

Cycle 2 enumerated seven priced text endpoints from the documentation. Live:

| Slug | Documented in | Result |
|---|---|---|
| `cogito-671b-v2-1-fp8-dynamic` | `docs.runpod.io/public-endpoints/models/cogito-671b` | **404** |
| `qwen3-32b` | the live reference page | **404** |
| `granite-4` | the live reference page | **404** |
| `moonshot-kimi` | — | 200 → `kimi-k2.6`, `kimi-k2.7-code`, `kimi-k3` |
| `qwen3-32b-awq` | *not on the reference page* | 200 → `Qwen/Qwen3-32B-AWQ` |

**Cogito was priced in Cycle 2 at $0.50/1M and was gone from the catalogue the
same day.** It was this cycle's chosen model on the strength of that price — 20×
cheaper than the alternatives — and it now returns `endpoint not found`.

That is a production risk, not a documentation nit. A per-token dependency whose
cheapest model can be withdrawn between one day and the next has no price floor
a cost model can rest on, and the withdrawal is silent: a 404 at request time is
the first notice. Anything built on a public endpoint needs a fallback model and
an alerting path for `404`, which is work that a "URL swap" framing hides.

**The reference page also conflates two different identifiers.** It lists
"model slugs" in one column, but `kimi-k2.6` is a *model id* passed in the
request body, and the *endpoint slug* that serves it is `moonshot-kimi`. Using
the documented value as a slug returns 404. Two of the three text slugs the page
does list are dead, and the one working Qwen endpoint is not on it.

#### Neither model returned anything the pipeline could parse

| | `kimi-k2.6` | `Qwen/Qwen3-32B-AWQ` |
|---|---|---|
| Calls | 10 | 2 |
| HTTP 200 | 10 | 2 |
| **Clean parses** | **0** | **0** |
| Latency median | **13.106 s** | 27.9 s and 59.3 s |
| Cost | $0.040734 | $0.039080 |

Home's `cast-mentions` median is **2.877 s**. The hosted models are **4.5× to
20× slower per call** on the identical prompt.

**They failed in two different ways, and neither is "the model is bad".**

`kimi-k2.6` is a reasoning model. Every one of the ten calls returned
`finish_reason: length` with **699 of its 700 output tokens spent on
`reasoning_content` and zero characters of `content`**. Home's `num_predict` of
700 is not a budget this model can work inside — it thinks past it every time,
and the account pays for all 7,000 wasted tokens.

`Qwen/Qwen3-32B-AWQ` emits its chain of thought **into `content`** as a `<think>`
block when nothing constrains it, so the response fails at character 1. Of two
calls, one produced JSON missing a required property and one produced 3,036
characters that were not JSON.

#### Structured output does exist, and it is undocumented

No Runpod page mentions it. All four mechanisms work on the vLLM-backed
endpoint, tested against a simple schema:

| Parameter | Result |
|---|---|
| none | 200 — but `content` begins `<think>` |
| `response_format: {type: json_object}` | **200** — `{"ok":true}` |
| `response_format: {type: json_schema}` | **200** — `{"ok":true}` |
| `response_format: {type: json_schema, strict: true}` | **200** — `{"ok":true}` |
| `guided_json` (vLLM native) | **200** — `{"ok":true}` |

So the constraint mechanism Scriptorium needs is available on
`qwen3-32b-awq` — it is simply written down nowhere.

#### But Scriptorium's actual schema does not compile

Bisected one feature at a time, same endpoint, same prompt:

| Schema | Result |
|---|---|
| array of strings | 200 |
| + nested objects | 200 |
| + `additionalProperties: false` | 200 |
| + `maxItems` | 200 |
| **+ `minLength` / `maxLength` on a string** | **HTTP 500 after 60.5 s** |
| the real `cast-mentions` schema | **HTTP 500** |

**String length bounds are the breaking feature.** The failure is an opaque
`{"status":500,"title":"Internal Server Error"}` after a minute of apparent
work — no diagnostic naming the schema, no hint that a constraint is
unsupported.

`cast-mentions`'s schema uses `minLength: 1` and `maxLength: 60` on `name`,
`maxLength: 60` on aliases and `maxLength: 140` on descriptors.

**So the migration is a specific, bounded piece of work**: send a wire schema
with the string bounds stripped, keep the full schema for local validation after
the response arrives. That is a change to text-transform-service, not a URL swap
— but it is a day's work, not a rewrite.

#### One more thing that returns 500: ordinary sampling parameters

On `moonshot-kimi`, **`temperature` and `top_p` each cause HTTP 500**,
independently. Isolated with minimal requests:

| Body | Result |
|---|---|
| `messages` + `max_tokens` | 200 |
| + system message | 200 |
| + `temperature: 0.2` | **500** |
| + `top_p: 0.8` | **500** |
| + both | **500** |
| `max_tokens: 700`, no sampling | 200 |

Two of the most basic OpenAI parameters, on an endpoint advertised as
OpenAI-compatible, with the same opaque error body. Home runs every transform at
a deliberate `temperature` — `cast-mentions` at 0.2 — so this endpoint cannot
reproduce home's sampling at all.

#### Does per-token usage draw down the credit? Yes.

Cycle 2 could not settle this and leaned on a $0.0054 shortfall as circumstantial
evidence. Settled now: **the balance moves.** It fell from $49.9879616000 to
$49.9078527700 across this task's calls. Runpod's credit pays for public-endpoint
tokens, and Cycle 2's reading of that shortfall was right.

#### Cost, and a correction to how it was measured

**The endpoint's own `cost` field is exact.** It equals `total_tokens ×` the
published rate, verified on both models — Kimi reported $0.040734 for 13,404 in
and 7,000 out at $0.95/$4.00 per 1M, which is the list arithmetic to the cent.

**An earlier reading in this cycle claimed the account was billed 3.26× under
list price. That was wrong, and the error was in the method.** The probe read
`clientBalance` sixty seconds after the last call and treated a stable reading as
a settled one. Runpod's balance lags charges by several minutes, so an early read
reports a fraction of the spend and then stops changing, which looks exactly like
a settled number. Corrected: there is no discount, and the tool now reports the
endpoint's `cost` field as authoritative with the balance quoted only as a
lagging cross-check.

**Extrapolated to one full `pg-41` bake** — 55 text calls (20 `cast-mentions`,
20 `scene-update`, 9 `illustration-prompt`, 6 `cast-canonicalize`):

| Model | Rate | Per full bake | Note |
|---|---|---:|---|
| `Qwen/Qwen3-32B-AWQ` | $10.00/1M blended | **$1.07** | the only one that can be constrained |
| `kimi-k2.6` | $0.95 in / $4.00 out | **$0.22** | for 55 responses containing nothing |
| Home `qwen3.5:9b` | — | **$0.00** | marginal; the GPU is already owned |

Both are over-estimates: they scale `cast-mentions`, which carries the largest
`num_predict` of the four transforms.

#### Verdict

**Moving the text steps is a bigger change than a URL swap.** Four things have to
be true that are not true today, and only the first is really about code:

1. The wire schema must drop `minLength`/`maxLength`, with full validation moved
   after the response. Bounded work.
2. `response_format` has to be sent on every call, because unconstrained output
   is `<think>` prose and parses at 0%.
3. The pipeline must tolerate a model catalogue that changes without notice, with
   a fallback and a 404 alarm.
4. Someone has to accept **$1.07 a book** against $0.00 at home, and **4.5–20×
   the latency** on the step that is already the largest bucket in the bake.

The image steps are the opposite case: a GPU Scriptorium does not own, doing work
it cannot parallelise locally. The text steps are cheap and fast at home and get
expensive and slow hosted. On this evidence **the text steps should stay local**,
and that is a more useful answer than the one this cycle set out to confirm.

### The billing history API did not show a charge that demonstrably happened

`runpodctl billing serverless` returns `[]` — over today's window with hourly
buckets, and over an all-time window with monthly buckets — while the account
balance dropped $0.0066245833 for serverless work in that same period.

That matters beyond bookkeeping. This project's rule is that every cent is
verified against billing records. For serverless spend at this scale, **the
billing-history API cannot do that job**, and the balance — read to ten decimal
places — is the only instrument that works. Every cost in this cycle is therefore
sourced to a balance delta, with the billing history quoted alongside as
corroboration where it has any to offer.

Whether the charge posts to the history later, or whether sub-cent serverless
usage never appears there, is not yet established.

### Three smaller things the deployment taught

**`ready` does not mean ready.** The platform health route reported
`workers: {idle: 1, ready: 1}` *before* the first request, and that request still
paid the full 31.387 s cold start. A caller cannot use `ready` to predict
latency.

**`NVIDIA_VISIBLE_DEVICES` is worthless for identifying the card.** It returned
the literal string `void`. This was going to be `flash-imagegen`'s only record of
which GPU ran a plate, on a tier that can hand out more than one model of card.
Fixed — the render handler now reads the device name from ComfyUI's
`/system_stats` instead. Recorded here because the defect was ours and the
evidence for it came from this deployment.

**The endpoint is a load balancer, and the job counters stay at zero.**
`jobs: {completed: 0, …}` never moved despite four successful requests, because
load-balanced routes are not queue jobs. Anyone reading `completed` as "requests
served" on a Flash LB endpoint will read zero forever.

---

## 2026-08-17 — Cycle 2

### Account baseline, before any spend


Read with `runpodctl user` and `runpodctl billing`, both free read-only queries.
This is the reference point every later cost in this cycle is measured against.

| Field | Value |
|---|---|
| `clientBalance` | **$49.9945861833** |
| `currentSpendPerHr` | $0 |
| `spendLimit` | $80 |
| Billing history — pods | `[]` |
| Billing history — serverless | `[]` |
| Billing history — network volumes | `[]` |

The billing histories are empty over an all-time window
(`--start-time 2024-01-01T00:00:00Z --end-time 2026-08-18T00:00:00Z
--bucket-size month`), not merely over the default one-day window. So nothing has
ever been charged to this account for pods, serverless, or network volumes.

**One thing this does not explain, recorded rather than guessed at.** The balance
is **$0.0054138167 short of a round $50.00**. Three categories of billing history
are empty, so that difference did not come from a pod, an endpoint, or a volume.
Two candidates: the credit was never exactly $50.00, or something was spent in a
category `runpodctl` cannot report. The only category it cannot report is
per-token **public endpoint** usage — there is no
`runpodctl billing public-endpoints` subcommand, though the REST API has
`get-public-endpoint-billing-history`.

That matters beyond bookkeeping: **if that $0.0054 was a public-endpoint charge,
it is direct evidence that this account's credit does pay for per-token
billing**, which is the Task 5 question the documentation cannot answer. It is a
lead, not an answer, and it is not counted as this project's spend — it predates
Cycle 2's first command.

### Sleepy Hollow — ingest integrity, checked before baking

Cycle 1 established the rule: verify ingest against the source before spending
any GPU time, because *Usher* silently lost 48% of its text and reported no
warnings. Sleepy Hollow was not previously ingested, so it was created fresh and
checked.

| Field | Value |
|---|---|
| Book | *The Legend of Sleepy Hollow* |
| Author | Washington Irving |
| Source | Project Gutenberg ebook #41 |
| Source words | **12,214** (after Project Gutenberg boilerplate is stripped) |
| Stored words | **12,187** |
| **Retention** | **99.78%** |
| Pages after pagination | 20 |
| Chapters detected | 2 |
| Ingest warnings | `[]` — none |
| Scriptorium book id | `pg-41` |

Source count measured the same way as Cycle 1: fetch
`https://www.gutenberg.org/ebooks/41.txt.utf-8`, cut everything outside the
Project Gutenberg START/END markers, count whitespace-separated tokens. Stored
count is the sum of the 20 page word counts in
`scriptorium-data/work/pg-41/pages/*.json`.

**The chapter-detection bug did fire, and it cost 27 words, none of them prose.**
This needs stating carefully, because "99.78%" could hide a real loss.

The warnings array is empty, and that is the *bad* sign rather than the good one.
`chapters_undetected` — the warning *Yellow Wallpaper* produced — only fires when
detection finds nothing and the whole-text fallback keeps everything. Its absence
means detection succeeded and `_chapters_from_headings` ran, which is the path
that drops text. Two headings were detected, both all-caps lines:
`FOUND AMONG THE PAPERS OF THE LATE DIEDRICH KNICKERBOCKER.` and
`FOUND IN THE HANDWRITING OF MR. KNICKERBOCKER.`

Every one of the 27 missing words is accounted for:

| Words | Text | Why it went |
|---:|---|---|
| 8 | `The Legend of Sleepy Hollow by Washington Irving` | precedes the first detected heading, so it falls outside every chapter |
| 9 | `FOUND AMONG THE PAPERS OF THE LATE DIEDRICH KNICKERBOCKER.` | became a chapter title in `structure.json` rather than body text |
| 7 | `FOUND IN THE HANDWRITING OF MR. KNICKERBOCKER.` | same |
| 1 | `POSTSCRIPT.` | classed as heading-ish |
| 2 | `THE END.` | classed as heading-ish |
| **27** | | **sums exactly to the measured shortfall** |

Not one word of narrative prose is among them. `CASTLE OF INDOLENCE.` — the
epigraph's attribution — was *not* detected as a heading and survives in the body.

Spot-checks both pass. The stored text opens `A pleasing land of drowsy head it
was, Of dreams that wave before the half-shut eye…` and closes `…“as to that
matter, I don't believe one-half of it myself.” D. K.`

**One incidental benefit.** Because the title-and-byline line was dropped,
Washington Irving cannot be mistaken for a character. *Yellow Wallpaper* kept its
byline inside page 1 and the cast stage duly picked up "Charlotte Perkins
Gilman" as a person in the story. The same defect that loses 8 words here
prevents a worse defect downstream.

**Verdict: pass.** Retention 99.78% against a 99.5% threshold set in advance,
with every missing word identified and none of it prose. Recorded, not fixed —
the defect belongs to Scriptorium and is out of scope this cycle.

### Sleepy Hollow — plate count

**9 plates in the measured run**, inside the settled 8–12 target. Read from
`selection.plates`, which is what the selection engine wrote.

| Reason | Count | Pages |
|---|---:|---|
| `chapter_open` | 2 | 0001, 0020 |
| `fill` | 5 | 0003, 0006, 0008, 0011, 0013 |
| `scene_boundary` | 2 | 0015, 0018 |

Selection parameters, unchanged from Cycle 1: preset `lavish`, `min_gap` 1,
`max_gap` 3, `salience_floor` 0.40, `chapter_open` and `scene_boundary` both on.

**The plate count is not deterministic, and that is worth knowing before anyone
cites it.** The pre-flight probe of the same book with the same settings selected
**10** plates; the measured run selected **9**. Nothing was changed between them.
The cause is upstream: `scene-update` and `cast-mentions` are language-model calls
run at `temperature` 0.2, so the per-page salience scores differ slightly from run
to run, and selection marks pages by comparing salience against
`salience_floor` and each other. Both runs landed inside 8–12, and the two
`scene_boundary` pages (0015, 0018) and both chapter openers were identical across
runs — it is the gap-filling positions that moved.

So the honest claim is **"Sleepy Hollow yields 9–10 plates at `lavish`"**, not a
single number, and the figure quoted alongside any timing is the one from that
same run.

**It is a better standard story than Yellow Wallpaper, not merely a longer one.**
Yellow Wallpaper produced 5 plates of which 4 were gap-filling, because a
first-person diary set in one room gives the selection engine almost no scene
changes to find. Sleepy Hollow contributes 2 genuine `scene_boundary` marks and 2
real chapter openers, so 4 of its 9 plates are chosen by content rather than by
spacing arithmetic.

### An observation about the cast, because it affects the render count

Cast canonicalization left 21 characters, 6 of them marked major, and the major
six are what get portraits. Several entries are plainly the same person:
`brom-bones`, `redoubtable-brom-bones` and `bones`; `van-tassel`,
`balt-van-tassel`, `old-baltus-van-tassel` and `mynheer-van-tassel`;
`headless-horseman`, `galloping-hessian` and `galloping-hessian-2`.

This is recorded because it is load-bearing for the numbers, not as a complaint:
portrait count follows the major-cast count, portraits are renders, and renders
are what the Runpod comparison measures. A different canonicalization would
change the total render count without changing the per-render time. It is a
Scriptorium quality issue, out of scope this cycle, and it was not touched.

### Baseline: the home bakery on Sleepy Hollow, end to end

One complete bake of `pg-41`, run unchanged on its normal home setup. Scriptorium's
source was not touched and its deployed configuration was not modified. Both human
review gates were cleared by the driver the instant they opened, so gate wait is
effectively zero and machine time equals wall clock.

Same hardware and models as Cycle 1: one NVIDIA RTX 5070 with 12 GB of video
memory, text model `qwen3.5:9b` served by Ollama behind text-transform-service,
image model `sd_xl_base_1.0` served by ComfyUI behind imagegen-service. Bake
settings: density preset `lavish`, `images_per_scene: 1`, portraits enabled,
portrait review off, style `oil-painting`, era `1790s Hudson Valley`.

**Wall clock: 388.63 s (6 min 29 s). Gate wait: 0.009 s.**

| Bucket | Time | Share |
|---|---:|---:|
| Text steps | 162.20 s | 41.7% |
| Image rendering | 123.34 s | 31.7% |
| Orchestration | 71.89 s | 18.5% |
| Model loading | 31.19 s | 8.0% |
| **Total** | **388.63 s** | **100%** |

Model loading is reported separately but happens *inside* the other two. Including
it, text steps took 165.49 s gross and image rendering 151.24 s gross.

**Text steps — 55 model calls, 162.20 s net**

| Transform | Calls | Total | Median |
|---|---:|---:|---:|
| `cast-mentions` | 20 | 59.86 s | 2.877 s |
| `scene-update` | 20 | 63.54 s | 2.946 s |
| `illustration-prompt` | 9 | 26.42 s | 2.523 s |
| `cast-canonicalize` | 6 | 15.67 s | 1.791 s |

All 55 returned 200. Call counts match artifact counts exactly (20 / 20 / 6),
which is how the measurement window is confirmed correct.

**Image rendering — 16 renders, 123.34 s net**

Warm render median **7.595 s** at 832×1216 (n=8). All 16 renders were attributed
to this bake and none were left unclaimed; pairing gap p50 was 0.38 s, max
0.592 s. The 16 are 9 plates, 6 character portraits at 1024×1024, and 1 cover.

**Model loading — 31.19 s**

| Cause | Count | Each | Total |
|---|---:|---:|---:|
| Image model reloaded after the orchestrator freed the GPU | 1 | 8.195 s | 8.20 s |
| Image model re-staged under video-memory pressure | 7 | 2.815 s | 19.71 s |
| Text model loaded cold | 1 | — | 3.29 s |

The orchestrator freed the GPU 4 times and unloaded the text model 3 times.
Incidental re-staging — ComfyUI evicting and restoring the image model under
12 GB of pressure — happened 7 times in 16 renders and again cost more than the
deliberate swapping did.

**Orchestration — 71.89 s**

| Component | Time |
|---|---:|
| Idle between phases (11 gaps, 5 s runner tick) | 34.11 s |
| Generating web and thumbnail derivatives | 6.95 s |
| Everything else (HTTP, artifact writes, ingest, publish) | 30.83 s |

Machine-readable output: `runs/pg-41/timing.json`. Driver log: `runs/pg-41/run.json`.
Collector integrity flags: counts match artifacts, residual non-negative, no
foreign transforms in the window, no warnings.

### Sleepy Hollow against Yellow Wallpaper — the constants hold

The point of re-measuring is not the wall clock, which obviously grows with a
longer book. It is whether the *derived* per-render constants reproduce.

| | `pg-1952` | `pg-41` | Difference |
|---|---:|---:|---:|
| Words | 6,085 | 12,187 | +100% |
| Pages | 11 | 20 | +82% |
| Plates | 5 | 9 | +80% |
| Renders | 12 / 12 | 16 / 16 | — |
| Text calls | 33 | 55 | +67% |
| Wall clock | 289.39 s | 388.63 s | +34% |
| **Warm render median** | **7.615 s** (n=6) | **7.595 s** (n=8) | **−0.3%** |
| Re-stage penalty | 2.795 s | 2.815 s | +0.7% |
| Reload-after-free penalty | 10.565 s | 8.195 s | −22% |
| GPU free events | 4 | 4 | — |

**The warm render median agrees to within 0.3% across two different books.** With
Cycle 1's two reference bakes (`pg-75201` at 7.44 s, `pg-28054` at 7.49 s) that is
four independent measurements of the same constant spanning 7.44–7.615 s. **7.6 s
per 832×1216 plate is a sound number to hold Runpod against.**

Two things did move, and both are explainable rather than noise:

- **Reload-after-free dropped 22%** (10.565 s → 8.195 s). It is a single event in
  each run, so it is one sample, not a median — a 2 s spread on one cold load is
  not a finding.
- **Text steps went from 28.6% of the run to 41.7%**, and the per-call medians rose
  (`cast-mentions` 1.869 s → 2.877 s). Sleepy Hollow's pages are longer (609 words
  average against 553) and it has 21 cast members against Yellow Wallpaper's
  smaller cast, so each call carries more input and returns more output. This is
  the more interesting shift for the migration: **on this book the text steps are
  now the largest bucket, larger than image rendering.**

**What that means for the Runpod plan.** Image generation — the part moving to
Flash first — is 31.7% of this run, close to Cycle 1's 32.8%. But text steps are
now 41.7%. Moving rendering to Runpod addresses the second-largest bucket, not the
largest. The hosted per-token endpoints in Task 5 matter more than Cycle 1's
numbers suggested.

### The standard comparison story is now Sleepy Hollow

Locked. Every home-versus-Runpod measurement from here uses this book.

| Field | Value |
|---|---|
| Book | *The Legend of Sleepy Hollow* |
| Author | Washington Irving |
| Source | Project Gutenberg ebook #41 |
| Source words | 12,214 |
| Stored words | 12,187 (99.78% retention) |
| Pages | 20 |
| Plates | 9–10 at `lavish` (9 in the measured run) |
| Renders | 16 (9 plates + 6 portraits + 1 cover) |
| Scriptorium book id | `pg-41` |
| Bake settings | `lavish`, `images_per_scene: 1`, portraits on, portrait review off, `oil-painting`, era `1790s Hudson Valley` |

It replaces *The Yellow Wallpaper*, which is **superseded, not deleted** — its
numbers below are the evidence for the 7.6 s constant and remain citable as such.
The reason for the change is the plate count: the brief asked for a story yielding
8–12 plates, Yellow Wallpaper produced 5 and structurally could not do better, and
Sleepy Hollow produces 9–10 with 4 of them chosen by content rather than spacing.

### Tooling versions these numbers came from

| Tool | Version |
|---|---|
| `runpodctl` | `2.9.0-c094cac`, installed from the pinned GitHub release, SHA256 verified against `checksums_2.9.0_sha256.txt` |
| `flash` | `Runpod Flash CLI v1.19.0` (`runpod-flash` 1.19.0 on Python 3.13) |

### Key check result

| Tool | Reads the installed `~/.runpod/config.toml`? |
|---|---|
| `runpodctl` | **Yes.** `runpodctl user` returns the account record with nothing set in the environment. |
| `flash` | **No.** Every account-touching subcommand fails with `RunpodAPIKeyError`. |

The cause is a format mismatch, not a missing key: `runpodctl` uses a top-level
`apikey`, while `flash` requires a `[default]` table containing `api_key`. Full
diagnosis and the draft issue are in [AI-ASSIST.md](AI-ASSIST.md); the practical
consequence is in [hello-flash/README.md](hello-flash/README.md) under "Two CLIs,
one file, two formats".

**This blocks deployment.** Nothing that needs `flash` can run until `flash login`
is done once, interactively, in a browser. No workaround was attempted, because
every remedy the CLI itself suggests requires extracting the plaintext key.

### Does an idle Flash app with zero workers bill anything?

**No — provided no network volume is attached and minimum workers is 0.**

The question was asked specifically about container storage, because Runpod's
serverless pricing page lists container disk as its own cost line with a
"(5-min intervals)" qualifier, which reads like something that accrues on a timer
whether or not anything is running. It does not.

**The decisive sentence is on a different page from the price.**
`docs.runpod.io/serverless/storage/overview` describes container disk as
"Temporary storage that exists only while a worker is running", and gives its cost
as "**included in the worker's running cost**". So container storage is not a
separate meter that outlives the worker; it is part of the worker's per-second
charge. At zero workers there is no worker cost, so there is no container storage
cost, because there is no container.

Two further statements agree:

- `docs.runpod.io/serverless/workers/overview` — flex workers "cost nothing when
  not in use."
- `docs.runpod.io/pods/pricing` — the only Runpod table that says it outright:
  container disk is "**Not charged**" on a stopped Pod. Network volume, in the same
  table, costs the same stopped or running.

**On the five-minute interval specifically**, there are two different statements
and conflating them is the trap:

1. `docs.runpod.io/accounts-billing/billing` — "Billing runs every 5 minutes, and
   charges are deducted continuously based on the resources you have running."
   That is the account-wide ledger sweep, and it is scoped to *running* resources.
   At zero workers the sweep finds nothing to charge.
2. `docs.runpod.io/serverless/pricing`, container-disk row — "Worker storage
   (5-min intervals)". That parenthetical is the entire text on the subject, and it
   is never defined anywhere.

**So container storage's 5-minute billing does not apply at zero workers, because
container storage does not exist at zero workers.**

**The one thing that does bill at idle is a network volume.** Charged continuously,
stopped or running, at $0.07/GB/month under 1 TB. Flash's `NetworkVolume` defaults
to 100 GB, so attaching one would burn about **$7.00 a month** whether or not a
single request ever arrived. That is why the production image-generation app fetches
its weights at build time instead of mounting them.

**Decision: leave the app deployed.** Tearing it down buys nothing and costs a
rebuild.

**The empirical half is not done, and the answer above is documentary only.** The
brief asked for confirmation against the account's real billing records after a
deployment. Nothing has been deployed, because `flash` cannot authenticate (above),
so there is no idle window to measure. What the check would look for is recorded
now so it can be run without re-deriving it:

> If Flash's default 64 GB container disk *were* billed at zero workers,
> $0.10/GB/month would accrue **$0.0089/hr** — so a three-hour idle window should
> show about **$0.027** against `runpodctl billing serverless`, which is clearly
> distinguishable from $0.00. Read `runpodctl billing serverless` and
> `runpodctl billing network-volume` at deploy time and again after the window,
> and record the achieved idle duration alongside the result.

### Runpod's hosted per-token text models

Runpod calls these **Public Endpoints**: models Runpod operates, billed per token,
with nothing to deploy, no workers to scale, no cold start you own and nothing to
tear down. Enumerated from the documentation, free. **No call was made** — see the
end of this section.

Base URL `https://api.runpod.ai/v2/{slug}`. Two request shapes: a native
`/runsync` that wraps arguments in an `input` object, and an OpenAI-compatible
`/openai/v1/chat/completions`.

| Model | Model id | Input /1M | Output /1M |
|---|---|---:|---:|
| Cogito 671B v2.1 FP8 | `cogito-671b-v2-1-fp8-dynamic` | $0.50 blended | |
| Moonshot Kimi k2.6 | `kimi-k2.6` | $0.95 | $4.00 |
| Moonshot Kimi k2.7-code | `kimi-k2.7-code` | $0.95 | $4.00 |
| Moonshot Kimi k3 | `kimi-k3` | $3.00 | $15.00 |
| Qwen3 32B AWQ | `Qwen/Qwen3-32B-AWQ` | $10.00 blended | |
| GPT-OSS 120B | `openai/gpt-oss-120b` | $10.00 blended | |
| IBM Granite 4.0 | `granite-4-0-h-small` | $10.00 blended | |

"Blended" means the documentation quotes one rate covering input and output
together; only the Kimi models publish a split. Source:
`docs.runpod.io/public-endpoints/reference` and the per-model pages under
`docs.runpod.io/public-endpoints/models/`.

Two documented facts that matter for cost modelling: **failed generations are not
charged**, and there is **no idle cost**, because nothing is deployed.

### Which of them could do Scriptorium's text steps

The three text steps are `cast-mentions` (who is on this page), `scene-update`
(what changed) and `illustration-prompt` (what a picture of it should show). All
three send roughly a page of prose and expect short structured JSON back.

Home does this with `qwen3.5:9b` at Q8_0 through Ollama. Measured on the `pg-41`
baseline above: 55 calls, medians 1.791–2.946 s, `temperature` 0.2–0.5,
`num_predict` 350–700, and input around 570–770 estimated tokens per call. That is
an instruction-following job, not a reasoning-heavy one, so **none of these models
is short of capability** — the choice is about price and output discipline.

- **Cogito 671B v2.1** — $0.50/1M blended, 20× cheaper than the $10 tier. The
  value pick.
- **Qwen3 32B AWQ** — $10.00/1M, documented for "reasoning, instruction-following,
  agent capabilities". Same model family as the one home already runs, which makes
  it the most likely to behave similarly on prompts that were tuned against
  `qwen3.5:9b`. That is worth something real when the prompts are not being
  rewritten.
- **Kimi k2.6** — $0.95 in / $4.00 out. Wins when output is short relative to
  input, which is this workload's shape.

**A rough cost sketch, from the baseline's measured token counts.** 55 calls at
roughly 700 input and 300 output tokens is about 38,500 input and 16,500 output
tokens per book. At Cogito's $0.50/1M blended that is **about $0.03 per book**. At
the $10/1M tier it is **about $0.55 per book**. Both are estimates from published
prices against measured call counts, not charges, and the token figures are
Scriptorium's own estimator (`TOKENS_PER_WORD = 1.35`), not a tokenizer.

**The gap that matters more than price.** No Runpod page documents JSON mode,
`response_format`, or grammar-constrained decoding for public endpoints.
Scriptorium's transforms need parseable JSON and currently get it from a local
Ollama that can constrain output. Moving those steps to a public endpoint means
relying on the prompt alone unless the OpenAI-compatible route happens to accept
`response_format` undocumented. That is a functional risk, not a cost one, and it
is the thing to test first.

### Do the assignment credits cover per-token billing?

**Not established from the documentation — and the documentation is the wrong place
to settle it.** What exists:

- Billing docs say credits "can only be used for Runpod services": a restriction
  *to* Runpod, with no carve-out excluding any product line.
- There is a first-class `get-public-endpoint-billing-history` REST endpoint, which
  puts public-endpoint spend in the same billing-history family as pods, serverless
  and volumes, implying one shared ledger.
- But the single sentence enumerating what credits are spent on says "Pods,
  Serverless endpoints, and storage" and omits public endpoints, and the word
  "promotional" does not appear in the billing documentation at all.

**The account itself is better evidence than the docs, and it points to yes.** The
pre-spend baseline at the top of this cycle shows a balance $0.0054138167 below a
round $50.00 with all three `runpodctl billing` categories empty over an all-time
window. The one spend category `runpodctl` cannot report is per-token
public-endpoint usage. If that shortfall is a public-endpoint charge, then this
account's credit demonstrably pays for per-token billing.

That is a strong lead, **not proof** — the alternative explanation is simply that
the credit was never exactly $50.00. Closing it needs either the console's billing
view or a `get-public-endpoint-billing-history` call.

### The Runpod render app reproduces the home graph exactly

Measured, not asserted. The app is built and **not deployed**, so there is no
Runpod render time yet — but the thing that makes such a number honest is settled,
and it is settled by comparing output rather than by comparing settings tables.

`flash-imagegen/verify_port.py` rebuilds a plate the home bakery already rendered,
using the seed, positive prompt and negative prompt recorded in that plate's own
provenance file, submits it to the local ComfyUI, and compares the result against
the stored PNG pixel by pixel.

| Plate | Path exercised | Differing pixels | Max abs difference |
|---|---|---:|---:|
| `pg-41` `0001` | LoRA only | **0** of 1,011,712 | 0 |
| `pg-41` `0003` | LoRA + IP-Adapter | **0** of 1,011,712 | 0 |

Pixel-identical on both paths. SDXL at a fixed seed is deterministic, so any
difference in checkpoint, VAE, LoRA, sampler, scheduler, step count, CFG, size or
IP-Adapter wiring would change the image. The 7 of 9 Sleepy Hollow plates that
used a character reference make the second row the more important one.

**It failed the first time, which is the reason the check exists.** The initial
port *set* the negative prompt on node `7`. imagegen-service *appends* it — the
workflow template carries a baseline `blurry, lowres, deformed, text, watermark`
and the caller's negative is joined onto it (`engine.ts:562-569`). Replacing it
dropped five negative terms and changed **1,010,483 of 1,011,712 pixels**. Every
setting in the comparison table was correct at the time.

Model files are verified the same way rather than trusted by filename: all five
match the recorded byte count and SHA256 of the files the home machine is running
(`flash-imagegen/fetch_models.py --check-only`, 5 of 5 ok). The style LoRA's hash,
`74b377ee…adc87fd`, also matches CivitAI's record for version 2.1 and the
creator's own HuggingFace mirror, which is what establishes its provenance.

Pinned for this to stay true: ComfyUI 0.27.0 at `6cc8144`, `ComfyUI_IPAdapter_plus`
at `a0f451a`, torch 2.11.0+cu128.

### The test call was not made

It needs an `Authorization: Bearer` header, and the only way to build one here is
to extract the plaintext key out of `~/.runpod/config.toml`. `runpodctl` has no
subcommand that invokes a public endpoint, so there is no tool-mediated route that
leaves the key unread. Deferred rather than worked around — the estimate stands at
about $0.002 for two calls, which is not the reason it did not happen.

---

## 2026-08-17 — Cycle 1

### The standard comparison story — SUPERSEDED 2026-08-17 by `pg-41`

> **Superseded in Cycle 2.** The standard comparison story is now *The Legend of
> Sleepy Hollow* (`pg-41`) — see "The standard comparison story is now Sleepy
> Hollow" above. The reason is the plate count: the brief asked for a story
> yielding 8–12 plates and this one yields 5, for structural reasons given below.
>
> Everything in this section is still **correct and still cited.** The 7.615 s
> warm render median measured here is one of the four independent measurements
> that establish the 7.6 s per-plate constant, and the Runpod comparison rests on
> it. Kept verbatim rather than rewritten.

Every home-vs-Runpod measurement from here on uses the same book, so the
numbers stay comparable across cycles.

| Field | Value |
|---|---|
| Book | *The Yellow Wallpaper* |
| Author | Charlotte Perkins Gilman |
| Source | Project Gutenberg ebook #1952 |
| Words | 6,085 (after Project Gutenberg boilerplate is stripped) |
| Pages after pagination | 11 (Scriptorium targets 550 words per page) |
| Scriptorium book id | `pg-1952` |

Bake settings: density preset `lavish`, `images_per_scene: 1`, portraits
enabled, portrait review off, style `oil-painting`, era `1890s New England`.

**Ingest verified before baking:** the 11 pages contain 6,085 words, i.e. 100.0%
of the source. This check exists because the first story tried failed it — see
"Story #932 was rejected" below.

**Plate count came in under target.** The brief asked for a story sized to yield
8–12 plates. Selection chose **5**. The reason is in `selection.json`: the
selection engine marks a page when the scene changes, then fills gaps so no run
of pages exceeds `max_gap` (3 on `lavish`). *The Yellow Wallpaper* is a
first-person diary set almost entirely in one room, so the model found nearly no
scene changes and 4 of the 5 plates were chosen by gap-filling rather than by
content. With 11 pages and `max_gap: 3`, roughly 4–5 plates is the floor this
story can produce.

Total rendered images was **12**, which is in the intended range, but they are
not all plates:

| Image kind | Count | Size |
|---|---|---|
| Plates | 5 | 832×1216 |
| Cover | 1 | 832×1216 |
| Character portraits | 6 | 1024×1024 |
| **Total renders** | **12** | |

This is a decision Kris needs to make before Cycle 2, because the standard story
is locked once later measurements start citing it. Options are in the status
report.

### Baseline: the home bakery, end to end

One complete bake of `pg-1952`, run unchanged on its normal home setup — the
deployed service configuration was not modified, and Scriptorium's source was
not touched. Both human review gates were cleared by an automated driver the
instant they opened, so gate wait is effectively zero and machine time equals
wall clock.

Hardware: one NVIDIA RTX 5070, 12 GB of video memory. Text model
`qwen3.5:9b` served by Ollama behind text-transform-service. Image model
`sd_xl_base_1.0` served by ComfyUI behind imagegen-service.

**Wall clock: 289.39 s (4 min 49 s). Gate wait: 0.016 s.**

| Bucket | Time | Share |
|---|---:|---:|
| Image rendering | 94.79 s | 32.8% |
| Text steps | 82.64 s | 28.6% |
| Orchestration | 72.25 s | 25.0% |
| Model loading | 39.71 s | 13.7% |
| **Total** | **289.39 s** | **100%** |

Model loading is reported separately but happens *inside* the other two — a
model load is part of whichever request triggered it. Including it, text steps
took 97.81 s gross and image rendering took 119.33 s gross.

**Text steps — 33 model calls, 82.64 s net**

| Transform | Calls | Total | Median |
|---|---:|---:|---:|
| `cast-mentions` | 11 | 34.5 s | 1.869 s |
| `scene-update` | 11 | 34.2 s | 2.720 s |
| `cast-canonicalize` | 6 | 14.1 s | 1.639 s |
| `illustration-prompt` | 5 | 14.9 s | 1.971 s |

All 33 returned 200. Call counts match artifact file counts exactly (11 / 11 /
6), which is how the measurement window is confirmed correct.

**Image rendering — 12 renders, 94.79 s net**

Warm render median **7.615 s** at 832×1216 (n=6). All 12 renders were attributed
to this bake; none were left unclaimed.

**Model loading — 39.71 s, and this is the interesting number**

| Cause | Count | Each | Total |
|---|---:|---:|---:|
| Image model reloaded after the orchestrator freed the GPU | 1 | 10.565 s | 10.56 s |
| Image model re-staged under video-memory pressure | 5 | 2.795 s | 13.97 s |
| Text model loaded cold | 1 | — | 15.17 s |

The orchestrator freed the GPU 4 times and unloaded the text model 3 times
during this run. That deliberate swapping cost 10.6 s. The *incidental*
re-staging — ComfyUI evicting and restoring the image model under 12 GB of
video-memory pressure — happened 5 times in 12 renders and cost more.

**Orchestration — 72.25 s, a quarter of the run**

| Component | Time |
|---|---:|
| Idle between phases (11 gaps, 5 s runner tick) | 36.21 s |
| Generating web and thumbnail derivatives | 5.47 s |
| Everything else (HTTP, artifact writes, ingest, publish) | 30.57 s |

The single worker sleeps 5 seconds between advancing phases. On a book this
short that fixed cost is 12.5% of the entire run, spent doing nothing.

Machine-readable output: `runs/pg-1952/timing.json`. Driver log:
`runs/pg-1952/run.json`.

**What this means for the Runpod comparison.** Only 32.8% of this run was image
generation — the part moving to Flash first. A further 28.6% is text steps,
which move to a hosted endpoint later. The remaining 38.7% is orchestration and
model loading, and model loading is a cost that mostly *disappears* when the two
models stop sharing one GPU.

### Story #932 was rejected, and why it matters

The first choice was *The Fall of the House of Usher* (Project Gutenberg #932,
7,087 words). Scriptorium's ingest produced 11 pages containing only 3,670
words — **48% of the story was silently discarded**, including the entire
opening.

Cause: `detect_chapters` in `server/src/scriptorium/ingest/base.py:323` builds
chapters from detected headings, and `_chapters_from_headings` keeps only text
that falls under a heading. Usher contains an interior poem, "The Haunted
Palace", whose six stanzas are numbered I–VI. Those stanza numbers were detected
as chapter headings, so everything before the poem — the narrator's arrival and
the description of the house — fell outside every chapter and was dropped. The
resulting book reported no warnings.

This is a Scriptorium defect, not a Runpod one. It is out of scope this cycle
and was not fixed. It is recorded here because it is the reason the standard
story changed, and because any book with interior numbered sections is affected.

The check that catches it is one line: after ingest, compare the sum of page
word counts against the source word count. *The Yellow Wallpaper* returns
100.0%; *Usher* returns 51.8%.

### Hello-world Flash app

*Blocked.* No Runpod API key is present on this machine, so nothing was
deployed and nothing was spent. See the status report for the one step that
unblocks it.

---

## Reference numbers from earlier runs

Not produced by this project. Two bakes were already on disk when this work
started, and they are what `tools/bake_timing.py` was validated against before
it was trusted on the run above.

| | `pg-75201` | `pg-28054` | `pg-1952` (this cycle) |
|---|---:|---:|---:|
| Wall clock | 46 m 40 s | 10 h 01 m | 4 m 49 s |
| Renders attributed | 145 / 147 | 452 / 454 | 12 / 12 |
| Warm render median | 7.44 s | 7.49 s | 7.615 s |
| Re-stage penalty | 2.89 s | 2.80 s | 2.795 s |
| Reload-after-free penalty | 10.07 s | 10.49 s | 10.565 s |
| GPU free events | 4 | 4 | 4 |

The three derived constants agree to within 4% across three independent bakes
run days apart, which is the evidence that the measurement method is sound
rather than a coincidence of one run.

`pg-28054`'s bucket *percentages* are meaningless — that run sat about seven
hours at an overnight human review gate, so orchestration swallows 74.6% of it.
Its absolute seconds and derived constants are still usable. The collector also
correctly flags that run's window as contaminated by another project's traffic.

**Collector validation.** Before use, `tools/bake_timing.py` was required to
reproduce both past bakes within tolerance *and* to fail loudly when given a
deliberately wrong window. Widening `pg-75201`'s window by 15 minutes either
side made it report a count mismatch and 29 unattributable renders, which is the
behaviour wanted — a silent wrong answer is worse than a loud refusal.
