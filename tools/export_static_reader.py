#!/usr/bin/env python3
"""Freeze a published Scriptorium book into a static site the real reader can read.

The reader is normally served by the bakery on the LAN and talks to it over five
GET routes. Those five are the whole read path -- checkout downloads a bundle once
and everything after that is local. So a book can be put on a public static host
with no server at all, by laying the same five routes out as files:

    /health                              -> health.json      (via rewrite)
    /api/users                           -> api/users.json   (via rewrite)
    /api/library                         -> api/library.json (via rewrite)
    /api/library/{id}/manifest           -> .../manifest.json (via rewrite)
    /api/library/{id}/files/{path}       -> real files, served directly

The rewrites exist because `/api/library` has to be a file and `/api/library/{id}/`
has to be a directory, and one path cannot be both. `vercel.json` resolves that.

What does NOT work, and is recorded rather than hidden: the sync routes are PUTs
(`/api/sync/annotations/...`, `/api/sync/positions/...`). Highlights and reading
position will not survive on a static host. The reader already probes `/health`
and degrades when the server is unreachable, so this is a reduced reader, not a
broken one -- but a demo should not imply otherwise.

Which files a reader downloads is not guessed here: `resolve_reader_files` is
imported from the Scriptorium server, the same function `GET /api/library` uses to
compute `total_bytes_reader`. It expands the `reader_required` globs and collapses
every `-rN` image group to its highest revision.

    ./export_static_reader.py --book-id pg-120 --out /tmp/site
    ./export_static_reader.py --book-id pg-120 --out /tmp/site --reader-dist ../scriptorium/reader/dist
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.request
from pathlib import Path

SCRIPTORIUM = Path("/home/kb/Desktop/projects/scriptorium")
sys.path.insert(0, str(SCRIPTORIUM / "server" / "src"))

from scriptorium.library.checkout import resolve_reader_files  # noqa: E402

BASE = "http://localhost:8720"


def get(path: str) -> bytes:
    with urllib.request.urlopen(BASE + path, timeout=120) as r:
        return r.read()


def get_json(path: str):
    return json.loads(get(path))


def write(dest: Path, data: bytes) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return len(data)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--book-id", required=True, action="append",
                    help="repeatable; the shelf lists exactly these books")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--reader-dist", type=Path,
                    default=SCRIPTORIUM / "reader" / "dist")
    args = ap.parse_args()

    out: Path = args.out
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    # 1. the reader itself, built same-origin (no VITE_SERVER_URL)
    if not (args.reader_dist / "index.html").exists():
        raise SystemExit(f"no reader build at {args.reader_dist} -- run `npm run build`")
    shutil.copytree(args.reader_dist, out, dirs_exist_ok=True)
    app_bytes = sum(p.stat().st_size for p in args.reader_dist.rglob("*") if p.is_file())
    print(f"reader app        {app_bytes / 1e6:.2f} MB")

    # 2. /health -- the reachability probe. Reported reachable so the shelf renders;
    #    the sync layer will still fail its PUTs, which is the honest limitation.
    write(out / "health.json", json.dumps({
        "status": "ok",
        "static_mirror": True,
        "note": "Static export. Reading works fully; sync (highlights, reading "
                "position) is unavailable because it needs PUT.",
    }).encode())

    # 3. /api/users
    write(out / "api" / "users.json", get("/api/users"))

    # 4. /api/library -- filtered to the books being shipped
    shelf = [b for b in get_json("/api/library") if b["id"] in args.book_id]
    if len(shelf) != len(args.book_id):
        missing = set(args.book_id) - {b["id"] for b in shelf}
        raise SystemExit(f"not published: {sorted(missing)}")
    write(out / "api" / "library.json", json.dumps(shelf).encode())

    # 5. per book: the manifest, and every file the reader will actually fetch
    total = 0
    for book_id in args.book_id:
        manifest = get_json(f"/api/library/{book_id}/manifest")
        base = out / "api" / "library" / book_id
        write(base / "manifest.json", json.dumps(manifest).encode())

        files = resolve_reader_files(manifest)
        for entry in files:
            rel = entry["path"]
            total += write(base / "files" / rel, get(
                f"/api/library/{book_id}/files/{rel}"))
        print(f"{book_id:<17} {len(files)} files, {total / 1e6:.2f} MB "
              f"(manifest says total_bytes_reader "
              f"{manifest.get('total_bytes_reader', 0) / 1e6:.2f} MB)")

    # 6. the rewrites that let /api/library be both a file and a directory
    write(out / "vercel.json", json.dumps({
        "rewrites": [
            {"source": "/health", "destination": "/health.json"},
            {"source": "/api/users", "destination": "/api/users.json"},
            {"source": "/api/library", "destination": "/api/library.json"},
            {"source": "/api/library/:id/manifest",
             "destination": "/api/library/:id/manifest.json"},
        ],
        # No content-type overrides. Every rewrite lands on a real .json file so
        # Vercel infers it, and a blanket rule on /api/(.*) would have mislabelled
        # the plate images, which live under /api/library/{id}/files/.
    }, indent=2).encode())

    grand = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    print(f"\nsite              {grand / 1e6:.2f} MB at {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
