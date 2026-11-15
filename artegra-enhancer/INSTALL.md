# Install and run

Use the Windows installer or extract the portable ZIP into a writable folder. Installation is per-user and does not need administrator access. Models and the image-engine runtime are installed separately.

## Before you start

Use native x64 Windows 10 22H2 or Windows 11 22H2 or newer and an NVIDIA RTX graphics card. Use a current NVIDIA Studio driver, preferably branch 595 or newer for the pinned CUDA 13.2 runtime. See [the compatibility matrix](docs/COMPATIBILITY.md) for tested hardware, memory requirements and limitations.

Allow about 14 GiB for Standard and Fast models, plus the separate runtime, downloads, working files and outputs. Use an SSD with sufficient free space. A system-managed Windows pagefile can prevent commit-limit failures; it does not replace graphics memory or guarantee acceptable performance.

## Set up the image engine

Open PowerShell in the installed or extracted application folder and run:

```powershell
.\SetupRuntime.exe --install --directory "$env:LOCALAPPDATA\ArtegraEnhancerRuntime"
```

Choose a **new, empty destination that does not yet exist**. The command downloads pinned Python, engine dependencies and ComfyUI from their publishers and verifies their checksums. It preserves other engine installations. Double-clicking SetupRuntime.exe only displays command-line help.

If setup fails, read its error before trying again. An incomplete folder is not a working runtime. Choose a different new destination for a fresh attempt; the setup will not overwrite an existing directory.

## Set up models and start

1. Open Artegra Enhancer and choose the runtime, models and output folders in Settings. The runtime folder is the destination used above.
2. Open **Set up or verify models**. Review each publisher's terms and accept those for the models you want, then choose **Download selected**. Standard needs five files; Fast adds its LoRA. Downloads can pause and resume. Existing files are verified and never replaced. **Verify existing files** uses no network.
3. Choose **Start engine**, add an image, choose Standard or Fast and upscale. Fast supports Light or Default at 2× within its size limit.
4. This build retains the verified image settings. Smaller-memory profiles are withheld after a candidate failed visual quality review. 64 GB system RAM is recommended; other GPU tiers remain unqualified.

Individual model terms are described in [MODEL-LICENSES.md](MODEL-LICENSES.md), including the TTPlanet publisher's unspecified OpenRAIL version. No model weights are included in the download.

## Display or startup problems

For a blank window or graphics-driver display problem, try:

```powershell
.\ArtegraEnhancer.exe --software-rendering
```

This draws the interface using the CPU; image processing still uses the NVIDIA GPU. The window fits the screen's available logical size and settings scroll on smaller displays.

For insufficient memory, close other GPU/RAM-heavy applications, choose a smaller source image or upscale factor, and check the supported hardware limits. Check Windows' available RAM, commit limit and free SSD space. The app does not change pagefile, driver or system settings automatically.

Use **Open logs** or **Save diagnostic bundle** in Settings to investigate problems. Review the ZIP before sharing; nothing uploads automatically.

## Files and removal

Settings and job state are beneath the current user's local application-data folder, under `Studio Artegra/Artegra Enhancer`. Output images go to the chosen output folder. Closing the app stops its owned image-engine processes.

The installer removes installed application files; model, runtime and output folders are preserved. To remove a portable copy, close it and remove its extracted folder. Keep or remove application state separately.

This alpha is unsigned. Verify its published SHA-256 checksum and review output before delivery.
