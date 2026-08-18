// Drive the deployed reader the way a person would, and prove the book reads.
//
// Every check in this repo so far has been an HTTP status and a byte count, which
// establishes that the static mirror *serves* the five routes but not that the
// reader *works* against them. Those are different claims, and the second one is
// the one a live-demo fallback has to make. So this boots real Chromium against
// the deployed URL, picks a profile, downloads the book through the reader's own
// checkout path, opens it, turns pages, and screenshots what it saw.
//
// It fails loudly on any console error or failed request, because a reader that
// renders page one while quietly 404ing its plates would otherwise pass.
//
//   node tools/verify_reader.mjs <url> <book-id> [screenshot-dir]
//
// Uses the reader repo's own Playwright install and browsers.

import { chromium } from "/home/kb/Desktop/projects/scriptorium/reader/node_modules/playwright/index.mjs";
import { mkdirSync } from "node:fs";

const [url, bookId, shotDir = "/tmp/reader-verify"] = process.argv.slice(2);
if (!url || !bookId) {
  console.error("usage: verify_reader.mjs <url> <book-id> [screenshot-dir]");
  process.exit(2);
}
mkdirSync(shotDir, { recursive: true });

const problems = [];
const ok = (label, cond, detail = "") => {
  console.log(`  ${cond ? "ok  " : "FAIL"} ${label}${detail ? "  " + detail : ""}`);
  if (!cond) problems.push(label);
};

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });

page.on("console", (m) => {
  if (m.type() === "error") problems.push(`console error: ${m.text().slice(0, 200)}`);
});
page.on("requestfailed", (r) => {
  problems.push(`request failed: ${r.url().slice(0, 160)} (${r.failure()?.errorText})`);
});
const badStatus = [];
page.on("response", (r) => {
  // /artsets/{user}/{book}/edits/manifest 404s on the real bakery as well
  // ("no such set 'edits'") until somebody makes a private edit, so a 404 there
  // is the mirror being faithful rather than the mirror being incomplete.
  const expected404 = /\/artsets\/[^/]+\/[^/]+\/edits\//.test(r.url());
  if (r.status() >= 400 && !expected404) badStatus.push(`${r.status()} ${r.url().slice(0, 160)}`);
});

console.log(`reader  ${url}`);
console.log(`book    ${bookId}\n`);

await page.goto(url, { waitUntil: "networkidle", timeout: 60000 });
await page.screenshot({ path: `${shotDir}/1-profiles.png` });

// 1. profile picker -- served by /api/users
const profile = page.getByRole("button", { name: /Kris/ }).first();
await profile.waitFor({ timeout: 20000 });
ok("profile picker rendered (/api/users)", true);
await profile.click();

// 2. shelf -- served by /api/library
const card = page.locator(".shelf-card").filter({ hasText: /./ });
await card.first().waitFor({ timeout: 20000 });
const titles = await page.locator(".shelf-card-head strong").allInnerTexts();
const authors = await page.locator(".shelf-author").allInnerTexts();
ok("shelf listed the book (/api/library)", titles.length > 0,
   `${titles.length} card(s): ${titles.join(", ")}`);
console.log(`       title/author as published: ${titles[0]} / ${authors[0]}`);
await page.screenshot({ path: `${shotDir}/2-shelf.png` });

// 3. checkout -- manifest + every reader-required file
const download = page.getByRole("button", { name: /^Download$/ }).first();
await download.waitFor({ timeout: 20000 });
await download.click();
const openBtn = page.locator(".shelf-open").first();
await openBtn.waitFor({ timeout: 300000 });   // a whole illustrated book
ok("checkout completed (manifest + files)", true);
await page.screenshot({ path: `${shotDir}/3-resident.png` });

// 4. open and read
await openBtn.click();
const progress = page.locator(".reader-progress");
await progress.waitFor({ timeout: 30000 });
const first = (await progress.innerText()).trim();
ok("book opened", /^\d+\s*\/\s*\d+$/.test(first), first);

// The dramatis personae interstitial auto-opens on a fresh book. Its presence is
// the check that the pruned cast actually reached the reader.
const cast = page.locator(".cast-page");
if (await cast.count()) {
  const portraits = await cast.locator("img").count();
  // Not an assertion: the cast page reveals people as the reader meets them, so
  // on page 1 "No one has been introduced yet" is correct, not a missing asset.
  console.log(`  --   cast page rendered, ${portraits} portrait(s) resident at page 1`);
  await page.screenshot({ path: `${shotDir}/4-cast.png` });
  await cast.getByRole("button", { name: "Done" }).click().catch(() => {});
  await cast.waitFor({ state: "detached", timeout: 10000 }).catch(() => {});
}

await page.screenshot({ path: `${shotDir}/5-page1.png` });

// 5. turn pages, and find one with a plate on it
let sawPlate = false;
for (let i = 0; i < 12 && !sawPlate; i += 1) {
  const imgs = await page.locator(".reader-page img, .plate img, figure img").count();
  if (imgs > 0) sawPlate = true;
  else await page.getByRole("button", { name: "Next" }).click().catch(() => {});
  await page.waitForTimeout(400);
}
ok("an illustration rendered in the reading surface", sawPlate);
await page.screenshot({ path: `${shotDir}/6-plate.png` });

const last = (await progress.innerText()).trim();
console.log(`       progress moved ${first} -> ${last}`);

// 6. nothing broke quietly
ok("no 4xx/5xx responses", badStatus.length === 0,
   badStatus.slice(0, 5).join(" | "));
ok("no console errors or failed requests",
   problems.filter((p) => p.startsWith("console") || p.startsWith("request")).length === 0);

await browser.close();

const hard = problems.filter(
  (p) => !p.startsWith("console error: Failed to load resource") && !/edits/.test(p));
console.log(`\nscreenshots in ${shotDir}`);
if (hard.length) {
  console.log(`\nFAILED (${hard.length}):`);
  for (const p of hard.slice(0, 12)) console.log(`  - ${p}`);
  process.exit(1);
}
console.log("\nPASS -- the deployed reader downloads and reads the book end to end.");
