# The five model files, and the terms they come with

**No weight file is in this repository, and none may be committed to it or baked
into any publicly pullable image.** They are downloaded at container build time
from the sources below and checked against the SHA256s below.

The hashes are not decoration. They are how "the Runpod app runs the same model
the home machine runs" stops being a claim and becomes a check: every hash here
was computed from the file currently installed under `/home/kb/comfyui/models`,
and the build fails closed if a download does not match.

## The files

| ComfyUI path | File | Bytes | SHA256 |
|---|---|---:|---|
| `checkpoints/` | `sd_xl_base_1.0.safetensors` | 6,938,078,334 | `31e35c80fc4829d14f90153f4c74cd59c90b779f6afe05a74cd6120b893f7e5b` |
| `vae/` | `sdxl_vae.safetensors` | 334,641,164 | `63aeecb90ff7bc1c115395962d3e803571385b61938377bc7089b36e81e92e2e` |
| `loras/` | `ClassipeintXL2.1.safetensors` | 132,865,728 | `74b377ee27855418a95935852f570f0078a9a7a82cfa4ddc81568fc52adc87fd` |
| `ipadapter/` | `ip-adapter-plus-face_sdxl_vit-h.safetensors` | 847,517,512 | `677ad8860204f7d0bfba12d29e6c31ded9beefdf3e4bbd102518357d31a292c1` |
| `clip_vision/` | `CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors` | 2,528,373,448 | `6ca9667da1ca9e0b0f75e46bb030f7e011f44f86cbfb8d5a36590fcd7507b030` |

About 11 GB in total, which is why they cannot ride inside the Flash artifact —
`flash build` caps at 1500 MB.

## Where each one comes from

| File | Source | Licence | Gated? |
|---|---|---|---|
| `sd_xl_base_1.0.safetensors` | `stabilityai/stable-diffusion-xl-base-1.0` → same name | CreativeML Open RAIL++-M | no |
| `sdxl_vae.safetensors` | `stabilityai/sdxl-vae` → same name | MIT | no |
| `ClassipeintXL2.1.safetensors` | `EldritchAdam/SDXL_Eldritch_LoRAs` → same name | RAIL++-M + Addendum — **see below** | no |
| `ip-adapter-plus-face_sdxl_vit-h.safetensors` | `h94/IP-Adapter` → `sdxl_models/ip-adapter-plus-face_sdxl_vit-h.safetensors` | Apache-2.0 | no |
| `CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors` | `h94/IP-Adapter` → **`models/image_encoder/model.safetensors`** | Apache-2.0 | no |

### Two traps in that table

**The CLIP vision file is not from LAION**, despite being named after LAION's
repository. ComfyUI's convention renames `h94/IP-Adapter`'s
`models/image_encoder/model.safetensors` to `CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors`.
The real `laion/CLIP-ViT-H-14-laion2B-s32B-b79K` weights are about 3.94 GB
because they include the text tower, and `sdxl_models/image_encoder/model.safetensors`
in the same h94 repo is 3.69 GB of ViT-bigG belonging to the `_vit-g` adapters.
Only the 2,528,373,448-byte file is the ViT-H encoder that
`ip-adapter-plus-face_sdxl_vit-h` requires. Fetching either of the other two
would fail to load or silently change the conditioning — which is why the byte
count and hash are checked rather than the filename.

**The LoRA must come from the creator's own repository.** imagegen-service's
`install/models.manifest:41` fetches it from `WolfAether21/PONY-DIFFUSION-SDXL-LORA`
with `nerualdreming/Best_LoRas_Mar24` as fallback — two third-party re-uploads,
neither the creator's, both serving the same unattributed copy. A mirror cannot
grant rights the original licence withholds. `EldritchAdam/SDXL_Eldritch_LoRAs`
is the creator's own upload, is ungated, and serves a byte-identical file: the
SHA256 above matches CivitAI's record for version 2.1 exactly.

## The LoRA's licence, and the four conditions this project works under

`ClassipeintXL2.1.safetensors` is [CivitAI model 127139](https://civitai.com/models/127139/classipeintxl-oil-paint-oil-painting-style),
"ClassipeintXL (oil paint / oil painting style)", by **eldritchadam**. Version
2.1 is modelVersionId 356771. It is licensed CreativeML Open RAIL++-M plus a
model-specific [Addendum](https://civitai.com/models/license/356771).

Permission flags, from CivitAI's public API:

| Permission | Granted? |
|---|---|
| Use without crediting the creator | yes (`allowNoCredit: true`) |
| Sell images generated with it | yes (`allowCommercialUse` includes `Image`) |
| Run it on Civitai | yes (`RentCivit`) |
| **Run it on services that generate images for money** | **no — `Rent` is absent** |
| Share merges | no (`allowDerivatives: false`) |
| Sell the model or merges of it | no |

The Addendum's operative sentence is *"Do not use the Model on any service that
monetizes image generation,"* and every example it gives is about charging:
providing the model for a subscription or per-image fee, or on an ad-supported
platform.

**Why this project's use is permitted.** Selling generated images is explicitly
allowed, so showing them in a talk — a strictly lesser act — is allowed too. The
endpoint monetizes nothing: one user, no fee, no subscription, no advertising.
Paying Runpod for GPU time is buying compute, not monetizing generation; the
money flows outward. The withheld `Rent` flag describes deploying the LoRA *on* a
commercial generation platform, which is a different act.

**Stated plainly: that is a reading of the clause, not a documented permission.**
The creator withheld `Rent` while granting `RentCivit`, so they considered hosted
deployment and chose to allow it only on CivitAI. A maximally conservative
reading could stretch "any service" to cover a private Runpod endpoint regardless
of who pays. The text does not support that reading — the prohibition is
qualified by "that monetizes image generation" — but it is not zero-risk, and the
mitigations cost nothing.

### The four conditions

1. **Fetch only from `EldritchAdam/SDXL_Eldritch_LoRAs`.** Never the third-party
   mirrors, never CivitAI. CivitAI's own download URL returns HTTP 401
   unauthenticated for this file, and CivitAI's ToS §11.4 permits scripted access
   only through their API "with your own valid credentials", so fetching there
   would need a token and would pull the build inside CivitAI's terms. The
   creator's HuggingFace repo needs neither.
2. **Never fuse the LoRA into a checkpoint, and never ship a merge.**
   `allowDerivatives` is false and the Addendum forbids sharing merges. ComfyUI's
   `LoraLoader` applies it at runtime as a separate file — which is what home
   already does — so this costs nothing to honour.
3. **The endpoint stays private, free, ad-free and single-user.** No paywall, no
   third-party access. **If this is ever monetized or opened to other users, that
   step is prohibited by the absent `Rent` flag and needs written permission from
   eldritchadam.**
4. **Credit "ClassipeintXL v2.1 by eldritchadam (CivitAI)"** in the talk and here,
   even though `allowNoCredit: true` makes it optional.

## Everything else

SDXL base 1.0 is CreativeML Open RAIL++-M — not the Stability AI Community
Licence, which applies to later Stability releases. It permits commercial use and
hosting, subject to Attachment A's use-based restrictions, none of which are
engaged by illustrating a public-domain short story.

The IP-Adapter and CLIP-vision weights are Apache-2.0 from `h94/IP-Adapter`.

`sdxl_vae` is MIT.

None of the five is gated and none needs a token, so the build needs no
credentials at all.
