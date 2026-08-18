#!/usr/bin/env python3
"""Prove the ported graph renders exactly what imagegen-service rendered.

The Runpod app only produces an honest comparison if it runs the same
computation the home machine runs. Reading the settings out of `engine.ts` and
copying them into `graph.py` is not proof of that -- a wrong edge or a missed
default would still look right in a settings table.

So this rebuilds a plate that the home bakery already rendered, using the seed,
prompt and negative prompt recorded in that plate's own provenance file, submits
it to the *local* ComfyUI, and compares the result against the stored PNG pixel
by pixel. Identical pixels mean the port reproduces the original graph, because
SDXL at a fixed seed is deterministic and any difference in model, LoRA,
sampler, scheduler, step count, CFG or size changes the image.

Pixels rather than bytes on purpose: ComfyUI embeds the prompt graph in the PNG
metadata, so byte equality would fail on cosmetic differences like key order
while telling us nothing about the computation.

Free and local. It renders on the home GPU and touches no Runpod resource.

    ./verify_port.py --book-id pg-41 --plate 0001
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
import urllib.request
from pathlib import Path

# numpy and PIL are imported inside main() rather than here, and that is not a
# style preference. `flash build` imports every .py file in the project
# directory to discover Endpoints, so a module-level import of something absent
# from the flash CLI's own environment fails the build of an app this file is
# not even part of. Since v1.4 the only way to exclude a file is to list it in
# .gitignore, which would mean untracking a checked-in tool. Deferring the
# import is the smaller change. See AI-ASSIST.md.

sys.path.insert(0, str(Path(__file__).parent))
import graph as G  # noqa: E402

COMFY = "http://localhost:8188"
LIBRARY = Path("/home/kb/scriptorium-data/library")


def upload_image(path: Path) -> str:
    """Stage a reference portrait into ComfyUI's input dir, as engine.ts does.

    Multipart by hand so this stays dependency-free -- the app already needs
    nothing but the standard library at runtime.
    """
    boundary = "----scriptoriumverify"
    body = b"".join([
        f'--{boundary}\r\nContent-Disposition: form-data; name="image"; '
        f'filename="{path.name}"\r\nContent-Type: image/png\r\n\r\n'.encode(),
        path.read_bytes(),
        f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n".encode(),
        f"--{boundary}--\r\n".encode(),
    ])
    req = urllib.request.Request(
        f"{COMFY}/upload/image", data=body,
        headers={"content-type": f"multipart/form-data; boundary={boundary}"},
        method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        info = json.loads(resp.read())
    name = info["name"]
    sub = info.get("subfolder") or ""
    return f"{sub}/{name}" if sub else name


def post_prompt(prompt_graph: dict) -> str:
    body = json.dumps({"prompt": prompt_graph}).encode()
    req = urllib.request.Request(
        f"{COMFY}/prompt", data=body,
        headers={"content-type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())["prompt_id"]


def await_image(prompt_id: str, timeout: float = 300.0) -> bytes:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with urllib.request.urlopen(f"{COMFY}/history/{prompt_id}", timeout=30) as resp:
            hist = json.loads(resp.read() or b"{}")
        entry = hist.get(prompt_id)
        if entry and entry.get("outputs"):
            for out in entry["outputs"].values():
                for img in out.get("images", []) or []:
                    q = urllib.parse.urlencode({
                        "filename": img["filename"],
                        "subfolder": img.get("subfolder", ""),
                        "type": img.get("type", "output"),
                    })
                    with urllib.request.urlopen(f"{COMFY}/view?{q}", timeout=120) as r:
                        return r.read()
        time.sleep(1.0)
    raise SystemExit(f"timed out waiting for {prompt_id}")


def main() -> int:
    import numpy as np  # deferred: see the note at the top of this file
    from PIL import Image

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--book-id", default="pg-41")
    ap.add_argument("--plate", default="0001")
    # Overrides, for isolating a cause rather than replaying home. Passing the
    # pre-Cycle-4 values (0.5 / 0.3) on a multi-figure plate reproduces the old
    # port's output, which is how the conditioning gap was proved rather than
    # assumed: same GPU, same interpreter, same seed, only these two numbers move.
    ap.add_argument("--reference-strength", type=float, default=None,
                    help="override the IP-Adapter weight (default: what home sent)")
    ap.add_argument("--reference-start", type=float, default=None,
                    help="override the IP-Adapter start_at (default: what home sent)")
    args = ap.parse_args()

    book = LIBRARY / args.book_id
    rec = json.loads((book / "prompts" / f"{args.plate}.json").read_text())
    stored_path = book / "images" / "plates" / f"{args.plate}.png"

    echo = rec["render"]["params_echo"]
    ref = rec.get("reference_slug") or rec["render"].get("reference_slug")

    # The conditioning home used is NOT recorded in provenance -- that is the gap
    # this cycle found. It is recomputed from `derived.depicted`, the same input
    # Scriptorium's `reference_conditioning` reads (p7_render.py:333-340). Without
    # this, every multi-figure plate rebuilds at 0.5/0.3 while home drew it at
    # 0.35/0.4, and the comparison silently measures the wrong thing.
    depicted = ((rec.get("derived") or {}).get("depicted")) or []
    strength, start = G.conditioning_for_depicted(depicted)
    if strength is None:
        provenance = "service default (single figure)"
    else:
        provenance = "multi-figure, ADR-0028"
    if args.reference_strength is not None or args.reference_start is not None:
        strength = args.reference_strength if args.reference_strength is not None else strength
        start = args.reference_start if args.reference_start is not None else start
        provenance = "OVERRIDDEN on the command line -- not what home sent"

    print(f"book={args.book_id} plate={args.plate}")
    print(f"  seed   {echo['seed']}")
    print(f"  size   {echo['width']}x{echo['height']}")
    print(f"  ref    {ref!r}  (IP-Adapter {'on' if ref else 'off'})")
    print(f"  figures depicted: {len(depicted)}")
    print(f"  conditioning      weight={strength if strength is not None else G.REFERENCE_WEIGHT}"
          f"  start_at={start if start is not None else G.REFERENCE_START}"
          f"  ({provenance})")

    uploaded: str | None = None
    if ref:
        portrait = book / "images" / "portraits" / f"{ref}.png"
        if not portrait.exists():
            print(f"  reference portrait missing: {portrait}")
            return 2
        uploaded = upload_image(portrait)
        print(f"  uploaded reference as {uploaded!r}")

    g = G.build(
        positive=rec["wrapped_prompt"],
        negative=rec["negative_prompt"],
        seed=echo["seed"],
        width=echo["width"],
        height=echo["height"],
        lora=True,
        reference_image=uploaded,
        reference_strength=strength,
        reference_start=start,
    )

    print(f"\n  graph nodes: {sorted(g.keys(), key=lambda k: int(k))}")
    print(f"  lora node 20 present: {'20' in g}  -> "
          f"{g.get('20', {}).get('inputs', {}).get('lora_name')} @ "
          f"{g.get('20', {}).get('inputs', {}).get('strength_model')}")
    print(f"  sampler model edge:  {g['3']['inputs']['model']}")
    print(f"  steps/cfg/sampler:   {g['3']['inputs']['steps']}/"
          f"{g['3']['inputs']['cfg']}/{g['3']['inputs']['sampler_name']}"
          f"/{g['3']['inputs']['scheduler']}")
    if "24" in g:
        print(f"  ip-adapter node 24:  weight={g['24']['inputs']['weight']} "
              f"start_at={g['24']['inputs']['start_at']} "
              f"weight_type={g['24']['inputs']['weight_type']!r}")

    print("\nsubmitting to local ComfyUI ...")
    t0 = time.monotonic()
    got = await_image(post_prompt(g))
    elapsed = time.monotonic() - t0
    print(f"  rendered in {elapsed:.2f}s")

    a = np.asarray(Image.open(io.BytesIO(got)).convert("RGB"), dtype=np.int16)
    b = np.asarray(Image.open(stored_path).convert("RGB"), dtype=np.int16)

    print(f"\n  rebuilt shape {a.shape}   stored shape {b.shape}")
    if a.shape != b.shape:
        print("  FAIL: different dimensions")
        return 1

    diff = np.abs(a - b)
    identical = bool((diff == 0).all())
    print(f"  max abs pixel difference: {int(diff.max())}")
    print(f"  differing pixels:         {int((diff.any(axis=2)).sum())} of {a.shape[0]*a.shape[1]}")
    print(f"\n  {'PASS -- pixel-identical, the port reproduces the home graph' if identical else 'FAIL -- images differ'}")
    return 0 if identical else 1


if __name__ == "__main__":
    import urllib.parse  # noqa: E402  (used in await_image)
    sys.exit(main())
