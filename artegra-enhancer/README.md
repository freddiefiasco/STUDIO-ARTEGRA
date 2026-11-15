# Artegra Enhancer: Creative Upscaler

Standalone Windows alpha of the v5 Creative Upscaler, with Standard and Fast modes.

Download the **Windows installer** or **portable ZIP** from this repository's Releases. No model weights are bundled. See [INSTALL.md](INSTALL.md) for runtime and model setup.

## Features

- Standard: Light, Default, Strong, Heavy and Extreme; 2Ã— and chained larger scales.
- Fast: Light or Default at 2Ã—, within the 9,375,000 padded-pixel limit. Each image uses one GPU; separate images can use separate GPUs.
- Local processing, resumable model downloads with individual publisher-term acceptance, verified files, separate settings, and owned-process cleanup.
- Diagnostic export redacts paths and credentials; nothing uploads automatically.

## Verified scope

Tested on Windows with NVIDIA RTX 5090 32 GB hardware. Selected Standard and Fast cold/warm renders match the v5 reference pixel for pixel. The independently installed pinned runtime also matches the original runtime. These representative checks do not cover every possible input or GPU.

331 automated tests and 33 subtests passed remotely, with additional targeted checks for the pruned node catalogue. Results and limits are in [docs/VALIDATION.md](docs/VALIDATION.md).

Windows 10 22H2 and Windows 11 22H2+ on native x64 are the platform targets. Driver checks and automatic VRAM profiles cover the requested RTX 3080/3090, 4080/4090 and 5080/5090 tiers. Actual physical-card qualification remains limited to RTX 5090. See [the compatibility matrix](docs/COMPATIBILITY.md) for the distinction and [installation guidance](INSTALL.md) for setup.

Auto retains the reference configuration on 32 GB cards and selects progressively smaller tiles with CPU offloading on smaller cards. Manual Balanced, Compact and Minimum profiles can reduce memory use further. Smaller tiles can change output. 64 GB system RAM is recommended; the conservative planner currently refuses ordinary renders on 32 GB systems. A pagefile helps commit capacity but does not bypass that limit.

Fast single-image GPU splitting and Faster remain disabled. Review outputs before delivery; this is an alpha.

## From source

```powershell
uv sync --locked
uv run python -m host.app --demo
```

Demo mode uses a simulated engine. Omit `--demo` for real processing after setup. Build with `uv run python tools/build_release.py --installer` when Inno Setup is available.

Project-owned host, service and UI code is source-available under [LICENSE.txt](LICENSE.txt). The node package and runtime patches are GPL-3.0; other components and models retain their own terms.
