# Artegra Enhancer: Creative Upscaler

Standalone Windows alpha of the v5 Creative Upscaler, with Standard and Fast modes.

Download the **Windows installer** or **portable ZIP** from this repository's Releases. No model weights are bundled. See [INSTALL.md](INSTALL.md) for runtime and model setup.

## Features

- Standard: Light, Default, Strong, Heavy and Extreme; 2× and chained larger scales.
- Fast: Light or Default at 2×, within the 9,375,000 padded-pixel limit. Each image uses one GPU; separate images can use separate GPUs.
- Local processing, resumable model downloads with individual publisher-term acceptance, verified files, separate settings, and owned-process cleanup.
- Diagnostic export redacts paths and credentials; nothing uploads automatically.

## Verified scope

Tested on Windows with NVIDIA RTX 5090 32 GB hardware. Selected Standard and Fast cold/warm renders match the v5 reference pixel for pixel. The independently installed pinned runtime also matches the original runtime. These representative checks do not cover every possible input or GPU.

331 automated tests and 33 subtests passed remotely, with additional targeted checks for the pruned node catalogue. Results and limits are in [docs/VALIDATION.md](docs/VALIDATION.md).

Other GPU tiers are unqualified. Fast single-image GPU splitting and Faster remain disabled, as in the selected preview. Review outputs before delivery; this is an alpha.

## From source

```powershell
uv sync --locked
uv run python -m host.app --demo
```

Demo mode uses a simulated engine. Omit `--demo` for real processing after setup. Build with `uv run python tools/build_release.py --installer` when Inno Setup is available.

Project-owned host, service and UI code is source-available under [LICENSE.txt](LICENSE.txt). The node package and runtime patches are GPL-3.0; other components and models retain their own terms.
