#!/usr/bin/env python3
"""Fold duplicate cast entries into one character, at the cast review gate.

`reduce_cast.py` groups mentions into characters, and on a long book with heavy
aliasing it under-merges. Treasure Island produced 70 characters, 35 of them
major, which is 35 portraits for about 20 people: four Dr. Liveseys
(`dr-livesey`, `doctor`, `livesey`, `doctor-livesey`), four Long John Silvers
(`silver`, `long-john`, `john`, `cook`), four Trelawneys.

The cause is visible in reduce_cast's own rules: 2c "never merges on a token
shared by >=2 full names", and the same-page guard refuses to merge two labels
that appear as distinct entries on one page. Both are there to prevent *wrong*
merges, and on a book with one surname per family they cost right ones.

There is no product affordance for this. `PUT /review/cast/{slug}` edits
`visual_description` and `one_line` only -- it cannot demote a character or merge
two. So this is a deliberate, recorded hand edit, applied at the cast gate, which
is before the ledger, selection, prompt and portrait phases all derive from
cast.json. Nothing downstream has to be patched because nothing downstream has
run yet.

The map is explicit rather than inferred. An automatic rule that merged on shared
surnames is exactly the rule reduce_cast declined to write, and it would be wrong
here in at least two places -- see AMBIGUOUS below.

    ./prune_cast.py --book-id pg-120 --dry-run
    ./prune_cast.py --book-id pg-120
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

DATA_ROOT = Path("/home/kb/scriptorium-data")

# canonical slug -> slugs folded into it. Each is one person in the novel.
MERGES: dict[str, list[str]] = {
    # Dr. Livesey: doctor, magistrate, narrator of chapters XVI-XVIII.
    "dr-livesey": ["doctor", "livesey", "doctor-livesey"],
    # Long John Silver, the sea-cook, "Barbecue".
    "silver": ["long-john", "john", "cook"],
    # Squire John Trelawney.
    "squire-trelawney": ["squire", "trelawney", "mr-trelawney"],
    # Jim Hawkins, the narrator.
    "jim": ["hawkins"],
    # Blind Pew is the blind man at the Admiral Benbow.
    "pew": ["blind-man"],
}

# Deliberately NOT merged, and the reason. These are the cases where the
# reducer's caution was right and a surname rule would have been wrong.
AMBIGUOUS = {
    "captain": "'the captain' is Billy Bones at the Admiral Benbow for the whole "
               "of Part One and Captain Smollett from Part Two on. One slug, two "
               "people; merging it into either is wrong for half the book.",
    "dick": "reduce_cast attached 'Israel Hands' to Dick's aliases, but Dick "
            "Johnson and Israel Hands are different pirates. Merging `dick` and "
            "`hands` would act on that bad alias rather than on the text.",
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--book-id", required=True)
    ap.add_argument("--data-root", type=Path, default=DATA_ROOT)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    path = args.data_root / "work" / args.book_id / "cast.json"
    doc = json.loads(path.read_text())
    chars = doc["characters"]
    by_slug = {c["slug"]: c for c in chars}

    majors_before = sum(1 for c in chars if c.get("major"))
    folded: list[str] = []

    for canonical, dupes in MERGES.items():
        keep = by_slug.get(canonical)
        if keep is None:
            print(f"  skip {canonical}: not in cast")
            continue
        for slug in dupes:
            dup = by_slug.get(slug)
            if dup is None:
                print(f"  skip {slug}: not in cast")
                continue
            # The duplicate's display name and its aliases all become aliases of
            # the kept character, so nothing the text actually said is lost.
            aliases = list(keep.get("aliases") or [])
            for a in [dup.get("name")] + list(dup.get("aliases") or []):
                if a and a != keep.get("name") and a not in aliases:
                    aliases.append(a)
            keep["aliases"] = aliases
            # Union the pages, so the kept character's mention span is the real one.
            pages = set(keep.get("mention_pages") or []) | set(dup.get("mention_pages") or [])
            keep["mention_pages"] = sorted(pages)
            keep["edited_by_human"] = True
            folded.append(slug)
            print(f"  {slug:<20} -> {canonical:<20} "
                  f"({len(dup.get('mention_pages') or [])} pages folded in)")

    doc["characters"] = [c for c in chars if c["slug"] not in folded]
    majors_after = sum(1 for c in doc["characters"] if c.get("major"))

    print(f"\ncharacters  {len(chars)} -> {len(doc['characters'])}")
    print(f"majors      {majors_before} -> {majors_after}   "
          f"(= portraits to render)")
    print("\nleft alone on purpose:")
    for slug, why in AMBIGUOUS.items():
        print(f"  {slug}: {why}")

    if args.dry_run:
        print("\ndry run -- nothing written")
        return 0

    # Validate against the server's own schema before writing, so a malformed
    # edit fails here rather than three phases later.
    import sys
    sys.path.insert(0, "/home/kb/Desktop/projects/scriptorium/server/src")
    from scriptorium import schemas
    schemas.validate("cast", doc)

    path.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"\nwrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
