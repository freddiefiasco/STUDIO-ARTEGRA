# Artegra Enhancer 0.1.0-alpha.2

Windows compatibility and memory refinement of the standalone v5 Creative Upscaler, with Standard and Fast modes.

Automatic VRAM profiles preserve the reference configuration on 32 GB cards and choose smaller tiles, sequential work and CPU offloading for lower-memory cards. Settings exposes Auto, Balanced, Compact and Minimum, including the effective tile size and offload mode. Smaller profiles can change output and take longer.

The app now checks Windows/native x64 and NVIDIA driver compatibility, checks RAM and commit headroom before the first image, and uses conservative memory budgets. Settings fits smaller/scaled screens; a software-rendered interface option helps with display-driver problems. Installation instructions are included in the app.

Targets: native x64 Windows 10 22H2 or Windows 11 22H2+, NVIDIA RTX 3080/3090, 4080/4090 and 5080/5090 tiers. Only RTX 5090 and Windows 11 have been physically tested. Other cards and Windows 10 remain compatibility targets, not certified configurations. 64 GB system RAM is recommended; ordinary renders on 32 GB physical-RAM systems remain blocked by the conservative planner.

Model files and the reference numerical recipe are retained. No quantized replacements or model weights are bundled. Models download from publishers after acceptance of their individual terms. Driver, Windows and pagefile settings remain user-controlled.

See the included compatibility and validation reports for measurements and limits. This is an unsigned alpha; verify the release checksums and review output before delivery.
