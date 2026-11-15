# Artegra Enhancer 0.1.0-alpha.2

Windows compatibility, memory safety and interface refinement of the standalone v5 Creative Upscaler, with Standard and Fast modes.

Adds Windows version/native x64 and NVIDIA driver checks, RAM and commit admission before the first image, conservative application memory budgets, and NVIDIA tool discovery when PATH is incomplete. Settings fits smaller/scaled screens; software interface rendering helps with display-driver problems. Installation instructions are available from Settings.

Standard and Fast passed actual packaged-service execution and visual checks. An experimental smaller-memory profile completed but produced visible artifacts, so it is excluded from this release. Original tile sizes, model files and numerical settings remain in use. No quantized replacements or model weights are bundled.

Targets native x64 Windows 10 22H2 or Windows 11 22H2+. Physical validation is Windows 11 and RTX 5090. RTX 3080/3090, 4080/4090, 5080 and Windows 10 remain compatibility targets requiring actual hardware and image-quality qualification. This update does not certify every listed card. 64 GB system RAM is recommended; the conservative planner refuses ordinary renders on 32 GB physical-RAM systems.

Models download from publishers after acceptance of their terms. Driver, Windows and pagefile settings remain user-controlled. See the compatibility and validation reports for measurements and limits. This is an unsigned alpha; verify checksums and review output before delivery.
