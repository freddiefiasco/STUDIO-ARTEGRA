# Artegra Enhancer: Creative Upscaler

A standalone Windows desktop preview for upscaling architectural renders. This source release is based on the v5 early preview and includes Standard and Fast modes.

**Status: developer preview, 0.1.0-alpha.1.** The standalone host and generated image prompts are tested. A clean-machine installation and rendered-pixel comparison of this standalone package are still required before a supported pilot release. See [validation](docs/VALIDATION.md).

## Try the interface

On Windows 11, install [uv](https://docs.astral.sh/uv/getting-started/installation/), then open a terminal in this repository:

```powershell
uv sync --locked
uv run python -m host.app --demo
```

Demo mode uses a simulated engine. Its pictures are not AI-upscaled results.

For the real engine, run without `--demo`, choose an installed runtime, a models folder and a writable output folder in Settings. Open **Set up or verify models** to acquire files directly from publishers after accepting their terms, or verify your existing files. See [INSTALL.md](INSTALL.md). Images are processed locally; the app does not upload them.

## Standard and Fast

| Mode | Looks | Scale | Operation |
|---|---|---|---|
| Standard | Light, Default, Strong, Heavy, Extreme | 2× and chained larger scales | Full preview workflow |
| Fast | Light, Default | 2× | Eight-step workflow; verified Fast LoRA required |

Fast accepts up to 9,375,000 padded input pixels. It processes each image on one graphics card; separate images can use separate cards. A single Fast image is not split across cards. The separate Faster option is disabled.

## Hardware

An NVIDIA GPU and a compatible CUDA driver are required for real processing. RTX 5090 32 GB is the reference hardware. Other cards, including 24 GB cards, are unqualified in this standalone preview. Model loading can require substantial RAM and approximately 15 GB of model storage, in addition to the runtime. The inherited planner enforces its size and memory limits; passing those checks is not a hardware certification.

## Models and licences

Model weights are never included in this repository or its build artifacts. [MODEL-LICENSES.md](MODEL-LICENSES.md) records publisher sources, terms and unresolved questions. Settings supports direct publisher downloads with individual licence acceptance, pause/resume and integrity checks. TTPlanet declares only the OpenRAIL family without a full text; the setup flow discloses this uncertainty and its no-adult-content request. Use only models whose terms you accept and whose permitted uses cover your work. The exact expected filenames, sizes and publisher hashes are in [models.manifest.json](models.manifest.json).

## Build and contribute

```powershell
uv run python -m pytest
uv run python tools/public_scan.py
uv run python tools/build_release.py
```

The build produces a portable application and, when Inno Setup is available, a per-user installer. [Release checklist](docs/RELEASE-CHECKLIST.md) lists the outstanding qualification steps. Project-owned host, service and UI code is source-available under [LICENSE.txt](LICENSE.txt). The ComfyUI node package and runtime patches are GPL-3.0. Third-party components keep their own licences.

