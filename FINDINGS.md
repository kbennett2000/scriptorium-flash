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
| — | Nothing spent yet | $0.00 | — |

**Total Runpod spend to date: $0.00**

---

## 2026-08-17 — Cycle 1

### The standard comparison story

Every home-vs-Runpod measurement from here on uses the same book, so the
numbers are comparable across cycles.

| Field | Value |
|---|---|
| Book | *The Fall of the House of Usher* |
| Author | Edgar Allan Poe |
| Source | Project Gutenberg ebook #932 |
| Words | 7,087 (after Project Gutenberg boilerplate is stripped) |
| Scriptorium book id | `pg-932` |

Word count measured by fetching `https://www.gutenberg.org/ebooks/932.txt.utf-8`,
cutting everything outside the Project Gutenberg START/END markers, and counting
whitespace-separated tokens — the same boilerplate rule Scriptorium's own
ingester applies.

Bake settings for the baseline run: density preset `lavish`,
`images_per_scene: 1`, portraits enabled, portrait review off, style
`oil-painting`.

### Baseline: the home bakery, end to end

*Pending — the measured run has not been performed yet.*

### Hello-world Flash app

*Pending.*

---

## Reference numbers from earlier runs

These were not produced by this project. They come from two book bakes that were
already sitting on disk when this work started, and they are recorded here
because they are what the collector in `tools/` was validated against.

*Pending — written when the collector has been validated.*
