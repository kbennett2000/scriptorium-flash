#!/usr/bin/env python3
"""Verify --from-dir copies, checks, and refuses to trust a bad cache.

The real models are ~11GB, so this runs the same code against synthetic files
with real hashes. The URL is a ``file://`` so the download path is exercised for
real without touching the network.

The property under test is the one that makes the local cache safe to use at
all: **a cached file is verified exactly like a downloaded one, and a cached
file that fails its hash is discarded rather than trusted.** If that did not
hold, a stale file on the build box would produce an image that renders
something other than what the home machine renders, and every timing comparison
in FINDINGS.md would be measuring the wrong thing.

    ./test_fetch_models.py
"""

from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fetch_models as F  # noqa: E402

failures: list[str] = []


def check(label: str, got: object, want: object) -> None:
    if got == want:
        print(f"ok       {label}: {got!r}")
    else:
        print(f"FAIL     {label}: got {got!r}, want {want!r}")
        failures.append(label)


def run(dest: Path, from_dir: Path | None, models) -> tuple[int, str]:
    """Run main() with a synthetic MODELS list, capturing stdout."""
    import contextlib
    import io

    argv = ["fetch_models.py", "--dest", str(dest)]
    if from_dir is not None:
        argv += ["--from-dir", str(from_dir)]

    real_models, real_argv = F.MODELS, sys.argv
    F.MODELS, sys.argv = models, argv
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = F.main()
    finally:
        F.MODELS, sys.argv = real_models, real_argv
    return rc, buf.getvalue()


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    good = b"the weights that home actually runs" * 1000
    digest = hashlib.sha256(good).hexdigest()

    # The "upstream" file, served over file:// so download() runs for real.
    upstream = root / "upstream" / "model.safetensors"
    upstream.parent.mkdir(parents=True)
    upstream.write_bytes(good)
    models = [("checkpoints", "model.safetensors", upstream.as_uri(), len(good), digest)]

    # --- 1. a correct cache is used, and is verified -----------------------
    cache = root / "cache"
    (cache / "checkpoints").mkdir(parents=True)
    (cache / "checkpoints" / "model.safetensors").write_bytes(good)

    dest = root / "dest1"
    rc, out = run(dest, cache, models)
    check("correct cache: exit 0", rc, 0)
    check("correct cache: used the cache", "[local cache]" in out, True)
    check("correct cache: did not download", "fetch " in out, False)
    check(
        "correct cache: file landed intact",
        F.sha256(dest / "checkpoints" / "model.safetensors"),
        digest,
    )
    check("correct cache: no .part left behind",
          list((dest / "checkpoints").glob("*.part")), [])

    # --- 2. a WRONG cache is discarded, not trusted ------------------------
    # This is the whole reason the cache is safe to use.
    bad_cache = root / "badcache"
    (bad_cache / "checkpoints").mkdir(parents=True)
    (bad_cache / "checkpoints" / "model.safetensors").write_bytes(b"a different model entirely")

    dest = root / "dest2"
    rc, out = run(dest, bad_cache, models)
    check("bad cache: exit 0 (recovered)", rc, 0)
    check("bad cache: mismatch was detected", "cache mismatch" in out, True)
    check("bad cache: fell back to download", "download after cache mismatch" in out, True)
    check(
        "bad cache: correct bytes ended up in the image",
        F.sha256(dest / "checkpoints" / "model.safetensors"),
        digest,
    )

    # --- 3. a cache MISS falls through to the URL --------------------------
    dest = root / "dest3"
    rc, out = run(dest, root / "does-not-exist", models)
    check("cache miss: exit 0", rc, 0)
    check("cache miss: downloaded", "[download]" in out, True)

    # --- 4. no --from-dir at all still works (the path everyone else takes) -
    dest = root / "dest4"
    rc, out = run(dest, None, models)
    check("no cache flag: exit 0", rc, 0)
    check("no cache flag: downloaded", "[download]" in out, True)

    # --- 5. an unreachable URL with no cache fails the build loudly --------
    missing = [("checkpoints", "gone.safetensors",
                (root / "upstream" / "nope.safetensors").as_uri(), len(good), digest)]
    dest = root / "dest5"
    rc, out = run(dest, None, missing)
    check("unreachable + no cache: exit 1", rc, 1)
    check("unreachable + no cache: nothing left on disk",
          (dest / "checkpoints" / "gone.safetensors").exists(), False)

    # --- 6. --check-only still reports without fetching --------------------
    dest = root / "dest6"
    argv, real = ["fetch_models.py", "--dest", str(dest), "--check-only"], sys.argv
    real_models = F.MODELS
    F.MODELS, sys.argv = models, argv
    import contextlib
    import io

    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = F.main()
    finally:
        F.MODELS, sys.argv = real_models, real
    check("check-only on empty dest: exit 1", rc, 1)
    check("check-only: reported missing", "missing" in buf.getvalue(), True)
    check("check-only: fetched nothing", dest.exists(), False)

    shutil.rmtree(root, ignore_errors=True)

print()
if failures:
    print(f"{len(failures)} check(s) failed: {', '.join(failures)}", file=sys.stderr)
    sys.exit(1)
print("all checks passed -- the cache is an accelerator, never an authority")
