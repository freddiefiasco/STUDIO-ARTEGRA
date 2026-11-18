# Artegra Enhancer (Beta) 5.0.0 Beta 1

Artegra Enhancer leaves alpha. This first beta brings the final v5 Creative Upscaler's enhancement tab to the standalone app, renames the modes and adds an update check and a proper Windows uninstaller.

**Redux and Bolt.** Standard is now Redux, for finals; Fast is now Bolt, for quick drafts. Each has a small mark: Redux's stacked courses and Bolt's strike, beside the names and on every queued image and result. A Bolt result is saved as `name_cu2x_bolt.png`; older `_fast` results are still recognised.

**The final v5 tab.** The tab, service and finish times now match the final v5 after its four rounds of QA fixes. Bolt is offered only once its files are checked. On two identical RTX 5090 cards a single Bolt image uses both cards; everywhere else each Bolt image uses one card, and the finish time says so. The engine and node pack are unchanged.

**Check for updates.** In Settings and About. It asks GitHub only when you click it and never downloads or installs anything.

**Uninstall.** From Installed apps, the Start menu or Settings. It closes only the app's own processes, never removes your images, and offers to also remove the downloaded enhancement files and the settings and logs, both off by default.

**Upgrading.** Install over alpha 4: your models, settings, outputs and memory choice are kept. Setup shows the terms page again and checks the models you have; it does not download them again.

Targets native x64 Windows 10 22H2 or Windows 11 22H2+, with an NVIDIA RTX card and 64 GB of system memory. Physical verification remains Windows 11 and RTX 5090. See the installation guide, the compatibility matrix, the known issues and the validation report. This is an unsigned beta; compare the download with the published checksums and review results before delivery.

[Download the installer](https://github.com/freddiefiasco/STUDIO-ARTEGRA/releases/download/artegra-enhancer-v5.0.0-beta.1/ArtegraEnhancer-5.0.0b1-Setup.exe)
