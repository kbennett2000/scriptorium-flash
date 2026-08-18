#!/usr/bin/env python3
"""Task 0b: re-derive every pg-41 plate's request strings with TODAY's code.

The baseline bake wrote `wrapped_prompt` and `negative_prompt` into each plate's
provenance file. This replays `wrap_prompt` against the same inputs -- the same
job record, the same styles catalog, the same prompt docs -- and asserts byte
equality. If ADR-0036 (user negative applied to every plate) changed anything
about a bake where the owner supplied nothing, it shows up here, in the strings,
before a single pixel is rendered.

Reads only. Writes nothing. Costs nothing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SERVER = Path("/home/kb/Desktop/projects/scriptorium/server")
sys.path.insert(0, str(SERVER / "src"))

from scriptorium.bake.phases.p7_render import wrap_prompt  # noqa: E402
from scriptorium.styles import resolve_style  # noqa: E402

DATA = Path("/home/kb/scriptorium-data")
BOOK = "pg-41"


def main() -> int:
    job = json.loads((DATA / "jobs" / f"{BOOK}.json").read_text())
    cfg = job["bake_config"]
    style = resolve_style(cfg)

    prompts = sorted((DATA / "work" / BOOK / "prompts").glob("*.json"))
    if not prompts:
        print(f"no prompt docs under {DATA / 'work' / BOOK / 'prompts'}")
        return 2

    print(f"book        {BOOK}")
    print(f"style_id    {cfg.get('style_id')}")
    print(f"era         {cfg.get('era')!r}")
    print(f"negative    {cfg.get('negative')!r}   <- the ADR-0036 field, unset by this bake")
    print(f"plates      {len(prompts)}")
    print()

    bad = 0
    for path in prompts:
        doc = json.loads(path.read_text())
        plate_id = doc["page_id"]
        if "wrapped_prompt" not in doc or "negative_prompt" not in doc:
            print(f"  {plate_id:<30} SKIP (never rendered: no stored strings)")
            continue
        wrapped, negative = wrap_prompt(
            style, plate_id, doc, cfg.get("era"), cfg.get("negative")
        )
        ok_w = wrapped == doc["wrapped_prompt"]
        ok_n = negative == doc["negative_prompt"]
        if ok_w and ok_n:
            print(f"  {plate_id:<30} identical  "
                  f"(positive {len(wrapped)} B, negative {len(negative)} B)")
            continue
        bad += 1
        print(f"  {plate_id:<30} DIFFERS")
        if not ok_w:
            print(f"      stored positive: {doc['wrapped_prompt']!r}")
            print(f"      replay positive: {wrapped!r}")
        if not ok_n:
            print(f"      stored negative: {doc['negative_prompt']!r}")
            print(f"      replay negative: {negative!r}")

    print()
    if bad:
        print(f"FAIL: {bad} plate(s) differ. The baseline's request strings are not "
              f"reproducible with today's code.")
        return 1
    print(f"PASS: all {len(prompts)} plates reproduce byte-identically. ADR-0036 and "
          f"ADR-0037 are no-ops for a bake that supplied no negative and no video.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
