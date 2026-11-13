# Model sources, licences and setup

Artegra Enhancer does not distribute model weights. Settings downloads selected files directly from their named publishers only after you explicitly accept each model's linked card and terms. The application is not granting a model licence or certifying legal suitability. The licences listed here have different conditions; they are not collectively described as OSI open source.

## Set up your models

1. Choose a writable Models folder in Settings. You may choose a folder containing existing models.
2. Open **Set up or verify models**. Standard's five files and the Fast LoRA are selected initially. The detailed-preview decoder is optional.
3. Review each **Publisher**, **Terms**, and **Saved terms** link. The saved text contains the full retrieved licence and model card for offline reference; TTPlanet's saved text accurately records its incomplete declaration.
4. Accept each selected model individually and choose **Download selected**. No transfer starts just by accepting. **Verify existing files** needs no download acceptance and makes no network requests.
5. Wait until the selected models are verified, then start the image engine.

A transfer can be paused and resumed. Completed files must match their pinned byte size and SHA-256 before appearing at their final path. Existing files with different contents are kept unchanged; move them aside yourself or choose another folder. A server that ignores resume requests is handled by restarting that transfer safely. Lost connections or insufficient space leave resumable partial data. The application does not collect model-host access tokens; if a publisher requires account approval, use its official page. Do not bypass its access conditions.

## Sources and exact terms

| Model | Publisher | Applicable licence / condition |
|---|---|---|
| Juggernaut XL Ragnarok | [Kandoo](https://huggingface.co/Kandoo/Juggernaut-XL-Ragnarok/blob/aa701fd414bf7810d7403342d645c404cd307459/README.md) | CreativeML OpenRAIL-M; creator explicitly permits commercial use subject to the licence |
| RealWebPhoto DAT2 4x | [Phips / Philip Hofmann](https://huggingface.co/Phips/4xRealWebPhoto_v4_dat2/blob/95e9cd50553951c27d86bafbdc1bc27ca8e750d2/README.md) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/legalcode.en) |
| TTPlanet Tile v2 FP16 | [TTPlanet](https://huggingface.co/TTPlanet/TTPLanet_SDXL_Controlnet_Tile_Realistic/blob/37f1c4575b543fb2036e39f5763d082fdd135318/README.md) | OpenRAIL **family** declared; exact version and full licence not supplied; publisher asks for no adult content |
| MistoLine FP16 | [TheMistoAI](https://huggingface.co/TheMistoAI/MistoLine/blob/1d9d0b3d48b295cf70d80a0f839a3055672f8393/LICENSE.md) | CreativeML Open RAIL++-M |
| SAM 3.1 multiplex FP16 | [Comfy-Org repack](https://huggingface.co/Comfy-Org/sam3.1/blob/7bb8374780a725b4353ed31f3a9395c9742b5621/LICENSE), derived from [Meta SAM 3.1](https://huggingface.co/facebook/sam3.1) | Custom SAM License, dated 19 November 2025 |
| Hyper-SDXL eight-step CFG LoRA | [ByteDance](https://huggingface.co/ByteDance/Hyper-SD/blob/bc08d970a87c74c71209491d64e3525845698863/LICENSE.md) | CreativeML Open RAIL++-M, **other SD-related models** section |
| TAESDXL decoder (optional) | [madebyollin](https://huggingface.co/madebyollin/taesdxl/blob/b20258aaef75ef61e659c1e0f14f251cf0ad153e/README.md) | MIT |

### What these terms mean for your use

**Juggernaut:** The exact Ragnarok creator card permits commercial model/output use under OpenRAIL-M and passes use restrictions through to downstream sharing. This does not automatically import paid-API restrictions from different Juggernaut versions. Its [saved terms](../licenses/models/juggernaut-xl-ragnarok.txt) include the licence linked by the creator and the pinned card.

**RealWebPhoto:** CC BY 4.0 permits commercial copying and adaptation subject to attribution, source/licence information, modification notices and no extra restrictions on the licensed material. Credit Philip Hofmann when sharing the model. This does not assert that output images are automatically licensed under CC BY. [Saved terms](../licenses/models/realwebphoto-v4-dat2.txt).

**TTPlanet:** The card says `license: openrail`. Hugging Face's [official licence identifier documentation](https://huggingface.co/docs/hub/en/repositories-licenses) defines that identifier as the OpenRAIL licence **family**, not one particular text. No licence file or more specific grant was found in the pinned publisher repository. Respect its no-adult-content request. The setup flow explicitly presents this uncertainty for acceptance of the publisher's terms and direct personal acquisition. It does not establish commercial rights, invent a redistribution grant, or bundle the weights. No blanket ban on publishing a weight-free host was found. Seek the publisher's clarification for uses requiring certainty. [Saved publisher declaration](../licenses/models/ttplanet-tile-v2.txt).

**MistoLine and Hyper-SDXL:** Open RAIL++-M permits use and distribution under its stated conditions. Redistribution requires the licence and retained notices, modified-file notices and enforceable downstream use restrictions. Read Attachment A. ByteDance's multi-family licence file also contains FLUX noncommercial and SD3 community sections; those are not the section assigned to this SDXL LoRA. [MistoLine terms](../licenses/models/mistoline-fp16.txt), [Hyper-SDXL terms](../licenses/models/hyper-sdxl-8steps-cfg.txt).

**SAM:** This is a custom agreement, not MIT or Apache. It grants use/modification/distribution subject to conditions including law, privacy, trade controls and certain restricted end uses. Redistributed material must carry the agreement. The original Meta repository has manual account approval; Comfy-Org's documented conversion is ungated and carries the SAM licence. An ungated file does not remove licence obligations. No credentials or access approvals are copied into the application. [Saved agreement and card](../licenses/models/sam3.1-multiplex-fp16.txt).

**TAESDXL:** MIT permits commercial use and redistribution with retained copyright/permission notice. The publisher download is FP32. The verified existing FP16 conversion has a different hash and is recognised without replacing it; there is no publisher download claim for that conversion. These affect live-preview pixels, not final outputs. [Saved terms](../licenses/models/taesdxl-decoder.txt).

The underlying SDXL base terms are also retained in [licenses/models/sdxl-base-license.txt](../licenses/models/sdxl-base-license.txt). Reading this summary does not replace the full applicable agreements.

## Integrity and storage

The five Standard files total 13,994,967,806 bytes (13.03 GiB). The Fast LoRA adds 787,359,648 bytes (0.73 GiB). The optional publisher decoder adds 4,895,612 bytes. Runtime storage and output space are additional.

[models.manifest.json](../models.manifest.json) records the pinned publisher revision, original download URL, expected size/hash, accepted existing optional variant and saved licence path. Six required Standard/Fast preview files were independently hashed and matched these publisher identities. This verification does not imply a licence grant. User installations are checked separately; verification reads existing files without changing them.

Acceptance is recorded locally against the particular model, revision, hash and displayed terms. Updated terms require fresh acceptance. The application code licence does not grant rights to any model weights.

## Network, acceptance and recovery details

Model setup makes network requests only after **Download selected**. Initial downloads use the pinned HTTPS Hugging Face URL in the manifest. Redirects are limited to HTTPS hosts `huggingface.co`, `*.huggingface.co`, `hf.co` and `*.hf.co` (including official CDN/Xet file-delivery hosts). Other redirect locations are refused. Your configured network proxy may be used; its credentials and signed download URLs are not written to setup progress or logs. Clicking a publisher or terms link opens that URL in your browser. **Saved terms** reads the included, hash-checked text without a network request.

Each acceptance record is local and specific to the model identity, revision, weight hash, displayed notice, card/terms URLs and saved-terms hash. Checking a box is not a download. A changed identity or terms snapshot needs new acceptance. Existing model verification performs no network request and requires no new download agreement.

Transfers use content-addressed partial files in the selected model folder. Pause or connection failure retains completed bytes; click **Download selected** again to resume. There is no automatic retry loop. A ten-second idle timeout handles silent connections. Pause also actively shuts down the active network socket, so a peer continuously sending tiny amounts of data cannot defer cancellation by keeping that timeout alive. Resume requires a valid byte-range response and matching declared total size; a full response restarts safely. All completed bytes are SHA-256 verified before an atomic, no-overwrite final installation. A hash mismatch removes only the failed partial download. Existing different models remain untouched. Separate setup processes share an operating-system folder lock. On filesystems without Windows hard-link support, a no-replace atomic rename is used.

Disk-full, permission, missing-drive and network failures are recoverable: restore access or free space and request the download again. Closing the app requests cancellation and waits for the transfer worker to release its file and folder lock; a saved partial can be resumed on the next run. Verification and transfers must finish or pause before changing model folders or starting the image engine.
