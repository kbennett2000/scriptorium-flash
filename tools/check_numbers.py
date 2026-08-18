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

    ./check_numbers.py                       # docs/NUMBERS.md against FINDINGS.md
    ./check_numbers.py --card docs/NUMBERS.md --log FINDINGS.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Digits, with optional thousands separators and decimal part.
_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")

# Not measurements: dates, ordinals, cycle numbers, issue numbers, and the
# handful of small integers that appear as English rather than as data.
ALLOWED = {
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10",
    "2026", "2025",                     # years
    "12", "15", "20", "24", "30", "60", # clock/count prose
    "363", "364", "365", "366", "798", "800", "327",  # issue numbers
    "0038", "0037", "0036", "0003",     # ADR numbers
}


def numbers(text: str) -> list[str]:
    """Every numeric literal, normalised to bare digits."""
    return [m.group(0).replace(",", "") for m in _NUM.finditer(text)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--card", type=Path, default=Path("docs/NUMBERS.md"))
    ap.add_argument("--log", type=Path, default=Path("FINDINGS.md"))
    args = ap.parse_args()

    log_numbers = set(numbers(args.log.read_text()))

    missing: list[tuple[int, str, str]] = []
    checked = 0
    for lineno, line in enumerate(args.card.read_text().splitlines(), 1):
        if line.lstrip().startswith(("<!--", "[")):
            continue  # comments and link definitions
        for n in numbers(line):
            if n in ALLOWED:
                continue
            checked += 1
            if n not in log_numbers:
                missing.append((lineno, n, line.strip()[:88]))

    print(f"card   {args.card}")
    print(f"log    {args.log}")
    print(f"checked {checked} numeric literals\n")

    if not missing:
        print("PASS -- every number on the card appears in the log.")
        return 0

    print(f"FAIL -- {len(missing)} number(s) on the card are not in the log:\n")
    for lineno, n, line in missing:
        print(f"  {args.card}:{lineno}  {n!r}")
        print(f"      {line}")
    print("\nPut the figure in FINDINGS.md first, with what it was measured from.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
