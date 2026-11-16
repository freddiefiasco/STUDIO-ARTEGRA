# Artegra Enhancer (Beta)

Local image enhancement for Windows by Studio Artegra, with two modes: **Redux** for finals and **Bolt** for quick drafts.

[**Download the Windows installer**](https://github.com/freddiefiasco/STUDIO-ARTEGRA/releases/download/artegra-enhancer-v5.0.0-beta.1/ArtegraEnhancer-5.0.0b1-Setup.exe). Open it, accept the terms and choose Install. Setup downloads and checks the image engine and the Redux and Bolt models automatically; Finish opens the app ready to add an image. No terminal commands or separate setup. The first installation needs internet access, about 40 GB of free space and time to download the required files; the models alone are about 14 GiB. See [installation and requirements](INSTALL.md).

## Features

- **Redux**: Light, Default, Strong, Heavy, Extreme and Custom; 2× and chained larger scales.
- **Bolt**: Light or Default at 2×, for images up to about 9 MP. Quicker, with a slightly different look; use Redux for finals. On two identical RTX 5090 cards a single Bolt image uses both cards; elsewhere each image uses one card.
- Each mode has its own mark beside its name, on every queued image and on every result, so you can see which mode made what.
- Check for updates in Settings and About. It asks GitHub only when you click it; nothing is downloaded or installed.
- A Windows uninstaller in Settings, the Start menu and Installed apps. It never removes your enhanced images; you choose whether to also remove the downloaded enhancement files and your settings.
- Local image processing, guided installation and checked downloads that resume after an interruption.
- Support details redact paths and credentials; nothing uploads automatically.

Redux is the API mode `standard` and Bolt is `fast`; stored jobs and settings keep those ids.

## Verified scope

Tested on Windows with NVIDIA RTX 5090 32 GB hardware. The image pipeline is the final v5 Creative Upscaler's, and the engine and node pack are unchanged from the earlier alphas, whose Redux and Bolt renders matched the v5 reference pixel for pixel. The Beta's own checks are recorded in [docs/VALIDATION.md](docs/VALIDATION.md); results still waiting for a GPU run are marked there.

Windows 10 22H2 and Windows 11 22H2+ on native x64 are compatibility targets. Physical qualification remains RTX 5090 on Windows 11. See [the compatibility matrix](docs/COMPATIBILITY.md) and [installation guidance](INSTALL.md).

Auto selects **Save GPU memory** on cards with 24 GB or less. This processes tiles one at a time and uses CPU model loading while keeping the original tile sizes, weights and numerical options. It can be slower, and pixels may differ slightly. Settings also lets you choose the original settings.

The Beta needs 64 GB of system memory; the planner refuses ordinary images on 32 GB systems even with a large pagefile.

"Speed up upscaling" (Faster) stays off. Review results before delivery: this is a beta.

## From source

```powershell
uv sync --locked
uv run python -m host.app --demo
```

Demo mode uses a simulated engine. Omit `--demo` for real processing after setup. Release maintainers should follow [the Windows build and verification instructions](docs/BUILDING.md).

Project-owned host, service and UI code is source-available under [LICENSE.txt](LICENSE.txt). The node package and runtime patches are GPL-3.0; other components and models keep their own terms.
