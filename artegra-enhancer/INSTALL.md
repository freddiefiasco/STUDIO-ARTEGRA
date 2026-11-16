# Install Artegra Enhancer (Beta)

1. [Download **ArtegraEnhancer-5.0.0b1-Setup.exe**](https://github.com/freddiefiasco/STUDIO-ARTEGRA/releases/download/artegra-enhancer-v5.0.0-beta.1/ArtegraEnhancer-5.0.0b1-Setup.exe).
2. Open it, review the app and model terms, and choose **Install**. Keep the suggested location unless you want the large enhancement files on another drive.
3. Leave setup open while it downloads and checks the required files. Choose **Finish** to open Artegra Enhancer, add an image and enhance it.

Setup installs everything needed for Redux and Bolt. You do not need Python, ComfyUI, a CUDA Toolkit, a terminal or a separate setup program. The app chooses its folders and connects to its image engine automatically.

## Before installing

- Native x64 Windows 10 22H2 or Windows 11 22H2 or newer.
- An NVIDIA RTX graphics card with at least 8 GB of graphics memory and a compatible NVIDIA Studio driver. A current Studio driver is recommended.
- **64 GB of system memory.** Ordinary enhancement on 32 GB systems is not supported.
- About **40 GB of free SSD space** for setup, plus space for your images. The enhancement models take about 14 GiB. Download time depends on your connection.
- Internet access during the first installation. Your images are processed locally; setup downloads software and models, not your pictures.

The installer checks compatibility and free space before the large downloads. Physical testing covers Windows 11 and RTX 5090. Other listed Windows releases and RTX cards are compatibility targets; see [compatibility details](docs/COMPATIBILITY.md).

## Interrupted installation

Keep the files already downloaded. Choose **Retry**, reopen the installer or open Artegra Enhancer to continue setup. Checked files are reused and downloads resume. A failed or paused installation never reports that the app is ready.

If a driver or disk-space issue needs attention, setup explains it in the same window. It does not change your Windows drivers or pagefile.

## Updates and repair

**Settings → Check for updates** (also in **About**) asks GitHub whether a newer release exists and offers **Download**, which opens the release page in your browser. Nothing is downloaded or installed automatically.

Install a newer version over the existing one. Installing the Beta over an alpha upgrades it in place: your images, saved locations, settings and enhancement files are kept, and you are not asked to accept the terms or download the models again. Going back from the Beta to an alpha is not supported.

**Settings → Repair installation** checks the required files and prepares anything missing through the same guided process.

The portable ZIP is an alternative for experienced users: extract it and open **ArtegraEnhancer.exe**. Its first-launch setup handles the same downloads and checks. It has no uninstaller; delete its folder to remove it.

## Where your files live

The app installs for your Windows account without administrator access. Enhancement files use the suggested app-data location or the drive you selected. Images save to **Pictures → Artegra Enhancer** by default; change the output location in Settings.

## Uninstall

Use any of these:

- **Settings → Uninstall Artegra Enhancer…** in the app (shown in an installed copy).
- **Start → Artegra Enhancer (Beta) → Uninstall Artegra Enhancer (Beta)**.
- **Windows Settings → Apps → Installed apps → Artegra Enhancer (Beta) → Uninstall**.

Windows asks you to confirm, then shows two choices, both off by default:

- **Also remove downloaded enhancement files** (about 14 GiB of models, plus the image engine setup installed). Only files the app downloaded into its own folder are removed. A models folder you chose yourself is never touched.
- **Also remove settings and logs.**

The uninstaller first closes Artegra Enhancer and its image engine (only the app's own processes), then removes the app and its shortcuts. **Your enhanced images are never removed.**

For administrators: `unins000.exe /VERYSILENT` (or `/SILENT`) removes the app and keeps everything optional. Add `/REMOVEFILES=1` and/or `/REMOVESETTINGS=1` to remove those too.

## Help

Use **Settings → Save support details** if you need to report a problem, then attach the saved file to a [support issue](https://github.com/freddiefiasco/STUDIO-ARTEGRA/issues). Review it before sharing; nothing is uploaded automatically.

This beta is unsigned, so Windows may show a publisher or reputation warning. Code signing is not included in this release. Download only from the linked Studio Artegra repository, and compare the file with `SHA256SUMS.txt` if you want to check it.
