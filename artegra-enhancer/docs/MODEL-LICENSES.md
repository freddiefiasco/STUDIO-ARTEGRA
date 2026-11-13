# Model sources and terms

Weights are not distributed with the app. The automatic downloader is disabled while the outstanding model-licence review is completed. Existing files remain in place.

Six required Standard/Fast model files from the selected preview were hashed read-only and match the pinned publisher SHA-256 values. The optional detailed-preview decoder is an FP16 variant and does not match the publisher FP32 file; its exact hash is separately recorded in the manifest.

| File | Publisher | Licence stated by publisher | Local match |
|---|---|---|---|
| `juggernautXL_ragnarok.safetensors` | [Kandoo/Juggernaut-XL-Ragnarok](https://huggingface.co/Kandoo/Juggernaut-XL-Ragnarok/blob/aa701fd414bf7810d7403342d645c404cd307459/README.md) | CreativeML OpenRAIL-M | Yes |
| `4xRealWebPhoto_v4_dat2.safetensors` | [Phips/4xRealWebPhoto_v4_dat2](https://huggingface.co/Phips/4xRealWebPhoto_v4_dat2/blob/95e9cd50553951c27d86bafbdc1bc27ca8e750d2/README.md) | CC-BY-4.0 | Yes |
| `TTPLANET_Controlnet_Tile_realistic_v2_fp16.safetensors` | [TTPlanet/TTPLanet_SDXL_Controlnet_Tile_Realistic](https://huggingface.co/TTPlanet/TTPLanet_SDXL_Controlnet_Tile_Realistic/blob/37f1c4575b543fb2036e39f5763d082fdd135318/README.md) | openrail (publisher metadata; exact text unresolved) | Yes |
| `mistoLine_fp16.safetensors` | [TheMistoAI/MistoLine](https://huggingface.co/TheMistoAI/MistoLine/blob/1d9d0b3d48b295cf70d80a0f839a3055672f8393/README.md) | CreativeML Open RAIL++-M | Yes |
| `sam3.1_multiplex_fp16.safetensors` | [Comfy-Org/sam3.1](https://huggingface.co/Comfy-Org/sam3.1/blob/7bb8374780a725b4353ed31f3a9395c9742b5621/README.md) | SAM License (2025-11-19) | Yes |
| `taesdxl_decoder.safetensors` | [madebyollin/taesdxl](https://huggingface.co/madebyollin/taesdxl/blob/b20258aaef75ef61e659c1e0f14f251cf0ad153e/README.md) | MIT | Different optional variant |
| `Hyper-SDXL-8steps-CFG-lora.safetensors` | [ByteDance/Hyper-SD](https://huggingface.co/ByteDance/Hyper-SD/blob/bc08d970a87c74c71209491d64e3525845698863/README.md) | CreativeML Open RAIL++-M (other SD-related models section) | Yes |

## Outstanding review

- The tile ControlNet card says `openrail` without identifying a full licence/version. Its exact terms must be established before automatic acquisition is enabled. No rights are inferred from a generic tag.
- SAM uses custom terms. Read and accept the upstream agreement and any access conditions before acquiring it. An ungated conversion is not permission to ignore upstream terms.
- The Hyper-SDXL eight-step file uses the publisher licence section for SD-related models. Do not apply a different model family’s licence to it.
- The optional decoder has a different precision from the publisher file. Do not silently replace it when comparing live preview behaviour.

## Integrity

Each entry in `../models.manifest.json` records a pinned publisher revision, URL, size, hash, licence URL and acquisition status. Verify existing files with `uv run python tools/verify_models.py <models-folder>`. Verification never copies, moves or changes model files. It will report the alternate optional decoder as different.

The model publishers remain responsible for their terms. The app’s code licence does not grant rights to model weights.
