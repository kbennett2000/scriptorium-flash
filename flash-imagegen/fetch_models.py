#!/usr/bin/env python3
"""Download the five model files at container build time and verify every one.

Run from the Dockerfile. Fails closed: a missing file, a short read, or a hash
mismatch aborts the build rather than producing an image that renders something
subtly different from home.

The hashes are the ones in MODELS.md, computed from the files the home machine is
running right now. That is the mechanism by which "same model, same settings" is
checked rather than asserted.

Two deliberate choices:

- **The LoRA comes from the creator's own repository**, not from the two
  third-party re-uploads imagegen-service's installer falls back to, and not from
  CivitAI (which returns 401 unauthenticated for this file and whose terms only
  permit scripted access with credentials). See MODELS.md.
- **The CLIP-vision encoder comes from `h94/IP-Adapter`**, not from LAION, despite
  ComfyUI's filename. The LAION repo's weights include a text tower and are a
  different file; the hash check is what stops that mistake being silent.

    ./fetch_models.py --dest /opt/ComfyUI/models
    ./fetch_models.py --dest /opt/ComfyUI/models --check-only
    ./fetch_models.py --dest /opt/ComfyUI/models --from-dir /modelcache

``--from-dir`` copies from a local ComfyUI models tree before reaching for the
network, which turns an ~11GB download into a disk copy when the build machine is
already running the home stack. **It changes nothing about what ends up in the
image**: the copied file goes through the identical size and SHA256 check, and a
mismatch fails the build exactly as a bad download would. A file missing from the
cache silently falls through to its URL, so the from-scratch path keeps working
for anyone without a local copy.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
import urllib.request
from pathlib import Path

HF = "https://huggingface.co"

# (subdir, filename-as-ComfyUI-wants-it, url, bytes, sha256)
MODELS = [
    (
        "checkpoints",
        "sd_xl_base_1.0.safetensors",
        f"{HF}/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors",
        6_938_078_334,
        "31e35c80fc4829d14f90153f4c74cd59c90b779f6afe05a74cd6120b893f7e5b",
    ),
    (
        "vae",
        "sdxl_vae.safetensors",
        f"{HF}/stabilityai/sdxl-vae/resolve/main/sdxl_vae.safetensors",
        334_641_164,
        "63aeecb90ff7bc1c115395962d3e803571385b61938377bc7089b36e81e92e2e",
    ),
    (
        "loras",
        "ClassipeintXL2.1.safetensors",
        f"{HF}/EldritchAdam/SDXL_Eldritch_LoRAs/resolve/main/ClassipeintXL2.1.safetensors",
        132_865_728,
        "74b377ee27855418a95935852f570f0078a9a7a82cfa4ddc81568fc52adc87fd",
    ),
    (
        "ipadapter",
        "ip-adapter-plus-face_sdxl_vit-h.safetensors",
        f"{HF}/h94/IP-Adapter/resolve/main/sdxl_models/ip-adapter-plus-face_sdxl_vit-h.safetensors",
        847_517_512,
        "677ad8860204f7d0bfba12d29e6c31ded9beefdf3e4bbd102518357d31a292c1",
    ),
    (
        # ComfyUI's name for h94/IP-Adapter's models/image_encoder/model.safetensors.
        # NOT laion/CLIP-ViT-H-14-... , whose weights carry a text tower and are ~3.94GB.
        "clip_vision",
        "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors",
        f"{HF}/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors",
        2_528_373_448,
        "6ca9667da1ca9e0b0f75e46bb030f7e011f44f86cbfb8d5a36590fcd7507b030",
    ),
]


def sha256(path: Path, chunk: int = 8 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def verify(path: Path, size: int, digest: str) -> tuple[bool, str]:
    if not path.exists():
        return False, "missing"
    actual_size = path.stat().st_size
    if actual_size != size:
        return False, f"size {actual_size} != {size}"
    actual = sha256(path)
    if actual != digest:
        return False, f"sha256 {actual[:16]}... != {digest[:16]}..."
    return True, "ok"


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as resp, tmp.open("wb") as out:
        while block := resp.read(8 << 20):
            out.write(block)
    tmp.replace(dest)


def copy_local(src: Path, dest: Path) -> None:
    """Copy from a local models tree, via a .part file like ``download`` does.

    The temp-then-rename keeps a half-copied file from ever being visible at the
    destination path, so an interrupted build cannot leave something that looks
    present but is short.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    shutil.copyfile(src, tmp)
    tmp.replace(dest)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dest", type=Path, required=True,
                    help="ComfyUI models/ directory")
    ap.add_argument("--check-only", action="store_true",
                    help="verify what is already there; download nothing")
    ap.add_argument("--from-dir", type=Path, default=None,
                    help="a local ComfyUI models/ tree to copy from before "
                         "downloading; copies are hash-checked identically")
    args = ap.parse_args()

    failures = 0
    for subdir, name, url, size, digest in MODELS:
        path = args.dest / subdir / name
        ok, why = verify(path, size, digest)

        if ok:
            print(f"ok       {subdir}/{name}")
            continue
        if args.check_only:
            print(f"FAIL     {subdir}/{name}: {why}")
            failures += 1
            continue

        # Prefer the local cache when it holds this file. A cache miss, or a
        # cached file that fails its hash, falls through to the URL -- the cache
        # is an accelerator, never an authority.
        source = "download"
        cached = args.from_dir / subdir / name if args.from_dir else None
        if cached is not None and cached.is_file():
            print(f"copy     {subdir}/{name}  (from {cached})")
            try:
                copy_local(cached, path)
                source = "local cache"
            except Exception as exc:  # noqa: BLE001 - build-time, report and fall back
                print(f"warn     {subdir}/{name}: copy failed ({exc}); downloading")

        if source == "download":
            print(f"fetch    {subdir}/{name}  ({why})")
            try:
                download(url, path)
            except Exception as exc:  # noqa: BLE001 - build-time, report and fail
                print(f"FAIL     {subdir}/{name}: download failed: {exc}")
                failures += 1
                continue

        ok, why = verify(path, size, digest)
        if ok:
            print(f"verified {subdir}/{name}  [{source}]")
        elif source == "local cache":
            # A cached file that does not match is a wrong file, not a slow one.
            # Discard it and take the network copy rather than trusting the box.
            print(f"warn     {subdir}/{name}: cache mismatch ({why}); downloading")
            path.unlink(missing_ok=True)
            try:
                download(url, path)
            except Exception as exc:  # noqa: BLE001
                print(f"FAIL     {subdir}/{name}: download failed: {exc}")
                failures += 1
                continue
            ok, why = verify(path, size, digest)
            if ok:
                print(f"verified {subdir}/{name}  [download after cache mismatch]")
            else:
                print(f"FAIL     {subdir}/{name}: {why}")
                path.unlink(missing_ok=True)
                failures += 1
        else:
            # Fail closed. A wrong file here renders something that is not what
            # the home machine renders, which would quietly invalidate the whole
            # comparison rather than breaking loudly.
            print(f"FAIL     {subdir}/{name}: {why}")
            path.unlink(missing_ok=True)
            failures += 1

    if failures:
        print(f"\n{failures} of {len(MODELS)} models failed verification", file=sys.stderr)
        return 1
    print(f"\nall {len(MODELS)} models present and verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
