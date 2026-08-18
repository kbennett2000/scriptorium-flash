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
#   python                  3.11.15   (deadsnakes; see the apt block below)
#
# The Python line used to read "3.11" and that vagueness was the defect: the
# distro package behind it was 3.11.0rc1, a 2022 release candidate, against
# home's 3.11.15. Every pin in this list is now an exact version, because a pin
# that names a series rather than a release is not a pin.
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

# --- the interpreter, pinned to the exact release home runs -----------------
# Ubuntu 22.04's own `python3.11` package is 3.11.0rc1 -- a release candidate
# from 2022 -- and under it this container segfaulted on boot every time, inside
# `torch.jit.script` while importing kornia. See the note further down; the
# workaround it describes (PYTORCH_JIT=0) was removed in Cycle 4 in favour of
# this.
#
# deadsnakes carries 3.11.15-1+jammy1, which is home's interpreter exactly
# (`/home/kb/comfyui/.venv/bin/python --version` -> 3.11.15). The version is
# pinned rather than floated: deadsnakes ships only the latest patch in a
# series, so an unpinned install silently drifts off home the day 3.11.16 lands,
# and this file's whole purpose is that it does not drift.
#
# `python3-pip` is deliberately NOT installed: on jammy it targets 3.10 and
# would shadow the interpreter below. `ensurepip` bootstraps pip for 3.11
# itself, which is what the pip line further down then upgrades.
ARG PYTHON_VERSION=3.11.15-1+jammy1
RUN apt-get update && apt-get install -y --no-install-recommends \
        software-properties-common gnupg curl git ca-certificates \
    && add-apt-repository -y ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        python3.11=${PYTHON_VERSION} \
        python3.11-venv=${PYTHON_VERSION} \
        python3.11-dev=${PYTHON_VERSION} \
        python3.11-minimal=${PYTHON_VERSION} \
    && python3.11 -m ensurepip --upgrade \
    && rm -rf /var/lib/apt/lists/*

# Fail the build here, loudly, rather than discovering at runtime that the
# interpreter is not the one this image claims. The old defect was invisible
# precisely because nothing in the build asserted it.
RUN test "$(python3.11 -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')" = "3.11.15" \
    && python3.11 -c "import sys; assert sys.version_info.releaselevel == 'final', sys.version" \
    && echo "interpreter: $(python3.11 --version)"

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

# --- the defect that used to be worked around here, kept as the record ------
#
# Cycle 3 shipped `ENV PYTORCH_JIT=0` at this point in the file. Without it the
# container segfaulted on boot, every time, before ComfyUI served a request:
#
#     Fatal Python error: Segmentation fault
#     Stack (most recent call first):
#       File ".../torch/jit/_script.py", line 1262 in _script_impl
#       File ".../kornia/__init__.py", line 28 in <module>
#       File "/opt/ComfyUI/nodes.py", line 2510 in init_builtin_extra_nodes
#
# The cause was the interpreter, not the packages. kornia 0.8.3, torch
# 2.11.0+cu128, torchvision 0.26.0+cu128, scipy 1.17.1 and safetensors 0.8.0
# were identical on both sides; only the Python differed -- 3.11.0rc1 here
# against 3.11.15 at home -- and only the container crashed, inside a function
# that does deep bytecode introspection and is exactly what a release candidate
# breaks.
#
# Disabling TorchScript fixed the crash but left the container running a
# different configuration from home: JIT off here, on at home, with kornia in
# the IP-Adapter preprocessing path that 7 of the 9 pg-41 plates use.
#
# Cycle 4 removed it by pinning the real interpreter in the apt block above.
# The ENV is gone rather than commented out, because a disabled workaround left
# in place is a thing someone re-enables.
#
# Note for anyone re-running the push: the ENV was deliberately the LAST
# instruction, so that changing it rewrote only the image config and left every
# large layer's digest intact. The apt block has no such property -- editing it
# invalidates ComfyUI, torch, the IP-Adapter nodes and all 10.8 GB of models, so
# this change costs a full rebuild and a full re-push. That was known and
# accepted when it was deferred.

# ComfyUI in the background, then the Runpod handler. The handler waits for
# ComfyUI to answer /system_stats and reports that wait separately as
# model_load_s, so a cold start is never mistaken for a slow render.
CMD ["/bin/sh", "-c", \
     "python3.11 /opt/ComfyUI/main.py --listen 127.0.0.1 --port 8188 --disable-auto-launch & \
      exec python3.11 /opt/app/handler.py"]
