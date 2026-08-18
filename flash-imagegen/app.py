"""The Flash endpoint declaration for the image-generation worker.

Client mode: the container image carries ComfyUI, the models and the handler, so
Flash provisions and scales it rather than shipping a Python function body. That
is forced by size -- `flash build` caps its artifact at 1500MB and the models are
about 11GB -- and it is also what keeps the sampler identical to home.

This is the configuration that produced the project's headline numbers: 18 plates
for the `pg-41` bake and 91 for the `pg-120` showcase book, every one of them on
an RTX 4090, at $0.001742 per warm plate. See FINDINGS.md.

Deploying it is not `flash deploy`. A client-mode endpoint provisions on first
use, so `tools/provision_client_endpoint.py` calls that path directly and prints
the id -- see its docstring for why the obvious command silently creates nothing.

Two settings are load-bearing for cost and are commented where they are set:
`workers=(0, ...)` and the deliberate absence of `volume=`.
"""

import os

from runpod_flash import Endpoint, GpuType, PodTemplate

# Private: the image carries model weights, including a LoRA whose licence
# forbids redistribution. See MODELS.md. Verified private after every push.
IMAGE = "ghcr.io/kbennett2000/scriptorium-imagegen:sdxl-base-1.0-py31115"

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

# Cycle 3 task 6: the 24GB PRO tier, pinned to one exact card.
#
# Task 5 asked for AMPERE_24 by naming two cards -- A5000 and RTX 3090 -- and
# the endpoint read back exactly those two. Runpod then ran every render on an
# "RTX PRO 6000 Blackwell Server Edition MIG 1g.24gb", which is neither. So a
# two-card gpuTypeIds list did not constrain placement.
#
# This pass pins a single GpuType to find out whether one exact card is honoured
# when a list was not. If it is substituted too, the constraint is advisory at
# every level, which is the more important finding of the two.
TIER = GpuType.NVIDIA_GEFORCE_RTX_4090

imagegen = Endpoint(
    name="scriptorium-imagegen",
    image=IMAGE,
    gpu=TIER,

    # Cycle 4: four workers, because that is what makes a fan-out mean anything.
    # Scriptorium now renders plates concurrently (ADR-0038), and concurrency
    # against a one-worker endpoint is just a queue -- max_concurrency defaults to
    # 1, so one worker renders one plate at a time no matter how many arrive.
    # Four is where the return flattens: pg-41 is 16 renders, and past four the
    # bake is dominated by the text steps that stay at home, not by rendering.
    #
    # Still scale-to-zero in intent, and still not in fact. This produces
    # workersMin 0 but ALSO workersStandby 1, which neither runpodctl nor the SDK
    # can set to 0 -- filed as runpod/flash#364. Measured twice at $0.0000000000
    # over 11 m 13 s and 2 h 59 m 37 s, so it is a caveat rather than a blocker,
    # and on stage it is free cold-start insurance. The endpoint is still torn
    # down by name the moment a measurement pass finishes, rather than left up on
    # trust.
    workers=(0, 4),

    # Seconds. The worker stays warm this long after a request, and that time IS
    # billed -- it is the dominant cost of the headline bake, four workers wide.
    # Kept at 60 anyway: a render phase has gaps in it (the portrait phase, a
    # review transition, the runner's 5 s tick), and a worker that dies in one of
    # them pays a fresh cold start of six to seven minutes. Trading ~$0.07 of idle
    # tail against that risk is the right side of the trade when the wall-clock
    # number is the entire point of the cycle.
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
