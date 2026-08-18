#!/usr/bin/env python3
"""Render one Scriptorium plate on a Runpod worker.

One request, one plate. No batching, no queueing of its own -- Scriptorium's
parallel fan-out is a later cycle's change and it will fan out across *workers*,
not inside one.

The worker runs ComfyUI locally and talks to it over HTTP on 127.0.0.1:8188,
which is exactly what imagegen-service does at home. That is deliberate: the
comparison is only honest if both sides run the same sampler implementation, and
a diffusers reimplementation of "euler/normal at 25 steps" is not bit-identical
to ComfyUI's. `verify_port.py` demonstrates the graph builder reproduces home's
output pixel for pixel; running it under the same ComfyUI is what keeps that
true on the remote side.

Timings are reported per request so cold start and warm render can be separated
without reading worker logs:

    model_load_s   time waiting for ComfyUI to become responsive (first call only)
    render_s       ComfyUI's own execution time for this prompt
    total_s        handler entry to handler exit
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import graph as G  # noqa: E402

COMFY = os.environ.get("COMFY_URL", "http://127.0.0.1:8188")
BOOT_TIMEOUT_S = float(os.environ.get("COMFY_BOOT_TIMEOUT_S", "600"))
RENDER_TIMEOUT_S = float(os.environ.get("RENDER_TIMEOUT_S", "300"))

_booted = False
_gpu_name: str | None = None


def _get(path: str, timeout: float = 30.0) -> bytes:
    with urllib.request.urlopen(f"{COMFY}{path}", timeout=timeout) as resp:
        return resp.read()


def _post(path: str, payload: dict, timeout: float = 60.0) -> dict:
    req = urllib.request.Request(
        f"{COMFY}{path}", data=json.dumps(payload).encode(),
        headers={"content-type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read() or b"{}")


def _device_name(stats: dict) -> str:
    """Pull the GPU model name out of ComfyUI's /system_stats.

    ``NVIDIA_VISIBLE_DEVICES`` is not usable for this. On a Runpod serverless
    worker it returns an opaque index or UUID, and the hello-world deployment
    measured in FINDINGS.md got back the literal string ``void``. The card model
    is the one thing a per-plate timing is meaningless without, because
    ``GpuGroup``/multi-type pools hand out whichever card is cheapest and
    available -- so the number has to say which one it describes.

    ComfyUI reports it directly: ``devices[0].name`` is e.g.
    ``cuda:0 NVIDIA RTX A5000 : cudaMallocAsync``.
    """
    devices = stats.get("devices") or []
    if devices and isinstance(devices[0], dict):
        name = devices[0].get("name")
        if isinstance(name, str) and name.strip():
            return name.strip()
    return "unknown"


def wait_for_comfy() -> float:
    """Block until ComfyUI answers, returning how long that took.

    Only the first request on a worker pays this. It is reported separately
    rather than folded into render time, because conflating them is how a cold
    start gets mistaken for a slow model.

    The readiness probe's own response carries the GPU model, so it is captured
    here rather than asked for again.
    """
    global _booted, _gpu_name
    if _booted:
        return 0.0
    t0 = time.monotonic()
    deadline = t0 + BOOT_TIMEOUT_S
    while time.monotonic() < deadline:
        try:
            raw = _get("/system_stats", timeout=5)
            try:
                _gpu_name = _device_name(json.loads(raw or b"{}"))
            except (ValueError, TypeError):
                # A malformed /system_stats must not fail a render. The card
                # name is reporting metadata; the render is the job.
                _gpu_name = "unknown"
            _booted = True
            return time.monotonic() - t0
        except (urllib.error.URLError, OSError, TimeoutError):
            time.sleep(0.5)
    raise RuntimeError(f"ComfyUI did not become ready within {BOOT_TIMEOUT_S}s")


def upload_reference(data_b64: str, name: str = "reference.png") -> str:
    """Stage an IP-Adapter reference portrait into ComfyUI's input directory.

    The reference travels in the request rather than being baked into the image,
    so no character artwork ever enters the container or the registry.
    """
    raw = base64.b64decode(data_b64)
    boundary = "----scriptoriumref"
    body = b"".join([
        f'--{boundary}\r\nContent-Disposition: form-data; name="image"; '
        f'filename="{name}"\r\nContent-Type: image/png\r\n\r\n'.encode(),
        raw,
        f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="overwrite"\r\n\r\ntrue\r\n'.encode(),
        f"--{boundary}--\r\n".encode(),
    ])
    req = urllib.request.Request(
        f"{COMFY}/upload/image", data=body,
        headers={"content-type": f"multipart/form-data; boundary={boundary}"},
        method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        info = json.loads(resp.read())
    sub = info.get("subfolder") or ""
    return f"{sub}/{info['name']}" if sub else info["name"]


def render(prompt_graph: dict) -> bytes:
    """Submit a graph, wait for it, and return the PNG bytes.

    Timing is done by the caller rather than read out of ComfyUI's history,
    which does not report a duration in a form worth parsing. The polling
    interval is 0.25s because a warm plate takes about 8 seconds and a coarser
    poll would show up in the measurement.
    """
    prompt_id = _post("/prompt", {"prompt": prompt_graph})["prompt_id"]
    deadline = time.monotonic() + RENDER_TIMEOUT_S
    while time.monotonic() < deadline:
        entry = (json.loads(_get(f"/history/{prompt_id}") or b"{}")).get(prompt_id)
        if entry and entry.get("outputs"):
            for out in entry["outputs"].values():
                for img in out.get("images", []) or []:
                    q = urllib.parse.urlencode({
                        "filename": img["filename"],
                        "subfolder": img.get("subfolder", ""),
                        "type": img.get("type", "output"),
                    })
                    return _get(f"/view?{q}", timeout=180)
        time.sleep(0.25)
    raise RuntimeError(f"render timed out after {RENDER_TIMEOUT_S}s")


def _opt_float(value: object, field: str) -> float | None:
    """``None`` passes through; anything else must be a real number.

    Booleans are rejected explicitly: ``bool`` is a subclass of ``int``, so
    ``True`` would otherwise arrive as an IP-Adapter weight of 1.0.
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"{field} must be a number, got {type(value).__name__}")
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a number, got {value!r}") from None


def handler(job: dict) -> dict:
    """Runpod serverless entry point.

    Input:
        prompt             required, the wrapped positive prompt
        negative           the caller's negative; APPENDED to the template baseline
        seed               required; Scriptorium derives it deterministically
        width, height      default 832x1216
        reference_png_b64  optional IP-Adapter reference portrait
        reference_strength optional IP-Adapter weight;   absent -> 0.5
        reference_start    optional IP-Adapter start_at; absent -> 0.3
        lora               default true

    `reference_strength` and `reference_start` exist because Scriptorium has
    always computed them per plate and this handler had no way to receive them.
    A plate whose frame holds more than one person gets a weaker, later anchor --
    0.35 / 0.4 against the 0.5 / 0.3 default (p7_render.py:333-340) -- and every
    multi-figure plate rendered here before Cycle 4 used the wrong pair. On home
    hardware that difference alone moves 99.8% of the pixels, which is most of
    what Cycle 3 attributed to silicon on plates 0008, 0011 and 0013.

    Absent means the old defaults, deliberately: it keeps one image able to
    render both the old behaviour and the corrected one, so the interpreter
    change and this change stay separable in the comparison set.
    """
    t0 = time.monotonic()
    inp = job.get("input") or {}

    if "prompt" not in inp:
        return {"error": "prompt is required"}
    if "seed" not in inp:
        # Never default this. Scriptorium derives the seed from the book and
        # plate ids so a plate re-renders identically; inventing one here would
        # quietly destroy that.
        return {"error": "seed is required"}

    # Reject a malformed conditioning value rather than falling back to the
    # default. A silent fallback here renders a plate that is not the one asked
    # for and reports success, which is the failure mode this whole parameter
    # exists to close.
    try:
        strength = _opt_float(inp.get("reference_strength"), "reference_strength")
        start = _opt_float(inp.get("reference_start"), "reference_start")
    except ValueError as exc:
        return {"error": str(exc)}

    boot_s = wait_for_comfy()

    reference = None
    if inp.get("reference_png_b64"):
        reference = upload_reference(inp["reference_png_b64"])

    g = G.build(
        positive=inp["prompt"],
        negative=inp.get("negative", ""),
        seed=int(inp["seed"]),
        width=int(inp.get("width", G.PLATE_WIDTH)),
        height=int(inp.get("height", G.PLATE_HEIGHT)),
        lora=bool(inp.get("lora", True)),
        reference_image=reference,
        reference_strength=strength,
        reference_start=start,
    )

    t1 = time.monotonic()
    png = render(g)
    render_s = time.monotonic() - t1

    return {
        "image_png_b64": base64.b64encode(png).decode(),
        "model_load_s": round(boot_s, 3),
        "render_s": round(render_s, 3),
        "total_s": round(time.monotonic() - t0, 3),
        "width": g["5"]["inputs"]["width"],
        "height": g["5"]["inputs"]["height"],
        "seed": g["3"]["inputs"]["seed"],
        "steps": g["3"]["inputs"]["steps"],
        "cfg": g["3"]["inputs"]["cfg"],
        "sampler": g["3"]["inputs"]["sampler_name"],
        "scheduler": g["3"]["inputs"]["scheduler"],
        "lora": g.get("20", {}).get("inputs", {}).get("lora_name"),
        "ip_adapter": bool(reference),
        # Echoed from the BUILT GRAPH, not from the request, so this records what
        # was actually rendered rather than what was asked for. Null when no
        # reference conditioned this plate. Scriptorium folds this whole response
        # into the plate's provenance, which is what makes a multi-figure plate's
        # conditioning checkable after the fact instead of inferable.
        "reference_strength": g.get("24", {}).get("inputs", {}).get("weight"),
        "reference_start": g.get("24", {}).get("inputs", {}).get("start_at"),
        # The card model, from ComfyUI. Not NVIDIA_VISIBLE_DEVICES -- see
        # _device_name(). Every per-plate number in FINDINGS.md is quoted
        # beside this value.
        "gpu": _gpu_name or "unknown",
    }


if __name__ == "__main__":
    import runpod  # provided by the base image

    runpod.serverless.start({"handler": handler})
