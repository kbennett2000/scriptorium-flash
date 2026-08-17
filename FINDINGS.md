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
| 2026-08-17 | Cycle 2 key check — two read-only account queries | $0.00 | `runpodctl billing {pods,serverless,network-volume}` all return `[]` |

**Total Runpod spend to date: $0.00**

Verified against the account's own billing records, not estimated. See the
account baseline below for what "verified" rests on.

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
