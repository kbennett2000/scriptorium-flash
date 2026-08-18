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

# 7. IP-Adapter conditioning passthrough (Cycle 4).
#
#    Scriptorium gives a multi-figure plate a weaker, later anchor -- 0.35 / 0.4
#    against the 0.5 / 0.3 default (p7_render.py:333-340) -- and has always sent
#    it. This handler had no input for it, so every multi-figure plate rendered
#    here was a different computation from home's: 99.8% of pixels different on
#    home's own card. These checks pin all three halves of the fix -- that absent
#    still means the old defaults (so one image measures both arms), that a
#    supplied value is actually used, and that a malformed one is refused rather
#    than silently replaced by a default.
import graph as G  # noqa: E402

reset()
stub(json.dumps(SYSTEM_STATS).encode())
H.render = lambda g: b"\x89PNG\r\n\x1a\n fake"
REF_B64 = "aGVsbG8="  # never decoded: upload_reference is stubbed below
H.upload_reference = lambda b64, name="reference.png": "reference.png"

BASE = {"prompt": "a hollow at dusk", "seed": 1234567, "reference_png_b64": REF_B64}

out = H.handler({"input": dict(BASE)})
check("absent conditioning -> service default weight", out["reference_strength"], 0.5)
check("absent conditioning -> service default start", out["reference_start"], 0.3)
check("absent conditioning -> ip_adapter still on", out["ip_adapter"], True)

out = H.handler({"input": dict(BASE, reference_strength=0.35, reference_start=0.4)})
check("multi-figure weight is used", out["reference_strength"], 0.35)
check("multi-figure start is used", out["reference_start"], 0.4)

# Echoed from the built graph, so a partial override reports the real pair.
out = H.handler({"input": dict(BASE, reference_strength=0.35)})
check("partial override: weight applied", out["reference_strength"], 0.35)
check("partial override: start still default", out["reference_start"], 0.3)

# Strings are accepted (JSON senders vary); booleans are not, because bool is a
# subclass of int and True would arrive as a weight of 1.0.
out = H.handler({"input": dict(BASE, reference_strength="0.35")})
check("numeric string accepted", out["reference_strength"], 0.35)
for bad in (True, "banana", [], {}):
    out = H.handler({"input": dict(BASE, reference_strength=bad)})
    check(f"malformed weight {bad!r} refused", "error" in out, True)
    check(f"malformed weight {bad!r} rendered nothing", "image_png_b64" in out, False)

# Without a reference there is no IP-Adapter node, so conditioning is null
# rather than a default -- the plate genuinely had none.
out = H.handler({"input": {"prompt": "a hollow at dusk", "seed": 1, "reference_strength": 0.35}})
check("no reference -> conditioning is null", out["reference_strength"], None)
check("no reference -> ip_adapter off", out["ip_adapter"], False)

# The mirrored rule itself (graph.conditioning_for_depicted), since verify_port
# and the bench both rebuild home's request from it.
check("0 figures -> service default", G.conditioning_for_depicted([]), (None, None))
check("1 figure  -> service default", G.conditioning_for_depicted(["a"]), (None, None))
check("2 figures -> multi-figure pair", G.conditioning_for_depicted(["a", "b"]), (0.35, 0.4))
check("3 figures -> multi-figure pair", G.conditioning_for_depicted(["a", "b", "c"]), (0.35, 0.4))
check("None      -> service default", G.conditioning_for_depicted(None), (None, None))

# The separability guarantee the comparison set depends on: a request that omits
# the parameters must build the byte-identical graph the pre-Cycle-4 port built.
absent = G.build("p", "n", 1, reference_image="r.png")
explicit_none = G.build("p", "n", 1, reference_image="r.png",
                        reference_strength=None, reference_start=None)
check("omitted == explicit None (byte-identical graph)", absent == explicit_none, True)
check("omitted keeps the pre-Cycle-4 pair",
      (absent["24"]["inputs"]["weight"], absent["24"]["inputs"]["start_at"]), (0.5, 0.3))

print()
if failures:
    print(f"{len(failures)} check(s) failed: {', '.join(failures)}", file=sys.stderr)
    sys.exit(1)
print("all checks passed -- the handler names its GPU and honours per-plate conditioning")
