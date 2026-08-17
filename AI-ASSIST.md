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
