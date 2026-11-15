# Install Artegra Enhancer

1. [Download **ArtegraEnhancer-0.1.0a4-Setup.exe**](https://github.com/freddiefiasco/STUDIO-ARTEGRA/releases/download/artegra-enhancer-v0.1.0-alpha.4/ArtegraEnhancer-0.1.0a4-Setup.exe).
2. Open it, review the application and model terms, and choose **Install**. Keep the suggested location unless you want the large enhancement files on another drive.
3. Leave setup open while it downloads and checks the required files. Choose **Finish** to open Artegra Enhancer, add an image and enhance it.

Setup installs everything needed for Standard and Fast. You do not need Python, ComfyUI, a CUDA Toolkit, a terminal or a separate setup program. The app chooses its folders and connects to its image engine automatically.

## Before installing

- Native x64 Windows 10 22H2 or Windows 11 22H2 or newer.
- An NVIDIA RTX graphics card with at least 8 GB of graphics memory and a compatible NVIDIA Studio driver. A current Studio driver is recommended.
- **64 GB system memory for this alpha.** Ordinary enhancement on 32 GB systems remains unsupported.
- Approximately **40 GB free SSD space** for setup, plus space for your images. The enhancement models account for about 14 GiB. Download time depends on your connection.
- Internet access during the initial installation. Your images are processed locally; setup downloads software and models, not your pictures.

The installer checks compatibility and free space before the large downloads. Physical testing currently covers Windows 11 and RTX 5090. Other listed Windows releases and RTX cards are compatibility targets; see [compatibility details](docs/COMPATIBILITY.md).

## Interrupted installation

Keep the files already downloaded. Choose **Retry**, reopen the installer or open Artegra Enhancer to continue setup. Verified files are reused and supported downloads resume. A failed or paused installation never reports that the app is ready.

If a driver or disk-space issue needs attention, setup explains it in the same window. It does not change your Windows drivers or pagefile automatically.

## Updates and repair

Install a newer version over the existing version. Your image outputs, saved locations and enhancement files are preserved. The app's **Settings → Repair installation** checks required files and prepares missing components through the same guided process.

The portable ZIP is an alternative for experienced users: extract it and open **ArtegraEnhancer.exe**. Its first-launch setup handles the same downloads and checks.

## Where your files live

The app installs for your Windows account without administrator access. Enhancement files use the suggested application-data location or the drive you selected. Images save to **Pictures → Artegra Enhancer** by default; change the output location in Settings.

Uninstall through Windows Settings to remove the app and shortcuts. Your enhanced images and downloaded enhancement files are retained, so reinstalling does not discard them.

## Help

Use **Settings → Save support details** if you need to report a problem, then attach the saved file to a [support issue](https://github.com/freddiefiasco/STUDIO-ARTEGRA/issues). Review it before sharing; nothing is uploaded automatically.

This alpha is unsigned, so Windows may display a publisher or reputation warning. Code signing is not included in this release. Download only from the linked Studio Artegra repository.
