#!/usr/bin/env python3
"""Read the account balance until it stops moving, and say so only when it has.

Serverless spend cannot be read off a response; it has to be read off the balance,
and the balance lags the charge by minutes. Cycle 3 learned this twice. Once when a
read taken 60 s after the last call produced a "3.26x under list price" claim that
was simply wrong. And once in `render_bench.settled_balance()`, which accepts two
equal reads 30 s apart -- a test for *stable*, not for *settled*. A balance that
has not started moving yet is perfectly stable. Both render `summary.json` files
carry wrong `cost_usd` values because of it.

So this asks for more: N consecutive identical reads spanning a real span of wall
clock, defaulting to 6 reads at 45 s, which is the cadence that produced the
Cycle 4 evidence by hand. That loop was run in a terminal and never committed;
this is it, committed.

Emits the same append-only log format the Cycle 4 run left behind, one
`HH:MM:SSZ  <balance>` line per read, so the two are comparable:

    ./settle_balance.py --out runs/pg-120-runpod/balance-settle.log
    ./settle_balance.py --before          # capture an opening balance and exit
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def balance() -> str:
    """Client balance as an exact decimal string -- never a float.

    The figures in this project run to ten decimal places and are reconciled to
    1e-10, so parsing through a float would lose the thing being measured.
    """
    out = subprocess.run(
        ["runpodctl", "user"], capture_output=True, text=True, timeout=120,
    )
    if out.returncode != 0:
        raise SystemExit(f"runpodctl user failed: {out.stderr.strip()[:300]}")
    doc = json.loads(out.stdout)
    if "clientBalance" not in doc:
        raise SystemExit(f"no clientBalance in: {sorted(doc)}")
    return f"{doc['clientBalance']:.10f}"


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%SZ")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--reads", type=int, default=6,
                    help="consecutive identical reads required to call it settled")
    ap.add_argument("--gap", type=float, default=45.0, help="seconds between reads")
    ap.add_argument("--max-reads", type=int, default=40)
    ap.add_argument("--before", action="store_true",
                    help="take one read and exit, for an opening balance")
    args = ap.parse_args()

    lines: list[str] = []

    def emit(line: str) -> None:
        lines.append(line)
        print(line, flush=True)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            with args.out.open("a") as f:
                f.write(line + "\n")

    if args.before:
        emit(f"{stamp()}  {balance()}")
        return 0

    run = 0
    last: str | None = None
    for i in range(args.max_reads):
        b = balance()
        emit(f"{stamp()}  {b}")
        run = run + 1 if b == last else 1
        last = b
        if run >= args.reads:
            span = (run - 1) * args.gap
            print(f"\nsettled: {args.reads} identical reads over {span:.0f} s -> {b}",
                  flush=True)
            return 0
        if i < args.max_reads - 1:
            time.sleep(args.gap)

    print(f"\nNOT SETTLED after {args.max_reads} reads -- the balance was still "
          f"moving. Do not record a cost from this.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
