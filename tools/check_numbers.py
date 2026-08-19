#!/usr/bin/env python3
"""Refuse to let a number onto the card that is not in the log.

README states the project's one rule about numbers: FINDINGS.md is the only place
a measured number is written down, and everything else cites it, because retyped
numbers drift. A one-page card for a talk is exactly where that drift would happen
and exactly where it would be least recoverable -- on a slide, in front of people.

So this is the rule made mechanical. Every numeric literal in the card must appear
verbatim in FINDINGS.md. Not "be derivable from"; appear. If a figure needs
arithmetic, the arithmetic belongs in FINDINGS.md first, where it can be checked
against the artifact it came from.

Numbers are compared on their digits, so 4.7725 matches whether it was written
`4.7725 s`, `**4.7725**` or `4.7725s`, and 1,011,712 matches 1011712. Anything
listed in ALLOWED is skipped: years, section numbers, and the small integers that
are prose rather than measurement.

Cycle 6 pointed this at every document in the repo, not just the card, so "no
unlinked claims" is checked rather than remembered. That surfaced three classes
of digit that are addresses rather than measurements, and they are skipped
structurally rather than by adding numbers to ALLOWED one at a time:

- **Source citations.** `p7_render.py:358-361` and `engine.ts:562-569` name lines
  in a file. Skipping the whole span is right: it also means a real measurement
  can never hide inside one.
- **ADR references.** `ADR-0007`, `ADR 0038`, and a file's own `# ADR 0002`
  heading are identifiers. Most of them name ADRs in Scriptorium's private repo.
- **Hex digests.** MODELS.md's SHA256s are provenance for files this repo does
  not ship, and half their characters happen to be digits.

    ./check_numbers.py                       # docs/NUMBERS.md against FINDINGS.md
    ./check_numbers.py --card docs/NUMBERS.md --log FINDINGS.md
    ./check_numbers.py --card README.md GETTING-STARTED.md docs/*.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Digits, with optional thousands separators and decimal part.
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")

# Spans that are addresses, not measurements. Blanked before numbers are pulled,
# so a figure can never hide inside one.
_ADDRESSES = re.compile(
    r"""
      \b[\w./-]+\.(?:py|ts|sh|mjs|json|md|toml)   # a filename, then
        :\d+(?:-\d+)?                             # :line or :line-line,
        (?:\s*,\s*\d+(?:-\d+)?)*                  # and any ", 230-278" continuation
    | \#[0-9a-f]{3,8}\b                           # #3987e5 -- a colour, not a count
    | \bADR[- ]\d+                                # ADR-0007, ADR 0038
    | \b\d+(?:\.\d+){2,}(?:\+\w+)?                # 0.27.0, 3.11.15, 127.0.0.1,
                                                  #   2.11.0+cu128 -- no
                                                  #   measurement here has two
                                                  #   dots in it
    | (?<![\w.])                                  # git shas, SHA256 digests:
      (?=[0-9a-f]{7,}(?![\w.]))                   #   7+ hex chars, and at least
      [0-9a-f]*[a-f][0-9a-f]*                     #   one a-f, so a plain number
      (?![\w.])                                   #   like 7294523746 is not one
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Not measurements: dates, ordinals, cycle numbers, issue numbers, and the
# handful of small integers that appear as English rather than as data.
ALLOWED = {
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
    "2026", "2025",                     # years
    "12", "15", "20", "24", "30", "60", # clock/count prose
    "363", "364", "365", "366", "367", "798", "800", "327",  # issue numbers
    # ADR numbers. 0001-0003 are this repo's; the rest name ADRs in Scriptorium's
    # private repo, which this project cites but does not contain.
    "0001", "0002", "0003", "0036", "0037", "0038",
    # Ports and versions. Addresses and identifiers, not things that were timed:
    "8188",     # ComfyUI's own port, inside the container
    "8199",     # the host port the local boot-check publishes it on
    "8720",     # the local bakery's API, which is not part of this repo
    "11434",    # ollama
    "3.13", "3.14",   # Python versions, where written with one dot
    "5070",     # the home card's model number
    "4000",     # "A4000-class", naming the 16 GB pool
}


def numbers(text: str) -> list[str]:
    """Every numeric literal, normalised to bare digits."""
    text = _ADDRESSES.sub(" ", text)
    return [m.group(0).replace(",", "") for m in _NUM.finditer(text)]


def check(card: Path, log_numbers: set[str]) -> tuple[int, list[tuple[int, str, str]]]:
    """Return (literals checked, the ones the log does not have)."""
    missing: list[tuple[int, str, str]] = []
    checked = 0
    for lineno, line in enumerate(card.read_text().splitlines(), 1):
        if line.lstrip().startswith(("<!--", "[")):
            continue  # comments and link definitions
        for n in numbers(line):
            if n in ALLOWED:
                continue
            checked += 1
            if n not in log_numbers:
                missing.append((lineno, n, line.strip()[:88]))
    return checked, missing


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--card", type=Path, nargs="+", default=[Path("docs/NUMBERS.md")],
                    help="one or more documents to check against the log")
    ap.add_argument("--log", type=Path, default=Path("FINDINGS.md"))
    args = ap.parse_args()

    # The defaults are repo-relative, so running this from a subdirectory used to
    # die with a bare FileNotFoundError traceback. Say what is actually wrong.
    missing_files = [p for p in [args.log, *args.card] if not p.is_file()]
    if missing_files:
        for p in missing_files:
            print(f"no such file: {p}", file=sys.stderr)
        print("\nRun this from the repository root -- the default paths are "
              "relative to it.", file=sys.stderr)
        return 2

    log_numbers = set(numbers(args.log.read_text()))
    print(f"log    {args.log}\n")

    total_checked = 0
    failed: list[tuple[Path, list[tuple[int, str, str]]]] = []

    for card in args.card:
        checked, missing = check(card, log_numbers)
        total_checked += checked
        status = "PASS" if not missing else f"FAIL {len(missing)}"
        print(f"  {status:<7} {checked:>4} literals  {card}")
        if missing:
            failed.append((card, missing))

    print(f"\nchecked {total_checked} numeric literals across {len(args.card)} file(s)\n")

    if not failed:
        print("PASS -- every number appears in the log.")
        return 0

    n_missing = sum(len(m) for _, m in failed)
    print(f"FAIL -- {n_missing} number(s) are not in the log:\n")
    for card, missing in failed:
        for lineno, n, line in missing:
            print(f"  {card}:{lineno}  {n!r}")
            print(f"      {line}")
    print("\nPut the figure in FINDINGS.md first, with what it was measured from.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
