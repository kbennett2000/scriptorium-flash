#!/usr/bin/env python3
"""Provision a Flash client-mode (`image=`) Endpoint and print its id.

Why this exists: `flash deploy` does not provision a client-mode endpoint. It
builds and uploads an artifact, creates the app and environment, reports
"deployed to production", and writes a manifest containing `"resources": {}`.
`flash env get` then says "no resources". Nothing is created and nothing warns.

Client-mode endpoints provision on first use instead, inside
`Endpoint._ensure_endpoint_ready()`, which `run()`/`runsync()` call. This script
calls it directly so provisioning is a separate, timestamped step and the first
render can be timed as a request rather than as a deploy.

    RUNPOD_REGISTRY_AUTH_ID=<id> ./provision_client_endpoint.py --app-dir ../flash-imagegen
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import sys
import time
from pathlib import Path


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--app-dir", default=".", help="directory containing app.py")
    ap.add_argument("--attr", default="imagegen", help="Endpoint attribute name")
    args = ap.parse_args()

    app_path = Path(args.app_dir).resolve() / "app.py"
    if not app_path.is_file():
        raise SystemExit(f"no app.py at {app_path}")
    sys.path.insert(0, str(app_path.parent))

    spec = importlib.util.spec_from_file_location("flash_app", app_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ep = getattr(mod, args.attr)

    print(f"provision start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}", flush=True)
    t0 = time.monotonic()
    endpoint_id = await ep._ensure_endpoint_ready()
    print(f"provision took  {time.monotonic() - t0:.2f}s")
    print(f"provision end   {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    print(f"ENDPOINT_ID={endpoint_id}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
