#!/usr/bin/env python3
"""Cost out a container-image diet in the only unit that matters: bytes pulled.

The cold start on this endpoint is ~490 s and 478.2 s of it is image pull plus
worker start, so every candidate removal has to be priced in *compressed* layer
bytes -- what the registry actually ships -- not in what the layer unpacks to and
certainly not in what `docker images` reports.

Three different numbers describe this one image, and only one of them is the pull:

    docker images  DISK USAGE    42.0 GB   compressed blobs AND the unpacked
                                           snapshot, counted together
    docker history  layer sum    24.26 GB  what it unpacks to on the worker
    registry manifest, summed    17.72 GB  what Runpod pulls   <-- this one

FINDINGS.md previously attributed cold-start differences to the 42 GB figure. It
is not a size; it is two sizes added together by the containerd store.

Compression ratios below are measured per layer (manifest bytes / history bytes)
rather than assumed, because they differ by an order of importance: safetensors
are already-compressed weights and barely shrink (0.92), while shared objects and
Python trees roughly halve (0.55).

    ./image_diet.py
    ./image_diet.py --pull-seconds 478.2 --pull-bytes 17.72e9
"""

from __future__ import annotations

import argparse

GB = 1e9

# Measured: `docker manifest inspect --verbose` (compressed) against
# `docker history` (uncompressed), same image, same day.
LAYERS = [
    # name,                        unpacked GB, compressed GB
    ("models (fetch_models.py)",         10.80,  9.951),
    ("torch 2.11.0+cu128 + reqs",         8.48,  4.690),
    ("CUDA 12.8 apt libraries",           3.11,  2.058),
    ("cuDNN 9 apt",                       1.05,  0.704),
    ("python3.11 apt + deadsnakes",       0.363, 0.064),
    ("cuda-cudart + cuda-compat",         0.204, 0.109),
    ("ComfyUI clone",                     0.144, 0.102),
    ("ubuntu:22.04 base",                 0.0875, 0.030),
    ("everything else",                   0.019, 0.012),
]

# ratio for things living inside a given layer
R_MODELS = 9.951 / 10.80   # already-compressed weights
R_PY = 4.690 / 8.48        # .so files and Python trees

# name, saved-unpacked GB, saved-compressed GB, fidelity risk, verified how
CANDIDATES = [
    (
        "Drop the CUDA base image (nvidia/cuda -> ubuntu:22.04)",
        3.11 + 1.05, 2.058 + 0.704,
        "none",
        "ldd on libtorch_cuda.so: every CUDA library resolves to the pip "
        "nvidia/* wheels, not one to /usr/local/cuda-12.8 or the apt libcudnn",
    ),
    (
        "Store the CLIP vision encoder fp16 instead of fp32",
        1.264, 1.264 * R_MODELS,
        "MOVES PIXELS -- must pass verify_port.py first",
        "safetensors header: 520 F32 tensors, 2.53 GB; SDXL base and the "
        "IP-Adapter are already F16",
    ),
    (
        "Drop nccl + nvshmem + cusparseLt from the torch wheels",
        1.010, 1.010 * R_PY,
        "none if it imports",
        "multi-GPU collectives, multi-node shared memory and sparse tensor "
        "cores; one card, dense SDXL. torch dlopens at import, so test",
    ),
    (
        "Drop ComfyUI workflow-template media packages",
        0.370, 0.370 * R_PY,
        "none",
        "web-UI sample assets; the handler drives ComfyUI over its HTTP API "
        "and never serves the UI",
    ),
    (
        "Store the SDXL VAE fp16 instead of fp32",
        0.167, 0.167 * R_MODELS,
        "MOVES PIXELS -- must pass verify_port.py first",
        "safetensors header: 249 F32 tensors, 335 MB",
    ),
    (
        "Drop av, av.libs, botocore, boto3, OpenGL",
        0.168, 0.168 * R_PY,
        "none",
        "video muxing, AWS and GL bindings; this renders still images",
    ),
]

# Deliberately NOT costed as savings -- listed so the reader knows they were
# considered and why they are not in the table.
REJECTED = [
    ("triton (641 MB)", "torch imports it for inductor; removing it is a "
                        "coin-flip on import and saves 0.355 GB. Not worth "
                        "the risk for 10 s of pull."),
    ("SDXL base checkpoint (6.94 GB)", "already F16. There is no smaller "
                                       "honest variant of the model this "
                                       "project pinned and verified."),
    ("pip cache", "PIP_NO_CACHE_DIR=1 is already set. Nothing to reclaim."),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pull-bytes", type=float, default=17.72 * GB,
                    help="measured compressed image size")
    ap.add_argument("--pull-seconds", type=float, default=478.2,
                    help="measured pull + worker start, FINDINGS.md")
    ap.add_argument("--cold-start", type=float, default=489.82,
                    help="measured cold start wall, FINDINGS.md")
    args = ap.parse_args()

    rate = args.pull_bytes / args.pull_seconds  # bytes/s
    print(f"measured pull   {args.pull_bytes / GB:.2f} GB in {args.pull_seconds:.1f} s "
          f"= {rate / 1e6:.1f} MB/s")
    print(f"cold start      {args.cold_start:.2f} s wall, of which "
          f"{100 * args.pull_seconds / args.cold_start:.0f}% is pull\n")

    unp = sum(u for _, u, _ in LAYERS)
    cmp_ = sum(c for _, _, c in LAYERS)
    print(f"{'layer':<34} {'unpacked':>9} {'pulled':>9} {'% of pull':>10}")
    for name, u, c in LAYERS:
        print(f"{name:<34} {u:>8.2f}G {c:>8.2f}G {100 * c / cmp_:>9.1f}%")
    print(f"{'TOTAL':<34} {unp:>8.2f}G {cmp_:>8.2f}G {100.0:>9.1f}%\n")

    print(f"{'candidate removal':<52} {'saved':>8} {'pull':>8}")
    print(f"{'':<52} {'(pulled)':>8} {'time':>8}")
    total_c = 0.0
    for name, _u, c, risk, _how in CANDIDATES:
        total_c += c
        print(f"{name:<52} {c:>7.2f}G {c * GB / rate:>7.1f}s"
              + ("   <-- fidelity risk" if risk.startswith("MOVES") else ""))
    print(f"{'TOTAL':<52} {total_c:>7.2f}G {total_c * GB / rate:>7.1f}s\n")

    safe = sum(c for _, _u, c, risk, _h in CANDIDATES if not risk.startswith("MOVES"))
    print(f"of which no-fidelity-risk:                           "
          f"{safe:>7.2f}G {safe * GB / rate:>7.1f}s")
    new_pull = args.pull_bytes / GB - total_c
    new_cold = args.cold_start - total_c * GB / rate
    print(f"\nimage after the full diet   {new_pull:.2f} GB pulled "
          f"({100 * total_c / (args.pull_bytes / GB):.0f}% smaller)")
    print(f"cold start after the diet   ~{new_cold:.0f} s, against "
          f"{args.cold_start:.0f} s now")
    print(f"\nStated plainly: {args.cold_start / 60:.1f} min becomes "
          f"~{new_cold / 60:.1f} min. The diet does not remove the cold start,")
    print("it shortens it. A demo still cannot hide a six-minute wait; the "
          "warm-up\nprocedure is what removes it, and that is free.")

    print("\nconsidered and rejected:")
    for name, why in REJECTED:
        print(f"  {name:<34} {why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
