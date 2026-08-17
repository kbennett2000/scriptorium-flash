"""The Flash endpoint declaration for the image-generation worker.

Client mode: the container image carries ComfyUI, the models and the handler, so
Flash provisions and scales it rather than shipping a Python function body. That
is forced by size -- `flash build` caps its artifact at 1500MB and the models are
about 11GB -- and it is also what keeps the sampler identical to home.

NOTHING HERE IS DEPLOYED YET. Deployment is gated on Kris's approval of a cost
estimate, and separately blocked until `flash login` has been run once, because
flash cannot read the credential file runpodctl wrote. See FINDINGS.md.

Two settings are load-bearing for cost and are commented where they are set:
`workers=(0, ...)` and the deliberate absence of `volume=`.
"""

import os

from runpod_flash import Endpoint, GpuType, PodTemplate

# Private: the image carries model weights, including a LoRA whose licence
# forbids redistribution. See MODELS.md. Verified private after every push.
IMAGE = "ghcr.io/kbennett2000/scriptorium-imagegen:sdxl-base-1.0"

# Runpod needs its own credential to pull a private image. It is created in the
# console (the CLI's only interface is `runpodctl registry create --password
# <string>`, which would put a registry password in the process table and the
# shell history) and referenced here by id. The id is not a secret; it is read
# from the environment anyway so the deploy fails loudly rather than silently
# pulling nothing when it is unset.
#
# `containerRegistryAuthId` is undocumented: it is absent from
# `docs.runpod.io/flash/custom-docker-images`, which says only "configure Docker
# registry authentication in Runpod console", and absent from the flash skill's
# PodTemplate reference. It exists in the SDK and is threaded into the deploy
# manifest, which is how it was found. See AI-ASSIST.md.
REGISTRY_AUTH_ID = os.environ["RUNPOD_REGISTRY_AUTH_ID"]

# The 24GB tier by card rather than by GpuGroup.AMPERE_24.
#
# That group is L4 / A5000 / RTX 3090 / MIG-24, and GpuGroup takes the cheapest
# card available. An L4 is a very different machine from home's RTX 5070 for
# SDXL, so drawing one would make the headline per-plate number a story about
# card selection rather than about Runpod. Naming two comparable cards keeps the
# comparison honest and still leaves two sources of supply, which matters --
# every 24GB card currently reports stockStatus "Low".
#
# The handler reports which card actually ran, read from ComfyUI's
# /system_stats, and FINDINGS.md quotes it beside the timing.
TIER = [GpuType.NVIDIA_RTX_A5000, GpuType.NVIDIA_GEFORCE_RTX_3090]

imagegen = Endpoint(
    name="scriptorium-imagegen",
    image=IMAGE,
    gpu=TIER,

    # Scale to zero -- with a caveat measured this cycle. This produces
    # workersMin 0 but ALSO workersStandby 1, so Flash holds one worker warm
    # rather than truly scaling to zero, and neither runpodctl nor the SDK
    # exposes a way to set standby to 0. Measured over 11 minutes on the 16GB
    # tier, that warm worker billed nothing (FINDINGS.md), which is why this is
    # a caveat and not a blocker -- but the endpoint is still torn down by name
    # the moment a measurement pass finishes, rather than left up on trust.
    workers=(0, 1),

    # Seconds. The worker stays warm this long after a request, and that time IS
    # billed. Kept short for measurement; a real workload fanning out plates
    # would raise it so a burst does not pay repeated cold starts.
    idle_timeout=60,

    # NO volume=. A network volume bills continuously whether or not a worker
    # runs -- roughly $7/month for the 100GB default -- and it is the one thing
    # that would break the $0-at-idle result established in FINDINGS.md. The
    # weights live in the image instead.

    # 64GB against a 17.66GB image that unpacks to roughly 24GB. Room to spare,
    # and no network volume, so nothing here outlives the worker.
    template=PodTemplate(
        containerDiskInGb=64,
        containerRegistryAuthId=REGISTRY_AUTH_ID,
    ),

    flashboot=True,
    accelerate_downloads=True,
)
