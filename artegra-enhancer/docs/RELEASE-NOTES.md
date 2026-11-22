<!-- release-draft: engines. Draft for the next release. The release step writes the version heading and text, keeps the one paragraph marked "Variant" that the proof record supports (and only that one), removes the other variants, this note and the markers. The third variant needs the release owner's approval. There is no halo-fix variant: the halo fix is not proven, so the Large-image engine keeps the Classic engine's halos. Never write that the two engines give identical results on the reader's computer: in this release they never run the same plan for one person. -->

## Engines (draft for the next release)

**Two engines.** This release has two engines. The Classic engine is the one in 5.0.1: it makes every upscale it can make on your computer, with the same passes as 5.0.1 and, apart from the Protect change below, the same pixels. The new Large-image engine makes only the sizes the Classic engine cannot make on your computer, up to 32,000 px on the longest side. It runs Redux only; Bolt stays on the Classic engine, with the limits it has in 5.0.1. The plan for each image and the caption of its result say which engine runs it, and so does the image's row in the list where it has room.

**How the Large-image engine differs.** It works on the image in bands and keeps the image in work files on the work drive. It still needs more memory for larger outputs, and a size that does not fit this computer's memory is refused before it starts. Before an image starts, its plan gives the estimated time on your graphics card, the output size, the free disk space its work files need and the memory class of your computer. A Large-image upscale can restart the image engine between passes, so that the memory the last pass held is given back; the estimated time counts each restart.

**The first Large-image image on a computer.** Unless your kind of processor was measured before this release, the app first measures how your computer's processor runs the Large-image engine's finish, and the first Large-image image waits while it does. The measurement uses the processor, not the graphics card. On our test PC's processor it took about 22 to 25 minutes; a slower processor takes longer. It can run again for a size it has not measured yet, or after an update changes the image engine. If it cannot finish, the largest Large-image sizes are refused on this computer, and the refusal says that the processor has not been measured.

Variant (proof tier 0): The Large-image engine runs the same enhancement steps as the Classic engine over the whole image. On our test PCs, at the sizes both engines can run, its results were pixel-identical to the Classic engine's. It also keeps the Classic engine's look, including its edge halos.

Variant (proof tier 1): The Large-image engine runs the same enhancement steps as the Classic engine over the whole image. On our test PCs, at the sizes both engines can run, its results were identical to the Classic engine's except for isolated one-level differences. It also keeps the Classic engine's look, including its edge halos.

Variant (proof tier 2, for the size classes the proof names, only with the release owner's approval): The Large-image engine runs the same enhancement steps as the Classic engine over the whole image. On our test PCs, at the sizes both engines can run, its results were judged equal to the Classic engine's at 1:1 for <size classes>. It also keeps the Classic engine's look, including its edge halos.

**What both engines do, as in 5.0.1.** The finish puts small areas the enhancement invented back to the x4 upscaling model's picture, and carries the source's broad tones (its low frequencies) into the result. Both engines leave the light and dark halos along strong edges of geometry that 5.0.1 leaves; reducing them is planned for a later version.

**Large Protect passes.** With Protect on, a large pass no longer spills into shared graphics memory: above about 18 MP the protected areas are found by a step that enlarges only the masks it keeps, using far less graphics memory.

**Finish times.** Finish times now count the work on large inputs and outputs. A Redux 6× of a 2350 × 1762 image with Protect on said 81 min in 5.0.1 and took 115 min on an RTX 5090; it now says 119 min.

<!-- /release-draft -->

# Artegra Enhancer (Beta) 5.0.1 Beta 1

**What runs now.** On a 64 GB PC with one RTX 5090, Redux and Bolt make 2× of 3500 × 2188 renders and Redux makes 4× of a 1280 × 1600 image, all at full quality. Redux also makes 2× of a 2800 × 3500 render, at the lighter setting its size needs. 5.0.0 Beta 1 refused them for memory. Every image 5.0.0 Beta 1 could make is planned with the same passes and made exactly as before.

**Why it refused them.** It estimated 2× of a 3500 × 2188 render at 61.5 GB, against measured peaks of 51 GB in Bolt and 46 GB in Redux, and it kept back 10 % of the computer's memory, which left 55 GB on a 64 GB PC. The estimate now comes from peaks measured on RTX 5090 PCs, plus a 3 % margin, and the app keeps back 4 %, and at least 2.5 GB, which leaves 59 GB.

**When memory is short.** The app first tries a lighter setting at the size you chose, and the image's caption says so. Only when even that does not fit is the image refused, with the amount it needs. Bolt says when memory, not size, is the reason.

**What is still refused.** Redux 4× of a 3500 × 2188 render and Redux 6× or 8× of a 1280 × 1600 image need about 65 to 90 GB, so a 64 GB PC refuses them and a 128 GB PC runs them. 6× and 8× of a 3500 × 2188 render and 4× of a 2800 × 3500 render are over the engine's output limit of about 150 MP, so every computer refuses them; lifting that limit is planned. See the [known issues](../KNOWN-ISSUES.md).

**Updating.** Install over 5.0.0 Beta 1: your images, output folder, settings, waiting images and enhancement files are kept. If you changed `ram_cap_gb` in `settings.json` by hand as a workaround, 5.0.1 keeps your value; to use the new default, remove that entry as the [installation guide](../INSTALL.md#update-from-500-beta-1) describes.

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
