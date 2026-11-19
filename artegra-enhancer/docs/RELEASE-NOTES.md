# Artegra Enhancer (Beta) 5.0.1 Beta 1

This update stops the Beta refusing images a 64 GB PC can render.

**What runs now.** On a 64 GB PC with one RTX 5090, Redux and Bolt make 2× of 3500 × 2188 renders at full quality, and Redux makes 4× of a 1280 × 1600 image. 5.0.0 Beta 1 refused both for memory. Every image 5.0.0 Beta 1 could make is planned and made exactly as before.

**Why it refused them.** Its memory estimate was 17 to 34 % above what the engine really uses, and it let the engine use only the computer's memory less 10 %. The estimate now comes from peaks measured on RTX 5090 PCs, plus a 3 % margin, and the app may use the memory less 2.5 GB or 4 %: 59 GB on a 64 GB PC.

**When memory is short.** The app first tries a lighter setting at the size you chose, and the image's caption says so. Only when even that does not fit is the image refused, with the amount it needs. Bolt says when memory, not size, is the reason.

**What still needs 128 GB.** Redux 4× of a 3500 × 2188 render and 6× or 8× of a 1280 × 1600 image need about 65 to 90 GB, so a 64 GB PC refuses them and a 128 GB computer runs them. 6× and 8× of 3.5k renders are refused on every computer for now; a later release lifts those limits. See the [known issues](../KNOWN-ISSUES.md).

**Updating.** Install over 5.0.0 Beta 1: your models, settings, outputs and waiting images are kept. If you changed `ram_cap_gb` in settings.json by hand as a workaround, 5.0.1 keeps your value; to use the new default, remove that entry as the [installation guide](../INSTALL.md#update-from-500-beta-1) describes.

Targets native x64 Windows 10 22H2 or Windows 11 22H2+, with an NVIDIA RTX card and 64 GB of system memory. Physical verification remains Windows 11 and RTX 5090. See the [installation guide](../INSTALL.md), [Tips](TIPS.md), [Troubleshooting](TROUBLESHOOTING.md), the [compatibility notes](COMPATIBILITY.md), the [known issues](../KNOWN-ISSUES.md) and the [validation record](VALIDATION.md). This is an unsigned beta; compare the download with the published checksums and review results before delivery.

[Download the installer](https://github.com/freddiefiasco/STUDIO-ARTEGRA/releases/download/artegra-enhancer-v5.0.1-beta.1/ArtegraEnhancer-5.0.1b1-Setup.exe)

## 5.0.0 Beta 1

This is the first beta of Artegra Enhancer. It brings the enhancement tab up to date with all its latest fixes, renames the modes, and adds an update check and a Windows uninstaller.

**Redux and Bolt.** Standard is now Redux, for finals; Fast is now Bolt, for quick drafts. Each has a small mark: Redux's stacked courses and Bolt's strike, beside the names and on every queued image and result. A Bolt result is saved as `name_cu2x_bolt.png`; older `_fast` results are still recognised.

**The enhancement tab.** The tab, the service behind it and the finish times have all their latest fixes. Bolt is offered only once its files are checked. On two identical RTX 5090 cards a single Bolt image uses both cards; everywhere else each Bolt image uses one card, and the finish time says so. Saved images are made by the same engine and recipes as in the alphas; only the live preview's fallback changed.

**Check for updates.** In Settings and About. It asks GitHub only when you click it and never downloads or installs anything.

**Uninstall.** From Installed apps, the Start menu or Settings. It closes only the app's own processes, never removes your images, and offers to also remove the downloaded enhancement files and the settings and logs, both off by default.

**Upgrading.** Install over alpha 4: your models, settings, outputs and memory choice are kept. Setup shows the terms page again and checks the models you have; it does not download them again.

Targets native x64 Windows 10 22H2 or Windows 11 22H2+, with an NVIDIA RTX card and 64 GB of system memory. Physical verification remains Windows 11 and RTX 5090. See the [installation guide](../INSTALL.md), [Tips](TIPS.md), [Troubleshooting](TROUBLESHOOTING.md), the [compatibility notes](COMPATIBILITY.md), the [known issues](../KNOWN-ISSUES.md) and the [validation record](VALIDATION.md). This is an unsigned beta; compare the download with the published checksums and review results before delivery.

[Download the installer](https://github.com/freddiefiasco/STUDIO-ARTEGRA/releases/download/artegra-enhancer-v5.0.0-beta.1/ArtegraEnhancer-5.0.0b1-Setup.exe)
