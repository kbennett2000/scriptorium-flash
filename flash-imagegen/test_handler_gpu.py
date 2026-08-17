#!/usr/bin/env python3
"""Mock-verify that the handler reports the GPU model, not NVIDIA_VISIBLE_DEVICES.

This exists because the hello-world deployment measured in FINDINGS.md got back
``"gpu": "void"`` from ``NVIDIA_VISIBLE_DEVICES`` on a real Runpod serverless
worker. The render endpoint runs on a multi-card pool, so a per-plate timing that
cannot name its card is not a usable measurement.

No GPU, no network, no ComfyUI, no spend: ``_get`` is stubbed. Run it with

    ./test_handler_gpu.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import handler as H  # noqa: E402

# Shape copied from ComfyUI's /system_stats. Only the fields the handler reads
# are load-bearing; the rest is present so the fixture stays recognisable.
SYSTEM_STATS = {
    "system": {"os": "posix", "comfyui_version": "0.27.0", "python_version": "3.11.9"},
    "devices": [
        {
            "name": "cuda:0 NVIDIA RTX A5000 : cudaMallocAsync",
            "type": "cuda",
            "index": 0,
            "vram_total": 25429835776,
            "vram_free": 24230608896,
        }
    ],
}

failures: list[str] = []


def check(label: str, got: object, want: object) -> None:
    if got == want:
        print(f"ok       {label}: {got!r}")
    else:
        print(f"FAIL     {label}: got {got!r}, want {want!r}")
        failures.append(label)


def reset() -> None:
    H._booted = False
    H._gpu_name = None


def stub(payload: bytes | Exception):
    """Replace handler._get with something that returns a canned body."""

    def _get(path: str, timeout: float = 30.0) -> bytes:
        if isinstance(payload, Exception):
            raise payload
        return payload

    H._get = _get


# 1. The name is extracted from a well-formed payload.
check(
    "_device_name reads devices[0].name",
    H._device_name(SYSTEM_STATS),
    "cuda:0 NVIDIA RTX A5000 : cudaMallocAsync",
)

# 2. Degenerate payloads degrade to "unknown" rather than raising. A missing
#    card name must never fail a render -- it is reporting metadata.
check("_device_name with no devices", H._device_name({"devices": []}), "unknown")
check("_device_name with no key", H._device_name({}), "unknown")
check("_device_name with junk device", H._device_name({"devices": ["nope"]}), "unknown")
check("_device_name with blank name", H._device_name({"devices": [{"name": "  "}]}), "unknown")

# 3. wait_for_comfy captures the name from the readiness probe it already makes.
reset()
stub(json.dumps(SYSTEM_STATS).encode())
boot_s = H.wait_for_comfy()
check("wait_for_comfy caches the card", H._gpu_name, "cuda:0 NVIDIA RTX A5000 : cudaMallocAsync")
check("wait_for_comfy marks booted", H._booted, True)
print(f"ok       wait_for_comfy returned {boot_s:.4f}s")

# 4. A second call is free and does not re-probe.
called = {"n": 0}


def counting_get(path: str, timeout: float = 30.0) -> bytes:
    called["n"] += 1
    return json.dumps(SYSTEM_STATS).encode()


H._get = counting_get
check("second wait_for_comfy is a no-op", H.wait_for_comfy(), 0.0)
check("second wait_for_comfy makes no request", called["n"], 0)

# 5. Malformed JSON from /system_stats does not raise and does not block boot.
reset()
stub(b"<html>502 Bad Gateway</html>")
H.wait_for_comfy()
check("malformed /system_stats -> unknown", H._gpu_name, "unknown")
check("malformed /system_stats still boots", H._booted, True)

# 6. End to end: the value reaches the handler's response, and it is the card
#    name rather than anything out of the environment.
reset()
stub(json.dumps(SYSTEM_STATS).encode())
H.render = lambda g: b"\x89PNG\r\n\x1a\n fake"
import os  # noqa: E402

os.environ["NVIDIA_VISIBLE_DEVICES"] = "void"  # what the real worker returned

out = H.handler({"input": {"prompt": "a hollow at dusk", "seed": 1234567}})
check("handler reports the card", out["gpu"], "cuda:0 NVIDIA RTX A5000 : cudaMallocAsync")
check("handler did not report the env var", out["gpu"] == "void", False)
check("handler still reports render_s", isinstance(out.get("render_s"), float), True)
check("handler still reports model_load_s", isinstance(out.get("model_load_s"), float), True)
check("handler passed the seed through", out["seed"], 1234567)

print()
if failures:
    print(f"{len(failures)} check(s) failed: {', '.join(failures)}", file=sys.stderr)
    sys.exit(1)
print("all checks passed -- the handler names its GPU")
