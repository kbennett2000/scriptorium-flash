# flash-imagegen

The production Flash app: Scriptorium's plate renderer, on a Runpod GPU instead
of the desktop.

**Status: built, pushed private, deployed and measured on two GPU tiers.** It
rendered the 18 plates of the headline bake and the 91 of the showcase book. A
warm plate takes **4.2790 s** against home's **7.595 s**, and costs
**$0.001742**. Every number is in [../FINDINGS.md](../FINDINGS.md); the one-page
summary is [../docs/NUMBERS.md](../docs/NUMBERS.md).

## What it does

One request, one 832×1216 plate. The worker runs ComfyUI and submits the same
graph imagegen-service submits at home: SDXL base 1.0, the ClassipeintXL2.1 style
LoRA at 0.8, and — when the plate has a character reference — IP-Adapter face
conditioning at weight 0.5 starting 30% into the schedule.

Rendering runs on ComfyUI rather than a diffusers reimplementation on purpose.
"euler/normal at 25 steps" is not bit-identical between implementations, and a
comparison against the home 7.6 s only means something if both sides compute the
same thing.

## The fidelity claim, and how it is checked

The settings are copied from imagegen-service. Copying settings is not proof, so
`verify_port.py` rebuilds a plate the home bakery already rendered — using the
seed, prompt and negative prompt from that plate's own provenance file — submits
it to the local ComfyUI, and compares against the stored PNG pixel by pixel.

```
$ ./verify_port.py --book-id pg-41 --plate 0001     # LoRA path
  max abs pixel difference: 0
  differing pixels:         0 of 1011712
  PASS -- pixel-identical, the port reproduces the home graph

$ ./verify_port.py --book-id pg-41 --plate 0003     # LoRA + IP-Adapter path
  max abs pixel difference: 0
  differing pixels:         0 of 1011712
  PASS -- pixel-identical, the port reproduces the home graph
```

Pixels rather than bytes, because ComfyUI embeds the prompt graph in the PNG
metadata and byte equality would fail on key ordering while proving nothing about
the computation.

**It failed the first time, and that is the point of having it.** The initial port
*set* the negative prompt on node 7. imagegen-service *appends* it — the template
carries a baseline `blurry, lowres, deformed, text, watermark` and the caller's
negative is joined onto it (`engine.ts:562-569`). Replacing it dropped five terms
and changed 1,010,483 of 1,011,712 pixels. Every settings table in the world would
have looked correct.

## Files

| File | What it is |
|---|---|
| `graph.py` | Builds the ComfyUI prompt graph. A port of `engine.ts`, with node ids and edges matching so a diff is meaningful. |
| `handler.py` | The Runpod serverless handler. Reports `model_load_s` and `render_s` separately so a cold start is never mistaken for a slow render. |
| `app.py` | The Flash `Endpoint` declaration: the GPU pin, the worker range, the idle timeout, and the deliberate absence of a network volume. |
| `Dockerfile` | ComfyUI 0.27.0 at `6cc8144`, IPAdapter_plus at `a0f451a`, torch 2.11.0+cu128, plus the models. |
| `fetch_models.py` | Downloads the five model files at build time and verifies size and SHA256. Fails the build on any mismatch. |
| `workflow-sdxl-txt2img.json` | Copied verbatim from imagegen-service. |
| `MODELS.md` | Sources, sizes, hashes and licences — including the four conditions the style LoRA is used under. |
| `verify_port.py` | The pixel-equality check above. Local and free. |

## The settings, and where each came from

| Setting | Value | Source |
|---|---|---|
| Checkpoint | `sd_xl_base_1.0.safetensors` | workflow node `4` |
| VAE | `sdxl_vae.safetensors` | workflow node `10` |
| Steps | 25 | `engine.ts` `TIER_CONFIG.standard` |
| CFG | 7 | workflow node `3` |
| Sampler / scheduler | `euler` / `normal`, denoise 1 | workflow node `3` |
| Size | 832×1216, batch 1 | `p7_render.py:73` |
| Style LoRA | `ClassipeintXL2.1` @ 0.8 model+clip | `style-loras.ts:21-26` |
| IP-Adapter | weight 0.5, `start_at` 0.3, `ease in-out`, face crop | `engine.ts:74-84, 230-278` |
| Seed | supplied per request, never defaulted | `p7_render.py:358-361` |
| Negative | template baseline **plus** the caller's | `engine.ts:562-569` |

`start_at: 0.3` is not a tuning whim. imagegen-service's ADR-0007 records that
conditioning identity from step 0 lets the reference dictate composition, which
once shipped 84 plates that were near-copies of one reference painting. The early
high-noise steps decide layout; identity lands afterwards.

## Cost shape

The 24GB tier (`GpuGroup.AMPERE_24` — L4 / A5000 / RTX 3090) is **$0.69/hr**, or
$0.000192/s. It was chosen as roughly comparable in raw speed to the home RTX
5070, so a difference in render time would reflect the platform rather than a
bigger GPU. Both tiers were then measured:

| | 24 GB tier | Pinned RTX 4090 |
|---|---:|---:|
| Rate | $0.69/hr | $1.10/hr |
| Warm render median, corrected | **11.937 s** | **4.2175 s** |
| Cost per warm plate | **$0.002656** | **$0.001742** |

The faster card is also the cheaper one per plate, because it is warm for less
time. That is the whole cost argument, and it only holds while the endpoint
scales to zero.

Two settings decide whether this is cheap or ruinous, and both are commented in
`app.py`:

- **`workers=(0, N)`** — scale to zero. A minimum of 1 bills continuously at the
  full hourly rate, about **$497/month** on the 24 GB tier. Measured idle cost
  with the minimum at zero: **$0.00**, four times.
- **No network volume.** A network volume bills whether or not a worker runs,
  about **$7/month** for the 100GB default. The weights live in the image instead.

## What used to block deployment, and how each was cleared

Both are gone. They are kept here because the *way* they failed is the reusable
part.

1. **`flash` could not authenticate.** It needs a `[default]` table with
   `api_key` in `~/.runpod/config.toml`; `runpodctl` writes a top-level `apikey`.
   Given only the second, `runpodctl user` works and every `flash` subcommand
   dies with `RunpodAPIKeyError: No RunPod API key found` — an error that names
   the environment variable and `.env` as remedies and never mentions that the
   file it just read was the wrong shape. **Cleared by one interactive
   `flash login`**, which appends the table and preserves runpodctl's entry.
   Filed as [runpod/flash#363](https://github.com/runpod/flash/issues/363). No
   workaround was attempted, because every remedy the CLI suggests requires
   extracting the plaintext API key.
2. **The image had to be built and pushed to a private registry.** It carries
   ~11GB of weights including a LoRA that may not be redistributed, so it must
   not go to a public registry. **Cleared by pushing to a private GHCR
   repository** and referencing a registry credential by id from `app.py`. The
   `containerRegistryAuthId` field that makes this work is undocumented — it is
   absent from Runpod's custom-image docs and from the Flash skill's
   `PodTemplate` reference, and was found by reading the SDK. Filed as
   [runpod/docs#800](https://github.com/runpod/docs/issues/800). Privacy is
   re-verified after every push.

## Credits

Style LoRA: **ClassipeintXL v2.1 by eldritchadam**, from
[CivitAI model 127139](https://civitai.com/models/127139/classipeintxl-oil-paint-oil-painting-style).
Credit is optional under its licence and given anyway. Its terms permit this use —
private, free, single-user — and **prohibit running it on any service that
monetizes image generation**. See [MODELS.md](MODELS.md) before changing how this
endpoint is exposed.

## Building and pushing (Cycle 4)

Recorded here because Cycle 3 did not write these down, and the deadsnakes rebuild
had to reconstruct them from the Dockerfile's comments.

```bash
# Verify the local model cache first -- free, and it is the difference between a
# 12-minute build and an 11 GB download.
python3 fetch_models.py --check-only --dest /home/kb/comfyui/models

# Build. --build-context replaces the empty `modelcache` stage with the local
# ComfyUI models dir; without it every file is fetched from HuggingFace instead.
docker build \
  --build-context modelcache=/home/kb/comfyui/models \
  -t ghcr.io/kbennett2000/scriptorium-imagegen:sdxl-base-1.0-py31115 \
  flash-imagegen/

# Boot it on the machine that built it, BEFORE it reaches a paid worker. This is
# the step that caught the Cycle 3 segfault in twenty local minutes instead of a
# cold start in a crash loop. Note --runtime=nvidia: `--gpus all` is rejected on
# this box ("invoking the NVIDIA Container Runtime Hook directly ... is not
# supported").
docker run -d --name boot-check --runtime=nvidia \
  -e NVIDIA_VISIBLE_DEVICES=all -e NVIDIA_DRIVER_CAPABILITIES=compute,utility \
  -p 8199:8188 \
  ghcr.io/kbennett2000/scriptorium-imagegen:sdxl-base-1.0-py31115 \
  /bin/sh -c 'python3.11 /opt/ComfyUI/main.py --listen 0.0.0.0 --port 8188 --disable-auto-launch'

# Prove it renders what home renders, on home's own card.
COMFY_URL=http://localhost:8199 ./verify_port.py --book-id pg-41 --plate 0013

docker rm -f boot-check

# Push. Verify no stale push survives FIRST -- by process table and by egress,
# never by a kill's exit code (FINDINGS.md: a pkill reported success and the
# process lived; and dockerd, not the client, streams the layers).
docker login ghcr.io           # PAT with write:packages
docker push ghcr.io/kbennett2000/scriptorium-imagegen:sdxl-base-1.0-py31115

# Confirm PRIVATE after every push. The LoRA licence forbids redistribution.
```
