#!/usr/bin/env python3
"""Serve an exported static mirror the way Vercel will, so it can be checked first.

`export_static_reader.py` writes a `vercel.json` whose four rewrites let
`/api/library` be a file while `/api/library/{id}/` is a directory. Nothing on a
plain static server exercises that, so this reads the same `vercel.json` and
applies the same rewrites, turning a local directory into a faithful-enough stand-in
to click through before anything is published.

    ./serve_static_mirror.py --site /tmp/site --port 8099
    ./serve_static_mirror.py --site /tmp/site --check      # fetch every route, exit
"""

from __future__ import annotations

import argparse
import http.server
import json
import re
import socketserver
import sys
import urllib.request
from pathlib import Path


def load_rewrites(site: Path) -> list[tuple[re.Pattern, str]]:
    cfg = json.loads((site / "vercel.json").read_text())
    out = []
    for rw in cfg.get("rewrites", []):
        # Vercel's :param syntax -> a named group, same greedy-free semantics.
        pattern = "^" + re.sub(r":(\w+)", r"(?P<\1>[^/]+)", rw["source"]) + "$"
        out.append((re.compile(pattern), rw["destination"]))
    return out


def make_handler(site: Path, rewrites):
    class H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(site), **kw)

        def translate_path(self, path: str) -> str:
            clean = path.split("?", 1)[0].split("#", 1)[0]
            for pat, dest in rewrites:
                m = pat.match(clean)
                if m:
                    for k, v in (m.groupdict() or {}).items():
                        dest = dest.replace(f":{k}", v)
                    return super().translate_path(dest)
            return super().translate_path(clean)

        def log_message(self, *a):  # quiet
            pass

    return H


ROUTES = [
    ("/", "text/html"),
    ("/health", None),
    ("/api/users", None),
    ("/api/library", None),
]


def check(site: Path, port: int, book_ids: list[str]) -> int:
    base = f"http://127.0.0.1:{port}"
    failures = 0

    def fetch(path: str):
        try:
            with urllib.request.urlopen(base + path, timeout=30) as r:
                return r.status, r.read()
        except Exception as e:  # noqa: BLE001
            return 0, str(e).encode()

    for path, _ct in ROUTES:
        status, body = fetch(path)
        ok = status == 200 and len(body) > 0
        failures += not ok
        print(f"  {'ok ' if ok else 'FAIL'} {status:>3}  {path:<44} {len(body):>9} B")

    shelf = json.loads(fetch("/api/library")[1])
    print(f"  shelf lists {len(shelf)} book(s): "
          f"{', '.join(b['id'] + ' = ' + b['title'] for b in shelf)}")

    for book_id in book_ids:
        status, body = fetch(f"/api/library/{book_id}/manifest")
        ok = status == 200
        failures += not ok
        print(f"  {'ok ' if ok else 'FAIL'} {status:>3}  "
              f"/api/library/{book_id}/manifest {len(body):>9} B")
        if not ok:
            continue
        manifest = json.loads(body)
        sys.path.insert(0, "/home/kb/Desktop/projects/scriptorium/server/src")
        from scriptorium.library.checkout import resolve_reader_files
        files = resolve_reader_files(manifest)
        bad = []
        total = 0
        for entry in files:
            st, b = fetch(f"/api/library/{book_id}/files/{entry['path']}")
            total += len(b)
            if st != 200 or len(b) != entry.get("bytes", len(b)):
                bad.append((entry["path"], st, len(b), entry.get("bytes")))
        failures += len(bad)
        print(f"  {'ok ' if not bad else 'FAIL'}      "
              f"{len(files)} reader files fetched, {total / 1e6:.2f} MB, "
              f"{len(bad)} mismatched")
        for path, st, got, want in bad[:10]:
            print(f"        {st} {path} got {got} want {want}")

    print(f"\n{'ALL ROUTES OK' if not failures else f'{failures} FAILURES'}")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--site", type=Path, required=True)
    ap.add_argument("--port", type=int, default=8099)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--book-id", action="append", default=[])
    args = ap.parse_args()

    handler = make_handler(args.site, load_rewrites(args.site))
    socketserver.TCPServer.allow_reuse_address = True

    if not args.check:
        with socketserver.TCPServer(("127.0.0.1", args.port), handler) as httpd:
            print(f"serving {args.site} on http://127.0.0.1:{args.port}  (ctrl-c to stop)")
            httpd.serve_forever()
        return 0

    import threading
    with socketserver.TCPServer(("127.0.0.1", args.port), handler) as httpd:
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        books = args.book_id or [b["id"] for b in json.loads(
            (args.site / "api" / "library.json").read_text())]
        rc = check(args.site, args.port, books)
        httpd.shutdown()
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
