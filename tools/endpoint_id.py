#!/usr/bin/env python3
"""Resolve the render endpoint's id, so nobody has to copy-paste it on stage.

Every live-demo tool in here takes an ``--endpoint <14-char-id>``, and the id is
machine-generated noise: ``cire2u3mv4cr3m``. The runbook's own instruction was
"fill it in once at the top of your terminal and paste it into each command",
which is six paste operations under stage lighting, each one a chance to drop a
character into a tool that will then poll a nonexistent endpoint until it times
out.

``runpodctl serverless list`` already prints the id in a JSON ``id`` field. This
reads that, and prints the id alone::

    python3 tools/endpoint_id.py
    cire2u3mv4cr3m

    EP=$(python3 tools/endpoint_id.py)

The tools that take ``--endpoint`` call :func:`resolve` themselves when the flag
is omitted, so the common case needs neither the variable nor the flag.

**It refuses to guess.** Zero endpoints and it says so, pointing at the failure
table rather than printing an empty string that a caller would splice into a URL
and get a 404 from. Two or more and it lists them and asks you to narrow with
``--name``, rather than picking the first and being silently wrong about which
endpoint the demo just warmed. Both refusals exit non-zero, so ``EP=$(...)``
under ``set -e`` stops rather than continuing with nothing.

No credentials are handled here: ``runpodctl`` reads its own config.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys

# The endpoint this repo's demo actually uses. A substring, not an exact match,
# so a suffixed rehearsal endpoint (scriptorium-imagegen-2) still resolves.
DEFAULT_NAME = "scriptorium"


class NoEndpoint(SystemExit):
    """Raised as an exit: there is nothing to resolve, and guessing is worse."""


def listing() -> list[dict]:
    """Every serverless endpoint on the account, as runpodctl reports it."""
    if shutil.which("runpodctl") is None:
        raise NoEndpoint("runpodctl is not on PATH; see GETTING-STARTED.md")
    proc = subprocess.run(
        ["runpodctl", "serverless", "list"],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        raise NoEndpoint(f"runpodctl serverless list failed: {proc.stderr.strip()}")
    try:
        body = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise NoEndpoint(
            "runpodctl serverless list did not return JSON:\n" + proc.stdout[:400]
        )
    return body if isinstance(body, list) else []


def resolve(name: str | None = DEFAULT_NAME) -> str:
    """The one matching endpoint's id, or an exit explaining why there isn't one."""
    endpoints = listing()
    if name:
        endpoints = [e for e in endpoints if name.lower() in (e.get("name") or "").lower()]

    if not endpoints:
        where = f" matching {name!r}" if name else ""
        raise NoEndpoint(
            f"no serverless endpoint{where}.\n"
            "See 'Endpoint missing' in docs/DEMO-RUNBOOK.md; recovering costs "
            "about eight minutes, so if you are inside that, go to the book."
        )
    if len(endpoints) > 1:
        rows = "\n".join(f"  {e.get('id')}  {e.get('name')}" for e in endpoints)
        raise NoEndpoint(
            f"{len(endpoints)} endpoints match {name!r}; narrow it with --name:\n{rows}"
        )
    return endpoints[0]["id"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", default=DEFAULT_NAME,
                    help=f"substring of the endpoint name (default {DEFAULT_NAME!r}); "
                         f"pass '' to consider every endpoint on the account")
    ap.add_argument("--verbose", action="store_true",
                    help="also print the name and health URL, to stderr")
    args = ap.parse_args()

    endpoint_id = resolve(args.name or None)
    if args.verbose:
        match = next(e for e in listing() if e["id"] == endpoint_id)
        print(f"name    {match.get('name')}", file=sys.stderr)
        print(f"health  {(match.get('urls') or {}).get('health')}", file=sys.stderr)
    print(endpoint_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
