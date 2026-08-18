#!/usr/bin/env python3
"""Find the plates a worker rendered as its first render after a model load.

Cycle 4 established that the first render after a cold model load does not match
the renders after it: 842,339 differing pixels (83.3%), max abs 221, reproducible
to the pixel on home's own card as well as in the container. It is deterministic
behaviour of ComfyUI's dynamic VRAM staging, not noise.

On Runpod every worker's first render is a cold-load render. Pre-warming is meant
to absorb them all, and in the Cycle 4 headline bake it absorbed one of three: the
bake shipped two cold-load images, `portrait-hans-van-ripper` and plate `0011`.

The tell is in the bundle, because the worker echoes it: `render.params_echo`
carries `model_load_s`, and a non-zero value means that image was drawn by a model
that had just been staged. This reads every prompt doc and reports them, so no
cold-load image reaches a published book unnoticed.

    ./cold_load_plates.py --book-id pg-120
    ./cold_load_plates.py --book-id pg-120 --json
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

DATA_ROOT = Path("/home/kb/scriptorium-data")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--book-id", required=True)
    ap.add_argument("--data-root", type=Path, default=DATA_ROOT)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    prompts = sorted((args.data_root / "work" / args.book_id / "prompts").glob("*.json"))
    if not prompts:
        raise SystemExit(f"no prompt docs under work/{args.book_id}/prompts")

    rows = []
    for p in prompts:
        doc = json.loads(p.read_text())
        render = doc.get("render") or {}
        echo = render.get("params_echo") or {}
        if not echo:
            continue  # not rendered yet
        rows.append({
            "plate": p.stem,
            "model_load_s": float(echo.get("model_load_s") or 0.0),
            "render_s": float(echo.get("render_s") or 0.0),
            "gpu": echo.get("gpu", ""),
            "attempts": render.get("attempts"),
        })

    cold = [r for r in rows if r["model_load_s"] > 0]
    warm = [r for r in rows if r["model_load_s"] == 0]

    if args.json:
        print(json.dumps({"rendered": len(rows), "cold_load": cold,
                          "warm_median_s": round(statistics.median(
                              [r["render_s"] for r in warm]), 4) if warm else None},
                         indent=2))
        return 1 if cold else 0

    print(f"book            {args.book_id}")
    print(f"rendered        {len(rows)} images")
    if warm:
        print(f"warm median     {statistics.median([r['render_s'] for r in warm]):.4f} s "
              f"(n={len(warm)})")
    cards = sorted({r["gpu"] for r in rows if r["gpu"]})
    for c in cards:
        print(f"card            {c}")

    if not cold:
        print("\ncold-load plates none -- every image was drawn against a resident "
              "model.")
        return 0

    print(f"\ncold-load plates {len(cold)} -- these do NOT match a warm render and "
          f"must be re-rendered before packaging:")
    for r in cold:
        print(f"  {r['plate']:<28} model_load {r['model_load_s']:>6.3f}s   "
              f"render {r['render_s']:>7.3f}s")
    print("\nRe-render each against a worker that is already warm, then re-run this.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
