# The stage rehearsal, halted

Cycle 6 ran the demo exactly as it would run on stage, on endpoint
`cire2u3mv4cr3m`. **It stopped on two conditions, both recorded in
[FINDINGS.md](../../FINDINGS.md) and both Kris's call**: the cycle went
$0.1025810092 over its $0.30 ceiling, and the warm render median missed a band
registered before the run.

| Step | Result |
|---|---|
| 1. Pre-warm, twice | 121.88 s then 24.47 s. Warm signature confirmed: `boot 0`, `render 1.507` |
| 2. Live `pg-41` bake | **744.91 s** — contaminated, not a comparison. Rendering itself was 60.38 s against the headline's 59.74 s |
| 3. One warm render | **5.175 s** wall, `render_s` **2.813 s** — the fastest this project has recorded |
| 4. Vercel book | `PASS -- the deployed reader downloads and reads the book end to end.` |

| Cost | **$0.3963518425**, settled over six identical reads |
|---|---|

## Files

| File | What it is |
|---|---|
| `prewarm-1.json` / `.log` | Pass 1, cold endpoint |
| `prewarm-2.json` / `.log` | Pass 2, the warmth proof |
| `prewarm.json` | Pass 3, run inside the bake script. Contains the `FAILED` request |
| `run.json`, `timing.json` | The bake |
| `warm-demo.json` | The single warm render |
| `bake-console.log` | The driver transcript |
| `balance-settle.log` | Six identical reads |
| `reader-shots/` | Screenshots from the real-browser check |

**These artifacts are deliberately separate from `runs/pg-41-runpod/`**, which
holds the committed evidence behind the 325.24 s headline. `headline_bake.sh`
now takes an `OUT` override for exactly this reason: run with its default, this
rehearsal would have overwritten `run.json`, `timing.json`, `prewarm.json` and
`warm-demo.json` and destroyed the provenance behind the repo's headline number.

`6-plate.png` is not kept: it was byte-identical to `5-page1.png`
(md5 `e1be442b…`), because page 1 of *Treasure Island* is itself the illustrated
page the check went looking for. A second copy would add 452 KB and no evidence.
