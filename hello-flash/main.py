"""The smallest Flash app that deploys and answers one request.

The point is not what it computes. The point is to find out, with real numbers,
how long a Runpod Flash endpoint takes to answer its first request from cold,
and what that costs. Those numbers go in ../FINDINGS.md.

Notes that cost time to learn:

- Everything a remote function needs must be written *inside* the function
  body. `flash dev` ships only the body to the worker, so a module-level import
  or constant raises NameError there. `flash deploy` imports the whole module,
  so the same code can work when deployed and fail in development.

- `workers=(0, 1)` means scale to zero. Runpod bills from when a worker starts
  until it fully stops, so an endpoint sitting at zero workers is what makes
  idle cheap. `idle_timeout` is in *seconds*, and its 60-second default is a
  Flash default that differs from the platform's own.

- `flash dev` is not a local-only command. It executes these functions on
  remote workers, which costs money.
"""

from runpod_flash import Endpoint, GpuGroup

api = Endpoint(
    name="hello-flash",
    gpu=GpuGroup.AMPERE_16,  # 16GB tier: A4000-class, the cheapest GPU pool
    workers=(0, 1),  # scale to zero; never keep a worker warm
    idle_timeout=60,  # seconds, not minutes
    dependencies=[],  # nothing to install, so nothing to slow the cold start
)


@api.post("/predict")
async def predict(data: dict):
    """Echo the request back with proof of which machine ran it."""
    import os
    import socket
    import time

    return {
        "ok": True,
        "echo": data,
        "worker": socket.gethostname(),
        "gpu": os.environ.get("NVIDIA_VISIBLE_DEVICES", "unknown"),
        "replied_at": time.time(),
    }


@api.get("/health")
async def health():
    return {"status": "ok"}
