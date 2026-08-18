"""Build the ComfyUI prompt graph for one Scriptorium plate.

This is a port, not a redesign. Every value and every edge here is copied from
imagegen-service's `src/engine.ts` and `src/workflows/sdxl-txt2img.json`, because
the whole point of the Runpod app is to render *the same computation* the home
machine renders. A prettier graph would make the comparison meaningless.

Ported from, and kept in step with:

    imagegen-service/src/workflows/sdxl-txt2img.json   the base graph
    imagegen-service/src/engine.ts:210-224             applyLora
    imagegen-service/src/engine.ts:230-278             applyIPAdapter
    imagegen-service/src/engine.ts:145-153             TIER_CONFIG.standard (steps 25)
    imagegen-service/src/style-loras.ts:21-26          the oil-painting recipe
    scriptorium/server/.../p7_render.py:73             _PLATE_SIZE = (832, 1216)

Node ids are the template's own, and the injected ids are the ones engine.ts
picks, so a graph built here is comparable line for line with one built at home:

    3  KSampler                 20  LoraLoader              (injected)
    4  CheckpointLoaderSimple   21  LoadImage               (injected)
    5  EmptyLatentImage         22  IPAdapterModelLoader    (injected)
    6  CLIPTextEncode positive  23  CLIPVisionLoader        (injected)
    7  CLIPTextEncode negative  24  IPAdapterAdvanced       (injected)
    8  VAEDecode                25  PrepImageForClipVision  (injected)
    9  SaveImage
    10 VAELoader
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

Graph = dict[str, dict[str, Any]]

WORKFLOW = Path(__file__).with_name("workflow-sdxl-txt2img.json")

# --- the home configuration, as constants so drift is visible in a diff -------

PLATE_WIDTH = 832
PLATE_HEIGHT = 1216
PORTRAIT_SIZE = 1024

STEPS = 25          # engine.ts TIER_CONFIG.standard; Scriptorium never sends `quality`
CFG = 7             # workflow node "3"
SAMPLER = "euler"   # workflow node "3"
SCHEDULER = "normal"
DENOISE = 1

# style-loras.ts:21-26 -- the oil-painting recipe. `noRefiner: true` is why the
# refiner workflow never runs on this path.
LORA_FILE = "ClassipeintXL2.1.safetensors"
LORA_STRENGTH = 0.8
LORA_TRIGGER = "oil painting"

# engine.ts:74-84. REFERENCE_START is 0.3 rather than 0 for a documented reason
# (imagegen-service ADR-0007): conditioning identity from step 0 lets the
# reference dictate *composition*, which once shipped 84 plates that were
# near-copies of one two-figure reference painting. The early high-noise steps
# must belong to the text prompt alone; identity lands afterwards.
IPADAPTER_FILE = "ip-adapter-plus-face_sdxl_vit-h.safetensors"
CLIP_VISION_FILE = "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"
REFERENCE_WEIGHT = 0.5
REFERENCE_START = 0.3

# p7_render.py:329-330 (Scriptorium ADR-0028). A plate whose frame holds more than
# one person gets a weaker, later anchor: IP-Adapter is global and unmasked, so at
# full strength the second figure inherits the anchor's face and clothes.
#
# These two numbers are the reason this file needed a Cycle 4 change. Scriptorium
# has always sent them as `referenceStrength`/`referenceStart`; the first version of
# this port had no way to receive them, so every multi-figure plate rendered here at
# 0.5/0.3 while home rendered it at 0.35/0.4. That is a different computation, not a
# different GPU, and it accounts for the ~98% divergence Cycle 3 measured on plates
# 0008, 0011 and 0013 -- all three multi-figure -- against 51-79% on the rest.
#
# Scriptorium remains the authority on the rule (`reference_conditioning`,
# p7_render.py:333-340); it is mirrored here only so `verify_port.py` can rebuild
# what home actually sent from a plate's own provenance. `handler.py` never applies
# the rule -- it takes the values the caller computed.
MULTI_FIGURE_STRENGTH = 0.35
MULTI_FIGURE_START = 0.4


def conditioning_for_depicted(depicted: list | None) -> tuple[float | None, float | None]:
    """``(strength, start)`` for a plate's reference, mirroring p7_render.py:333-340.

    ``(None, None)`` means "accept the service defaults" -- which is what a
    single-figure plate does, and why single-figure plates were never affected.
    """
    if len(depicted or []) > 1:
        return MULTI_FIGURE_STRENGTH, MULTI_FIGURE_START
    return None, None


def load_template() -> Graph:
    """The base graph, copied from imagegen-service verbatim."""
    return json.loads(WORKFLOW.read_text())


def apply_lora(graph: Graph, lora_file: str = LORA_FILE,
               strength: float = LORA_STRENGTH) -> None:
    """Port of engine.ts:210-224.

    Inserts a LoraLoader as node "20" between the checkpoint and its consumers,
    then repoints the model and clip edges at it.
    """
    graph["20"] = {
        "class_type": "LoraLoader",
        "inputs": {
            "lora_name": lora_file,
            "strength_model": strength,
            "strength_clip": strength,
            "model": ["4", 0],
            "clip": ["4", 1],
        },
    }
    if "6" in graph:
        graph["6"]["inputs"]["clip"] = ["20", 1]
    if "7" in graph:
        graph["7"]["inputs"]["clip"] = ["20", 1]
    if "3" in graph:
        graph["3"]["inputs"]["model"] = ["20", 0]


def apply_ip_adapter(graph: Graph, image_name: str,
                     weight: float = REFERENCE_WEIGHT,
                     start_at: float = REFERENCE_START,
                     face_crop: bool = True) -> None:
    """Port of engine.ts:230-278.

    Takes its model from the LoRA node when one is present, else the checkpoint,
    and repoints the sampler at the IP-Adapter-modified model. That ordering
    matters: LoRA first, then IP-Adapter on top of it.
    """
    model_source = ["20", 0] if "20" in graph else ["4", 0]

    graph["21"] = {"class_type": "LoadImage", "inputs": {"image": image_name}}
    graph["22"] = {
        "class_type": "IPAdapterModelLoader",
        "inputs": {"ipadapter_file": IPADAPTER_FILE},
    }
    graph["23"] = {
        "class_type": "CLIPVisionLoader",
        "inputs": {"clip_name": CLIP_VISION_FILE},
    }

    image_source = ["21", 0]
    if face_crop:
        # ip-adapter-plus-face is trained on face crops; fed a full bust it
        # transfers the clothing and background too.
        graph["25"] = {
            "class_type": "PrepImageForClipVision",
            "inputs": {
                "image": ["21", 0],
                "interpolation": "LANCZOS",
                "crop_position": "top",
                "sharpening": 0.0,
            },
        }
        image_source = ["25", 0]

    graph["24"] = {
        "class_type": "IPAdapterAdvanced",
        "inputs": {
            "model": model_source,
            "ipadapter": ["22", 0],
            "image": image_source,
            "clip_vision": ["23", 0],
            "weight": weight,
            # "ease in-out" tapers injection at both ends of the window so
            # identity blends in rather than snapping on at start_at.
            "weight_type": "ease in-out",
            "combine_embeds": "concat",
            "start_at": start_at,
            "end_at": 1.0,
            "embeds_scaling": "V only",
        },
    }
    if "3" in graph:
        graph["3"]["inputs"]["model"] = ["24", 0]


def build(
    positive: str,
    negative: str,
    seed: int,
    width: int = PLATE_WIDTH,
    height: int = PLATE_HEIGHT,
    *,
    lora: bool = True,
    reference_image: str | None = None,
    reference_strength: float | None = None,
    reference_start: float | None = None,
) -> Graph:
    """One plate's graph, matching home for the same inputs.

    `seed` is required rather than defaulted. Scriptorium derives it as
    sha256(book_id \\x00 plate_id) so a plate re-renders identically
    (p7_render.py:358-361); a random default here would quietly destroy the
    reproducibility the comparison depends on.

    `reference_strength` and `reference_start` are the per-plate IP-Adapter
    conditioning Scriptorium computes (ADR-0028). `None` keeps REFERENCE_WEIGHT /
    REFERENCE_START, so a caller that does not send them builds a byte-identical
    graph to the pre-Cycle-4 port -- which is what lets one image measure both the
    old behaviour and the corrected one, and keeps the interpreter change separable
    from this one.
    """
    graph = copy.deepcopy(load_template())

    # Positive is SET; negative is APPENDED. engine.ts:562-569:
    #
    #     for (const id of ["6", "12"]) setNodeText(graph, id, positivePrompt);
    #     // Baseline negatives already live in the template; append caller's...
    #     if (params.negativePrompt) appendNodeText(graph, "7", params.negativePrompt);
    #
    # So node "7" keeps the template's own "blurry, lowres, deformed, text,
    # watermark" and the caller's negative is joined onto it with ", ". Replacing
    # it instead -- which is the obvious reading of a settings table, and what
    # this port did first -- silently drops five negative terms and changes every
    # pixel of the output. verify_port.py caught it.
    graph["6"]["inputs"]["text"] = positive
    if negative:
        graph["7"]["inputs"]["text"] = f'{graph["7"]["inputs"]["text"]}, {negative}'

    graph["5"]["inputs"]["width"] = width
    graph["5"]["inputs"]["height"] = height
    graph["5"]["inputs"]["batch_size"] = 1

    graph["3"]["inputs"]["seed"] = seed
    graph["3"]["inputs"]["steps"] = STEPS
    graph["3"]["inputs"]["cfg"] = CFG
    graph["3"]["inputs"]["sampler_name"] = SAMPLER
    graph["3"]["inputs"]["scheduler"] = SCHEDULER
    graph["3"]["inputs"]["denoise"] = DENOISE

    if lora:
        apply_lora(graph)
    if reference_image:
        apply_ip_adapter(
            graph,
            reference_image,
            weight=REFERENCE_WEIGHT if reference_strength is None else reference_strength,
            start_at=REFERENCE_START if reference_start is None else reference_start,
        )

    return graph


def wrap_positive(prompt: str, trigger: str = LORA_TRIGGER) -> str:
    """Prepend the LoRA trigger if it is not already in the prompt.

    Port of style-loras.ts:101-104. Scriptorium's own prompt assembly already
    starts oil-painting plates with "classical oil painting illustration, ...",
    so in practice the trigger is usually present and this is a no-op -- but it
    is the behaviour at home and the port keeps it.
    """
    return prompt if trigger.lower() in prompt.lower() else f"{trigger}, {prompt}"
