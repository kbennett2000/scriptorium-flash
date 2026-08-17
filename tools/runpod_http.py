#!/usr/bin/env python3
"""Make authenticated Runpod HTTP calls without ever handling the key in a shell.

Why this exists
---------------
Runpod endpoints -- both a deployed Flash app and the hosted per-token public
endpoints -- need an ``Authorization: Bearer`` header. Neither CLI can build one:
``runpodctl`` has no subcommand that invokes an endpoint, and ``flash``'s client
is a Python API rather than a command. The route everyone reaches for is the
one-liner this project flagged in Cycle 1 as a credential-harvesting primitive::

    KEY="${RUNPOD_API_KEY:-$(grep '^apikey' ~/.runpod/config.toml | sed ...)}"

That puts a long-lived plaintext key in a shell variable, the process table, and
the shell history, and every one of those outlives the command.

This module reads ``~/.runpod/config.toml`` itself, inside the process, and the
value never leaves it. There is no ``--api-key`` flag and no way to print the
key: ``redact()`` is applied to anything headed for stdout, stderr, or a saved
response file, and the exception handler below strips headers before re-raising,
because a urllib ``HTTPError`` repr can otherwise carry the request headers into
a traceback.

Both key names are accepted. ``runpodctl`` writes a top-level ``apikey``;
``flash`` writes ``[default].api_key``. They are the same credential under two
names, which is the subject of runpod/flash#363.
"""

from __future__ import annotations

import json
import re
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

CONFIG = Path.home() / ".runpod" / "config.toml"

# Runpod keys are `rpa_` + base32-ish; also catch anything key-shaped that a
# response or error might echo back at us.
_KEYLIKE = re.compile(r"\brpa_[A-Za-z0-9_\-]{8,}")


def redact(text: str) -> str:
    """Blank out anything key-shaped. Applied to every byte we emit or store."""
    return _KEYLIKE.sub("rpa_<redacted>", text)


def _read_key() -> str:
    """Return the API key from the credential file. Never logged, never returned
    to a caller that prints it -- only :func:`auth_header` consumes this."""
    if not CONFIG.is_file():
        raise SystemExit(f"no credential file at {CONFIG}; run `flash login`")
    with CONFIG.open("rb") as fh:
        conf = tomllib.load(fh)

    # flash's schema first, then runpodctl's. Either is fine; both are present
    # on a machine where `flash login` has run after `runpodctl` was configured.
    for value in (conf.get("default", {}).get("api_key"), conf.get("apikey")):
        if isinstance(value, str) and value.strip():
            return value.strip()

    raise SystemExit(
        f"{CONFIG} has neither `[default].api_key` nor a top-level `apikey`; "
        "run `flash login`"
    )


def auth_header() -> dict[str, str]:
    """The Authorization header. Do not print the return value of this."""
    return {"Authorization": f"Bearer {_read_key()}"}


class Response:
    """One HTTP response, with the wall clock it took and no key anywhere in it."""

    def __init__(self, status: int, body: str, seconds: float):
        self.status = status
        self.body = redact(body)
        self.seconds = seconds

    @property
    def json(self) -> Any:
        return json.loads(self.body)

    def __repr__(self) -> str:
        return f"<Response {self.status} in {self.seconds:.3f}s, {len(self.body)}B>"


def post(url: str, payload: dict, timeout: float = 600.0) -> Response:
    """POST JSON with the Bearer header, returning status, body and wall clock.

    Timing is measured around the whole exchange because that is what a caller
    experiences -- on a scaled-to-zero endpoint the first call includes the
    worker's cold start, and separating the two is the point of the measurement.
    """
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"content-type": "application/json", **auth_header()},
        method="POST",
    )
    return _send(req, timeout)


def get(url: str, timeout: float = 600.0) -> Response:
    req = urllib.request.Request(url, headers=auth_header(), method="GET")
    return _send(req, timeout)


def _send(req: urllib.request.Request, timeout: float) -> Response:
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", "replace")
            return Response(resp.status, body, time.monotonic() - t0)
    except urllib.error.HTTPError as exc:
        # An HTTPError carries the request headers, so it must never propagate
        # as-is: `raise ... from None` drops the original from the traceback.
        body = exc.read().decode("utf-8", "replace") if exc.fp else ""
        return Response(exc.code, body, time.monotonic() - t0)
    except urllib.error.URLError as exc:
        raise SystemExit(f"request to {req.full_url} failed: {exc.reason}") from None


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="one authenticated Runpod call")
    ap.add_argument("url")
    ap.add_argument("--data", default=None, help="JSON body; omit for GET")
    ap.add_argument("--repeat", type=int, default=1, help="calls to make, timed")
    ap.add_argument("--timeout", type=float, default=600.0)
    args = ap.parse_args()

    for i in range(args.repeat):
        r = (
            post(args.url, json.loads(args.data), args.timeout)
            if args.data
            else get(args.url, args.timeout)
        )
        print(f"[{i + 1}/{args.repeat}] {r.status}  {r.seconds:.3f}s  {r.body[:400]}")
