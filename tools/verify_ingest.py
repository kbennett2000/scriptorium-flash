#!/usr/bin/env python3
"""Check an ingested book against its Project Gutenberg source before any GPU time.

Cycle 1 established the rule the hard way: *The Fall of the House of Usher* silently
lost 48% of its text and reported no warnings, because `_chapters_from_headings` drops
everything before the first detected heading. The check that catches it is a word
count, and the check has to run before a bake spends money on a mutilated book.

This is the pg-41 procedure (FINDINGS.md, "Sleepy Hollow -- ingest integrity") turned
into a script, so a second book is verified the same way rather than a similar way:

  1. fetch the source, cut everything outside the PG START/END markers
  2. count whitespace-separated tokens -> source words
  3. sum `word_count` over work/<id>/pages/*.json -> stored words
  4. retention against a threshold set in advance (default 99.5%)
  5. read the warnings array -- an EMPTY array is the bad sign, see below
  6. diff source against stored and enumerate every missing line
  7. spot-check the stored opening and closing against the source

On (5): `chapters_undetected` fires only when detection finds nothing and the
whole-text fallback keeps everything. Its *absence* means detection succeeded and the
dropping path ran. Empty warnings plus high retention is fine; empty warnings plus low
retention is Usher.

    ./verify_ingest.py --book-id pg-120 --gutenberg-id 120
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
import urllib.request
from pathlib import Path

DATA_ROOT = Path("/home/kb/scriptorium-data")
SOURCE_URL = "https://www.gutenberg.org/ebooks/{id}.txt.utf-8"

# The same markers ingest/gutenberg.py uses, tolerant of THE/THIS and casing.
_START = re.compile(
    r"^\*\*\*\s*START OF TH(?:E|IS) PROJECT GUTENBERG.*\*\*\*\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_END = re.compile(
    r"^\*\*\*\s*END OF TH(?:E|IS) PROJECT GUTENBERG.*\*\*\*\s*$",
    re.IGNORECASE | re.MULTILINE,
)


def strip_boilerplate(text: str) -> str:
    """Return the text between the PG markers, or the whole thing if they are absent."""
    start, end = _START.search(text), _END.search(text)
    if start and end and end.start() > start.end():
        return text[start.end() : end.start()].strip("\n")
    return text


def fetch_source(gutenberg_id: int) -> str:
    url = SOURCE_URL.format(id=gutenberg_id)
    with urllib.request.urlopen(url, timeout=120) as resp:
        return resp.read().decode("utf-8", errors="replace")


def stored_pages(book_id: str, data_root: Path) -> list[dict]:
    paths = sorted((data_root / "work" / book_id / "pages").glob("*.json"))
    if not paths:
        raise SystemExit(f"no pages under work/{book_id}/pages -- has it been ingested?")
    return [json.loads(p.read_text()) for p in paths]


def job_warnings(book_id: str, data_root: Path) -> list:
    rec = data_root / "jobs" / f"{book_id}.json"
    if not rec.exists():
        return []
    return json.loads(rec.read_text()).get("warnings", []) or []


def structure(book_id: str, data_root: Path) -> dict:
    p = data_root / "work" / book_id / "structure.json"
    return json.loads(p.read_text()) if p.exists() else {}


# A table-of-contents line carries dot leaders: "THE BLACK SPOT . . . . . . 24".
# Whitespace tokenizing counts every dot group as a word, so a 34-entry contents
# page inflates the shortfall by hundreds of "words" that are punctuation. pg-41
# had no contents page, which is why the 99.5% threshold never had to allow for one.
_TOC_LEADER = re.compile(r"\.\s+\.\s+\.")


def classify(gone: list[str], chapter_titles: set[str]) -> dict[str, list[str]]:
    """Split missing lines into contents / headings / other, so a bare percentage
    is never the whole story. `other` is the group that matters: if narrative prose
    is missing, it lands there."""
    out: dict[str, list[str]] = {"contents": [], "headings": [], "other": []}
    for ln in gone:
        if _TOC_LEADER.search(ln) or ln.strip().upper() == "CONTENTS":
            out["contents"].append(ln)
        elif any(ln.strip() and ln.strip() in t for t in chapter_titles):
            out["headings"].append(ln)
        else:
            out["other"].append(ln)
    return out


def missing_lines(source: str, stored: str) -> list[str]:
    """Every source line absent from the stored text, in source order.

    Line-level rather than token-level so the output names the thing that went --
    a title, a heading, a stanza -- instead of a bag of words.
    """
    src_lines = [ln.strip() for ln in source.splitlines() if ln.strip()]
    out_lines = [ln.strip() for ln in stored.splitlines() if ln.strip()]
    gone: list[str] = []
    sm = difflib.SequenceMatcher(None, src_lines, out_lines, autojunk=False)
    for tag, i1, i2, _j1, _j2 in sm.get_opcodes():
        if tag in ("delete", "replace"):
            gone.extend(src_lines[i1:i2])
    return gone


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--book-id", required=True)
    ap.add_argument("--gutenberg-id", type=int, required=True)
    ap.add_argument("--data-root", type=Path, default=DATA_ROOT)
    ap.add_argument("--threshold", type=float, default=99.5,
                    help="retention %% below which this is a failure (set in advance)")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    raw = fetch_source(args.gutenberg_id)
    source = strip_boilerplate(raw)
    source_words = len(source.split())

    pages = stored_pages(args.book_id, args.data_root)
    stored_text = "\n".join(p.get("text", "") for p in pages)
    stored_words = sum(int(p.get("word_count", 0)) for p in pages)
    retention = 100.0 * stored_words / source_words if source_words else 0.0

    warnings = job_warnings(args.book_id, args.data_root)
    struct = structure(args.book_id, args.data_root)
    chapters = struct.get("chapters") or []

    gone = missing_lines(source, stored_text)
    gone_words = sum(len(ln.split()) for ln in gone)

    first_page = pages[0].get("text", "").strip().replace("\n", " ")
    last_page = pages[-1].get("text", "").strip().replace("\n", " ")

    print(f"book                {args.book_id}  (Project Gutenberg #{args.gutenberg_id})")
    print(f"source words        {source_words:,}   (after PG boilerplate stripped)")
    print(f"stored words        {stored_words:,}   (sum of {len(pages)} page word_counts)")
    print(f"retention           {retention:.2f}%   against a {args.threshold}% threshold")
    print(f"pages               {len(pages)}")
    print(f"chapters detected   {len(chapters)}")
    print(f"ingest warnings     {warnings if warnings else '[] -- see note below'}")
    print()

    if not warnings:
        print("NOTE: an empty warnings array is the *bad* sign, not the good one.")
        print("      `chapters_undetected` fires only when detection finds nothing and")
        print("      the whole-text fallback keeps everything. Its absence means")
        print("      _chapters_from_headings ran -- the path that drops text. Retention")
        print("      is the only thing that tells you whether that mattered.")
        print()

    titles = {c.get("title", "") for c in chapters}
    groups = classify(gone, titles)
    w = lambda lines: sum(len(x.split()) for x in lines)  # noqa: E731

    print(f"missing lines       {len(gone)}  ({gone_words} words), grouped:")
    for name, label in (("contents", "table of contents (dot leaders)"),
                        ("headings", "headings, now titles in structure.json"),
                        ("other", "everything else -- PROSE WOULD LAND HERE")):
        g = groups[name]
        print(f"  {name:<9} {len(g):>3} lines {w(g):>4} words   {label}")
    print()
    for ln in groups["other"]:
        shown = ln if len(ln) <= 74 else ln[:71] + "..."
        print(f"  other  {len(ln.split()):>4}w  {shown}")
    print()

    # Retention with the contents page removed from the denominator: the
    # apples-to-apples comparison against a book that never had one.
    adj_source = source_words - w(groups["contents"])
    adj_retention = 100.0 * stored_words / adj_source if adj_source else 0.0
    print(f"retention (raw)             {retention:.2f}%")
    print(f"retention (less contents)   {adj_retention:.2f}%   "
          f"of {adj_source:,} words")
    print()

    print(f"opens               {first_page[:100]}...")
    print(f"closes              ...{last_page[-100:]}")
    print()

    accounted = gone_words == (source_words - stored_words)
    verdict = "PASS" if retention >= args.threshold else "FAIL"
    print(f"shortfall           {source_words - stored_words} words; "
          f"missing lines sum to {gone_words} "
          f"({'exact' if accounted else 'DOES NOT RECONCILE'})")
    print(f"VERDICT             {verdict} against the raw {args.threshold}% threshold")
    if verdict == "FAIL" and adj_retention >= args.threshold:
        print("                    -- but the shortfall is a contents page, and")
        print("                       retention less contents clears the threshold.")
        print("                       Read the `other` group above before deciding.")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps({
            "book_id": args.book_id,
            "gutenberg_id": args.gutenberg_id,
            "source_words": source_words,
            "stored_words": stored_words,
            "retention_pct": round(retention, 4),
            "threshold_pct": args.threshold,
            "pages": len(pages),
            "chapters_detected": len(chapters),
            "warnings": warnings,
            "missing_lines": gone,
            "missing_words": gone_words,
            "missing_by_group": {k: {"lines": v, "words": sum(len(x.split()) for x in v)}
                                 for k, v in groups.items()},
            "retention_less_contents_pct": round(adj_retention, 4),
            "shortfall_reconciles": accounted,
            "opens": first_page[:200],
            "closes": last_page[-200:],
            "verdict": verdict,
        }, indent=2) + "\n")

    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
