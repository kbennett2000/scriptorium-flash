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

from runpod_flash import Endpoint, GpuGroup, PodTemplate

# The image must be private: it carries model weights, including a LoRA whose
# licence forbids redistribution. See MODELS.md.
IMAGE = "REGISTRY_PLACEHOLDER/scriptorium-imagegen:sdxl-base-1.0"

# 24GB tier -- L4 / A5000 / RTX 3090 -- at $0.69/hr. Chosen as roughly comparable
# in raw speed to the home RTX 5070, so the measured difference reflects the
# platform rather than a hardware mismatch. GpuGroup picks the cheapest card in
# the tier, so the handler reports which one actually ran and that goes in
# FINDINGS.md beside the number.
TIER = GpuGroup.AMPERE_24

imagegen = Endpoint(
    name="scriptorium-imagegen",
    image=IMAGE,
    gpu=TIER,

    # Scale to zero. An idle endpoint at zero workers bills nothing; a minimum
    # of 1 bills continuously at the full hourly rate -- about $497/month on this
    # tier -- and would defeat the entire cost argument.
    workers=(0, 1),

    # Seconds. The worker stays warm this long after a request, and that time IS
    # billed. Kept short for measurement; a real workload fanning out plates
    # would raise it so a burst does not pay repeated cold starts.
    idle_timeout=60,

    # NO volume=. A network volume bills continuously whether or not a worker
    # runs -- roughly $7/month for the 100GB default -- and it is the one thing
    # that would break the $0-at-idle result established in FINDINGS.md. The
    # weights live in the image instead.

    # 64GB is the default and holds the ~11GB of weights with room to spare.
    template=PodTemplate(containerDiskInGb=64),

    flashboot=True,
    accelerate_downloads=True,
)
