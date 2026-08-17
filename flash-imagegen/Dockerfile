# syntax=docker/dockerfile:1.7
# ^ must stay the first line: a parser directive is ignored if anything, even a
#   comment, precedes it. It buys the named-build-context override used below.

# Scriptorium's image-generation worker: the home render stack, on a Runpod GPU.
#
# Everything here is pinned to what the home machine is running, because the
# whole point is to render the same computation and compare the time. Loosening
# any pin makes the comparison worth less.
#
#   ComfyUI                 0.27.0 at 6cc8144
#   ComfyUI_IPAdapter_plus  a0f451a
#   torch                   2.11.0+cu128
#   python                  3.11
#
# BUILD THIS IMAGE PRIVATELY. It carries ~11GB of model weights fetched at build
# time, including a LoRA whose licence forbids redistribution. See MODELS.md.
# It must not be pushed to a public registry.

# An empty stand-in for the optional local model cache. A build that passes
#   --build-context modelcache=/path/to/ComfyUI/models
# replaces this stage with that directory; a build that does not gets an empty
# one, finds nothing to copy, and downloads from HuggingFace as before. Either
# way every file is hash-checked before it enters a layer.
FROM scratch AS modelcache

FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    COMFY_URL=http://127.0.0.1:8188

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.11 python3.11-venv python3-pip git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# --- ComfyUI, pinned to the commit home is running -------------------------
ARG COMFY_COMMIT=6cc8144
RUN git clone https://github.com/comfyanonymous/ComfyUI.git /opt/ComfyUI \
    && cd /opt/ComfyUI \
    && git checkout ${COMFY_COMMIT}

# torch first and explicitly, so ComfyUI's requirements cannot resolve a
# different CUDA build than the one measured at home.
RUN python3.11 -m pip install --upgrade pip \
    && python3.11 -m pip install torch==2.11.0+cu128 torchvision torchaudio \
        --index-url https://download.pytorch.org/whl/cu128 \
    && python3.11 -m pip install -r /opt/ComfyUI/requirements.txt \
    && python3.11 -m pip install runpod

# --- IP-Adapter nodes ------------------------------------------------------
# Not built into ComfyUI. Supplies IPAdapterAdvanced, IPAdapterModelLoader,
# CLIPVisionLoader and PrepImageForClipVision, all four of which the graph uses.
ARG IPADAPTER_COMMIT=a0f451a
RUN git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus.git \
        /opt/ComfyUI/custom_nodes/ComfyUI_IPAdapter_plus \
    && cd /opt/ComfyUI/custom_nodes/ComfyUI_IPAdapter_plus \
    && git checkout ${IPADAPTER_COMMIT}

# --- the five model files, fetched and hash-verified -----------------------
# Fails the build on any mismatch. A wrong file would render something that is
# not what home renders, which invalidates the measurement silently rather than
# loudly. ~11GB; this is the slow layer.
#
# The bind mount is the optional local cache declared above. It is a mount, not
# a COPY, so the cache never becomes a layer -- only the verified files written
# to /opt/ComfyUI/models do. A cached file that fails its hash is discarded and
# re-downloaded rather than trusted; see test_fetch_models.py.
COPY fetch_models.py /opt/app/fetch_models.py
RUN --mount=type=bind,from=modelcache,target=/modelcache \
    python3.11 /opt/app/fetch_models.py \
        --dest /opt/ComfyUI/models \
        --from-dir /modelcache

# --- the app ---------------------------------------------------------------
COPY workflow-sdxl-txt2img.json graph.py handler.py /opt/app/
WORKDIR /opt/app

# ComfyUI in the background, then the Runpod handler. The handler waits for
# ComfyUI to answer /system_stats and reports that wait separately as
# model_load_s, so a cold start is never mistaken for a slow render.
CMD ["/bin/sh", "-c", \
     "python3.11 /opt/ComfyUI/main.py --listen 127.0.0.1 --port 8188 --disable-auto-launch & \
      exec python3.11 /opt/app/handler.py"]
