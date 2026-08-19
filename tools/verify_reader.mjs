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
let responses = 0;
page.on("response", (r) => {
  responses += 1;
  // /artsets/{user}/{book}/edits/manifest 404s on the real bakery as well
  // ("no such set 'edits'") until somebody makes a private edit, so a 404 there
  // is the mirror being faithful rather than the mirror being incomplete.
  const expected404 = /\/artsets\/[^/]+\/[^/]+\/edits\//.test(r.url());
  if (r.status() >= 400 && !expected404) badStatus.push(`${r.status()} ${r.url().slice(0, 160)}`);
});

console.log(`reader  ${url}`);
console.log(`book    ${bookId}\n`);

// Anything that throws below lands here. Without this the script dies as an
// uncaught TimeoutError and takes `problems`, `badStatus` and the screenshot
// with it, which is what a 300 s checkout hang looked like on 2026-08-19: a
// Node stack trace and no evidence at all.
async function bail(stage, err) {
  console.log(`\nFAILED at: ${stage}`);
  console.log(`  ${String(err).split("\n")[0]}`);
  console.log(`\n  responses seen   ${responses}`);
  console.log(`  4xx/5xx          ${badStatus.length}`);
  for (const b of badStatus.slice(0, 10)) console.log(`    ${b}`);
  console.log(`  console/request  ${problems.length}`);
  for (const q of problems.slice(0, 10)) console.log(`    ${q}`);
  await page.screenshot({ path: `${shotDir}/FAILED-${stage}.png`, fullPage: true })
    .catch(() => {});
  console.log(`\n  screenshot of the failure: ${shotDir}/FAILED-${stage}.png`);
  await browser.close().catch(() => {});
  process.exit(1);
}

// Every step, not just the checkout. A pre-flight check that dies as a Node
// stack trace tells you it broke and nothing about why, which is the whole
// reason this net exists.
process.on("unhandledRejection", (err) => { bail("step", err); });
process.on("uncaughtException", (err) => { bail("step", err); });

// Wait, but say what is happening while waiting. A silent five-minute block is
// indistinguishable from a hang, and it was read as one.
async function waitLoud(locator, label, totalMs, sliceMs = 15000) {
  const t0 = Date.now();
  for (let waited = 0; waited < totalMs; waited += sliceMs) {
    try {
      await locator.waitFor({ timeout: Math.min(sliceMs, totalMs - waited) });
      return (Date.now() - t0) / 1000;
    } catch (err) {
      if (waited + sliceMs >= totalMs) throw err;
      console.log(`       ...${label}: ${((Date.now() - t0) / 1000).toFixed(0)}s, ` +
                  `${responses} responses, ${badStatus.length} bad`);
    }
  }
  return null;
}

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
// A whole illustrated book: ~330 requests for 6.8 MB. It completes in 11-21 s
// warm, and one run in five died partway with the reader showing "Failed to
// fetch" and the card at "incomplete". That is a flaky download, not a broken
// site, and the reader already handles it: the button becomes **Resume
// download**. Retrying `/^Download$/` matches nothing once that has happened,
// which is exactly how the first version of this retry wasted 150 s clicking a
// button that was no longer on the page. Match either label.
const resumeOrDownload = () =>
  page.getByRole("button", { name: /^(Resume download|Download)$/ }).first();
let checkoutS = null;
for (let attempt = 1; attempt <= 3 && checkoutS === null; attempt += 1) {
  const label = attempt === 1 ? "checkout" : `checkout retry ${attempt - 1}`;
  checkoutS = await waitLoud(openBtn, label, 120000).catch(() => null);
  if (checkoutS !== null) break;
  const card = await page.locator(".shelf-card").first().innerText().catch(() => "");
  const btn = resumeOrDownload();
  if (!(await btn.count())) {
    await bail("checkout", new Error(
      `stalled with no Download/Resume button. Card reads: ${card.replace(/\n/g, " | ")}`));
  }
  const btnText = (await btn.innerText().catch(() => "?")).trim();
  console.log(`       checkout stalled; card reads "${card.split("\n").pop()}", ` +
              `clicking "${btnText}" (attempt ${attempt + 1} of 3)`);
  await btn.click().catch(() => {});
}
if (checkoutS === null) {
  await bail("checkout", new Error("checkout did not complete in 3 attempts"));
}
ok("checkout completed (manifest + files)", true, `${checkoutS.toFixed(1)}s`);
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
const expected = (p) =>
  p.startsWith("console error: Failed to load resource") || /edits/.test(p);
const noisy = problems.filter(
  (p) => (p.startsWith("console") || p.startsWith("request")) && !expected(p));
ok("no console errors or failed requests", noisy.length === 0);
if (problems.length) {
  console.log("\n  observed (including expected ones):");
  for (const p of problems.slice(0, 12)) console.log(`    ${expected(p) ? "expected" : "PROBLEM "}  ${p}`);
}

await browser.close();

const hard = problems.filter((p) => !expected(p));
console.log(`\nscreenshots in ${shotDir}`);
if (hard.length) {
  console.log(`\nFAILED (${hard.length}):`);
  for (const p of hard.slice(0, 12)) console.log(`  - ${p}`);
  process.exit(1);
}
console.log("\nPASS -- the deployed reader downloads and reads the book end to end.");
