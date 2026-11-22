# Questions and answers

## About the app

### What does Artegra Enhancer do?

It makes architectural renders larger and adds fine detail, on your own Windows computer, with an NVIDIA RTX graphics card. You add renders, choose a mode, a scale and a Look, and it saves the results beside a record of the settings used.

### Who is it for?

Visualisation artists and studios who need print-size or presentation-size images from their renders, and who prefer to keep client work on their own machines.

### What happened to Standard and Fast?

They were renamed in this Beta: Standard is now **Redux** and Fast is now **Bolt**. They work as before, and your stored jobs and settings carry over. Results from the alphas ending `_fast` are still recognised as Bolt results; new Bolt results end `_bolt`.

### What is the difference between Redux and Bolt?

Redux is for finals: every Look, scales up to 8×, images up to 80 MP. Bolt is for drafts: 2× only, Light or Default, images up to about 9 MP, in about half the time, with a slightly different look. See [Redux or Bolt](TIPS.md#redux-or-bolt).

### Why is Bolt limited to 2×, Light and Default?

Bolt uses a shorter recipe that was tested and approved only for those settings. For anything else, use Redux. When you choose a setting Bolt cannot do, the app switches the Mode to Redux and tells you why.

### Is there a mode quicker than Bolt?

Not in this Beta. The setting "Speed up upscaling" (Faster) stays off.

### How long does an image take?

It depends on the card, the image size, the mode and the scale. On an RTX 5090, a 768 × 768 pixel crop at 2× took about 3 minutes in Redux and about 1.5 minutes in Bolt; a 4× Redux chain on a 384 pixel crop took about 4 minutes. Larger images take longer. Before you start, the app shows a finish time, which in the release tests was always longer than the time the image took.

### Which image files can it open and save?

It opens PNG, JPEG, TIFF, WebP and BMP. It saves PNG (8-bit or 16-bit), TIFF (16-bit) or JPEG (quality 95). Results are saved in sRGB; an Adobe RGB or Display P3 original is converted without a note.

<!-- release-draft: engines. Kept, changed or removed by the release step from the proof record. -->

### What are the Classic and Large-image engines?

The Classic engine is the one in 5.0.1. It makes every upscale it can make on your computer. The Large-image engine makes the sizes the Classic engine cannot make on your computer, up to 32,000 px on the longest side. The plan, the image's row and the result's caption say which engine runs it. See the [release notes](RELEASE-NOTES.md) for how the two engines compared on our test PCs.

### Why does my image say "Large-image"?

Its size is too large for the Classic engine on this computer. The plan gives the estimated time, the output size, the free disk space its work files need and the memory class of your computer before it starts.

### Why does my first Large-image image wait before it starts?

Unless your kind of processor was measured before this release, the app first measures how your computer's processor runs the Large-image engine's finish, and the image waits while it does. The measurement uses the processor, not the graphics card. On our test PC's processor it took about 22 to 25 minutes; a slower processor takes longer. It can run again for a size it has not measured yet, or after an update changes the image engine. If it cannot finish, the largest Large-image sizes are refused on this computer, and the refusal says that the processor has not been measured.

### Why does the image engine restart during a Large-image upscale?

A Large-image upscale can restart the image engine between passes, so that the memory the last pass held is given back before the next pass. The estimated time in the plan counts each restart.

### Does the Large-image engine fix the halos along edges?

No. It keeps the Classic engine's look, including the light and dark halos along strong edges of geometry. Reducing them is planned for a later version.

<!-- /release-draft -->

## Computer and installation

### Which graphics cards work?

NVIDIA RTX cards with at least 8 GB of graphics memory. The RTX 5090 is tested. The RTX 5080, 4090, 4080 and 3090 are expected to work but are not tested yet, and the RTX 3080 is experimental. AMD and Intel graphics are not supported, and there is no Mac or Linux version. See [the compatibility notes](COMPATIBILITY.md).

### Does it work on a laptop?

Laptop RTX cards are not tested. They have less memory and power than desktop cards of the same name. The same requirements apply: at least 8 GB of graphics memory and 64 GB of system memory.

### Can I use it with 32 GB of system memory?

No. This Beta needs 64 GB. On a 32 GB computer, setup stops before the large downloads. A larger pagefile does not raise the memory the app may use.

### Why does Windows warn me about the installer?

This Beta is not code-signed, so Windows SmartScreen and your browser may say the publisher is unknown or that the file is not commonly downloaded. Download it only from the [Studio Artegra release page](https://github.com/freddiefiasco/STUDIO-ARTEGRA/releases/tag/artegra-enhancer-v5.0.1-beta.1), check it against `SHA256SUMS.txt` if you want to (see [the installation guide](../INSTALL.md#download-and-check-the-file)), then choose **More info** and **Run anyway**.

### Does it need administrator rights?

No. It installs for your Windows account only.

### Do I need an internet connection?

For the first installation and for Repair, yes: setup downloads the image engine and about 14 GiB of models from their publishers. After that, enhancing images works offline. **Check for updates** needs a connection when you use it.

### Can I keep the models on another drive?

Yes. Choose the drive on the **Installation location** page of setup. To move them later, run the installer again and choose the new location; see [Tips](TIPS.md#keep-the-enhancement-files-on-another-drive).

### I have an alpha installed. Do I need to uninstall it first?

No. Run the Beta's installer over it. Your images, settings, memory choice and enhancement files are kept, and the enhancement files are checked rather than downloaded again. See [Upgrade from an alpha](../INSTALL.md#upgrade-from-an-alpha).

## Using it

### Where are my results?

In **Pictures → Artegra Enhancer**, unless you chose another folder in Settings or under **Output**. **Show file** under a result opens it in Explorer.

### What is the .json file next to each result?

A record of how the result was made: the settings, the time, checksums of both images and their full paths. **Use these settings** reads the settings back. The paths usually include your Windows user name, so remove the .json files before you send a folder to anyone.

### Can I use two graphics cards?

Yes. Each card takes its own image from the list. A single Bolt image is shared by two identical RTX 5090 desktop cards, and Redux can share an image across two cards. See [Two graphics cards](TIPS.md#two-graphics-cards).

### An image ran out of graphics memory. What now?

Choose **Try again with Save GPU memory** when the app offers it, close other programs that use the card, or try a smaller scale. See [Troubleshooting](TROUBLESHOOTING.md#enhancing-images).

## Updates, removal and terms

### How do I update?

Choose **Check for updates** in Settings or About. If a newer release exists, **Download** opens its page in your browser. Install it over your current copy. The app never updates itself.

### How do I uninstall, and what is kept?

Use **Settings → Uninstall Artegra Enhancer…**, the Start menu or Installed apps. Your enhanced images are always kept. You choose whether to also remove the downloaded enhancement files and the settings and logs. See [Uninstall](../INSTALL.md#uninstall).

### Can I use the results commercially?

Each model has its own terms, and some limit how outputs may be used. Read [MODEL-LICENSES.md](../MODEL-LICENSES.md) and decide for your use. You remain responsible for the rights to the images you put in.

### Under what terms is the Beta provided?

For evaluation, under [LICENSE.txt](../LICENSE.txt) and the [beta terms](../BETA-TERMS.md), without a warranty or a support commitment. Review results before you deliver them.

### Does Studio Artegra see my images or my usage?

No. Nothing is uploaded and there is no analytics. See [PRIVACY.md](../PRIVACY.md).

### How do I report a problem or suggest something?

Save support details from Settings, check the file, and [open an issue](https://github.com/freddiefiasco/STUDIO-ARTEGRA/issues/new/choose). [FEEDBACK.md](../FEEDBACK.md) lists what to include.
