# Repository images

Two rendered images, and the HTML that produces them. The HTML is kept so the
images can be regenerated rather than re-drawn: the numbers on them go stale
every time the ledger moves.

| File | Where it is used | Size |
|---|---|---|
| `banner.png` | the top of the repository README | 1280x400, rendered at 2x |
| `social-preview.png` | GitHub Settings, "Social preview" | 1280x640, rendered at 2x |

## Regenerating

Both are plain HTML screenshotted with Playwright at `deviceScaleFactor: 2`:

```bash
node - <<'JS'
import { chromium } from "/path/to/playwright/index.mjs";
const jobs = [["banner.html", "banner.png", 1280, 400, ".banner"],
              ["social-preview.html", "social-preview.png", 1280, 640, ".card"]];
const b = await chromium.launch();
for (const [html, out, w, h, sel] of jobs) {
  const p = await b.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 2 });
  await p.goto("file://" + process.cwd() + "/" + html);
  await p.waitForTimeout(300);
  await (await p.$(sel)).screenshot({ path: out });
}
await b.close();
JS
```

**The bar widths are hard-coded and proportional**, so they have to be
recomputed if a figure changes: the Runpod bar is the home bar times
`325.24 / 388.63`. There is no chart library here and no data binding, because
two bars did not warrant either.

## The colours

Blue `#3987e5` and orange `#d95926` on surface `#1a1a19`. That pair was checked
rather than chosen by eye: worst-case colour-vision-deficient separation is
OKLab dE 26.8, against a target of 8, and both clear 3:1 contrast against the
surface. Every bar is directly labelled as well, so identity never depends on
colour alone.

## The numbers on them

Every figure comes from [FINDINGS.md](../../FINDINGS.md), like everything else
in this repository. `tools/check_numbers.py` cannot read a PNG, so **these two
images are the one place a number is not machine-checked**. If you change a
figure in the log, change it here by hand.
