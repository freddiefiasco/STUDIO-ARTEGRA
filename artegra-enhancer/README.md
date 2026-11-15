# Artegra Enhancer: Creative Upscaler

Standalone Windows alpha of the v5 Creative Upscaler, with Standard and Fast modes.

[**Download the Windows installer**](https://github.com/freddiefiasco/STUDIO-ARTEGRA/releases/download/artegra-enhancer-v0.1.0-alpha.4/ArtegraEnhancer-0.1.0a4-Setup.exe). Open it, accept the terms and choose Install. Setup downloads and verifies the image engine and Standard/Fast models automatically; Finish opens the app ready to add an image. No terminal commands or separate runtime setup. The first installation needs internet access, about 40 GB of free space and time to download the required files; the models alone are about 14 GiB. See [installation and requirements](INSTALL.md).

## Features

- Standard: Light, Default, Strong, Heavy and Extreme; 2× and chained larger scales.
- Fast: Light or Default at 2×, within the 9,375,000 padded-pixel limit. Each image uses one GPU; separate images can use separate GPUs.
- Local image processing, guided installation and verified downloads that can resume after interruption.
- App updates and removal preserve your images, settings and downloaded enhancement files.
- Diagnostic export redacts paths and credentials; nothing uploads automatically.

## Verified scope

Tested on Windows with NVIDIA RTX 5090 32 GB hardware. Selected Standard and Fast cold/warm renders match the v5 reference pixel for pixel. The independently installed pinned runtime also matches the original runtime. These representative checks do not cover every possible input or GPU.

Automated regression checks, installation checks and actual image results are recorded in [docs/VALIDATION.md](docs/VALIDATION.md). The earlier baseline also passed the extended CPU recovery/fault suite.

Windows 10 22H2 and Windows 11 22H2+ on native x64 are compatibility targets. Physical qualification remains limited to RTX 5090 on Windows 11. See [the compatibility matrix](docs/COMPATIBILITY.md) and [installation guidance](INSTALL.md).

Auto selects **Save GPU memory** on cards with 24 GB or less. This processes tiles one at a time and uses CPU model loading while preserving original tile sizes, weights and numerical options. It can be slower, and pixels may differ slightly. Settings also lets you choose the original recipe explicitly. The earlier smaller-tile experiments remain excluded after a visual quality failure.

This alpha requires 64 GB system RAM; the conservative planner currently refuses ordinary renders on 32 GB physical-RAM systems even with a large pagefile. Allocator-budget checks on RTX 5090 support the memory-saving approach, but do not certify another physical GPU.

Fast single-image GPU splitting and Faster remain disabled. Review outputs before delivery; this is an alpha.

## From source

```powershell
uv sync --locked
uv run python -m host.app --demo
```

Demo mode uses a simulated engine. Omit `--demo` for real processing after setup. Release maintainers should follow [the Windows build and verification instructions](docs/BUILDING.md).

Project-owned host, service and UI code is source-available under [LICENSE.txt](LICENSE.txt). The node package and runtime patches are GPL-3.0; other components and models retain their own terms.
