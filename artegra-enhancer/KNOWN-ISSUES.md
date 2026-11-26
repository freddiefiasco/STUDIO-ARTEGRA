# Known issues

What this Beta does not do yet, and the rough edges we know about. For error messages and what to do about them, see [Troubleshooting](docs/TROUBLESHOOTING.md).

## Beta limits

- Testing covered the RTX 5090 (32 GB) on Windows 11. Windows 10 and other graphics cards are expected to work but are not tested yet. See [COMPATIBILITY.md](docs/COMPATIBILITY.md).
- Bolt supports Light and Default at 2×, for images up to about 9 MP. A single Bolt image shares two cards only on two identical desktop RTX 5090 cards with the original memory settings. "Speed up upscaling" (Faster) stays off.
- Redux can share one image across two cards of any kind, as in the alphas. That was proven on two RTX 5090 cards only; mixed or other cards are not tested.
- A Bolt image shared by two cards was not run again for this Beta. Its code and prompts are the same as in Studio Artegra's in-house build, where it was proven on two RTX 5090 cards.
- The Beta needs 64 GB of system memory. On a computer with 32 GB, setup stops before the large downloads, even with a large pagefile.
- On a 64 GB PC, the largest upscales need more memory than the app may use and are refused with the amount they need: Redux 4× of a 3500 × 2188 render (about 86 GB) and Redux 6× and 8× of a 1280 × 1600 image (about 65 and 90 GB). They run on a 128 GB PC. Making them fit in 64 GB is planned.
- 6× and 8× of a 3500 × 2188 render and 4× of a 2800 × 3500 render are refused on every computer: the result would be over the engine's output limit of about 150 MP. Lifting it is planned.
- The memory estimate comes from peaks measured on an RTX 5090 with the original memory settings, one image per card. Save GPU memory (on cards with 24 GB or less) and one image shared by two cards are not measured yet.
- Save GPU memory keeps the original tile sizes and numerical options. Selected outputs passed visual review, but they are not pixel-identical to the original settings.
- The installer downloads the required software and models after you accept the terms, so the first installation needs internet access. Models are not bundled. Updates are never downloaded or installed automatically.
- Going back from the Beta to an alpha (installing an alpha over it) is not supported.
- The portable ZIP opens only from a short folder path. Extracted under a folder path longer than about 110 characters (a deep folder or a long network path), Windows cannot load some of its files and the window does not open. Extract it to a short folder on a local drive, for example a folder named ArtegraEnhancer at the top of drive C. The installer always uses a short folder.
- With the AI files on a network drive, the uninstaller takes about two minutes to show its options after you confirm, while it measures them, and removing them takes about ten minutes. Nothing is removed before you choose.
- Every install, upgrade and repair checks each AI file again; they are not downloaded again. With the files on a network drive, installing over an existing installation took about two and a half minutes.
- Installed apps shows the size of the app itself, about 400 MB. The AI files and the image engine, about 21 GiB, are not counted there; the uninstaller shows their size.
- The app's program file has no version details in its Windows properties (they read 0.0.0.0). Installed apps and About show the right version.
- If you saved images inside the app's image engine folder, **Also remove downloaded enhancement files** keeps them and that folder. Move them out before you install again: setup can refuse an image engine folder that holds other files.
- Model terms differ. The tile model's publisher declares the OpenRAIL family without an exact version; its card and restrictions are shown before download. SAM has custom terms.
- The existing FP16 detailed-preview decoder is recognised and kept; a new publisher download is FP32. Preview precision differs; saved images are unchanged.
- The build is not code-signed, so Windows may show a publisher or reputation warning. Download it from the Studio Artegra GitHub release. Checksums are supplied.

<!-- release-draft: engines. Kept, changed or removed by the release step from the proof record. -->

## Engines (next release)

- The Large-image engine makes only the sizes the Classic engine cannot make on your computer. Images the Classic engine can make, including those it makes at a lighter setting for memory, stay on the Classic engine.
- A Large-image upscale keeps its work files on the work drive while it runs. Its plan says how much free space they need before it starts: about 185 GB at 8× of a 3500 × 2188 render.
- The largest Large-image upscales can take hours. The time in the plan is an estimate for your graphics card.
- The first Large-image image on a computer waits while the app measures how the computer's processor runs the Large-image engine's finish, unless that kind of processor was measured before this release. On our test PC's processor this took about 22 to 25 minutes; on a slower processor it takes longer.
- A Large-image upscale can restart the image engine between passes, so that the memory the last pass held is given back. The estimated time in the plan counts each restart.
- Both engines leave the light and dark halos along strong edges of geometry that 5.0.1 leaves. Reducing them is planned for a later version.
- An image's row in the list names its engine only when the row has room. The plan under the picture names it until the image is queued, and the caption names it on the finished result.
- The Large-image engine runs Redux only. Bolt stays on the Classic engine, with the limits listed under Beta limits above.
- The Large-image engine runs only on graphics cards with 12 GB of memory or more; on a smaller card the image is refused before it starts.
- On a graphics card with 24 GB or less, an image that needs more graphics memory than the card has is accepted as in 5.0.1. It may run slowly, because the part that does not fit may use shared memory; how much longer it takes has not been measured. The line under the picture says so while the image waits and while it is queued (a narrow window cuts the line; the whole note shows when you point at it), and the Activity log when it starts. On a PC with a small and a large graphics card, an image the small card cannot hold runs there when the larger card is busy or its engine cannot start, as in 5.0.1, and gets the note when it starts. As in 5.0.1, a pass that takes far longer than expected is stopped. These upscales have not yet been run on a card of 24 GB or less.
- On a 6 GB graphics card every image carries that note, because the estimate counts the enlarging step's full-size tile, which alone is more than such a card has free. The step halves its tile when it runs out of graphics memory, so the note may be a false alarm there; this has not been measured.
- For this release the Large-image engine was run on these graphics cards only: <the graphics cards from the proof record>. Other cards with 12 GB of memory or more are admitted, but it has not been run on them.
- Setup still needs 64 GB of system memory. Support for 48 GB PCs is planned once their upscales are measured.

<!-- /release-draft -->

## Planned for a later version

- If you choose Bolt in the first seconds after the app opens, while Bolt's files are still being checked, the image can wait up to 20 seconds before it starts.
- If the live preview reconnects during a pass, that pass's name is not shown until the next one starts.
- The remaining time of an image shared by two cards has been checked by automated tests only, not on two cards.
- When a batch of Bolt images starts on two RTX 5090 cards, its first finish time can briefly be the one for a single image shared by both cards. It corrects itself a moment later.

## Interface limits (planned for a later version)

- One set of settings applies to all waiting images. A change made during a batch reaches every image still waiting.
- With a finished image selected, the panel shows the settings for the next run. **Use these settings** loads what that image was made with.
- The selected image's row does not repeat its status; the line under the picture shows it.
- The chosen option and the selected image are marked by a slightly lighter background, which can be hard to see on a bright screen or a projector.
- The settings panel moves down by a line when a batch starts or an image finishes.
- During a batch, an image that ran out of graphics memory offers the same request again. **Try again with Save GPU memory** appears once no other image is working. On a graphics card of more than 24 GB nothing warns before a run that memory is tight.
- When the image engine stops, the workspace stays closed until you choose **Try again**. It does not restart by itself. Unfinished images carry on when it starts.
- If one graphics card's engine fails to start, the app says the engine did not start although the other card carries on, and **Add** waits until the batch ends.
- Finish times use the 24-hour clock and do not say "tomorrow". Batch progress counts finished images only.
- Each enhanced image has a .json file beside it that records the full paths of the original and the enhanced image (see PRIVACY.md). It cannot be turned off yet. Remove these files before you send a folder to anyone.
- Images are saved in sRGB. An Adobe RGB or Display P3 source is converted without a note.
- Where Helvetica Neue is installed the app uses it; elsewhere it uses its bundled face, Instrument Sans. The app can look slightly different from one computer to another.
- The picture cannot be panned from the keyboard. Single-key shortcuts (B, M, 0, 1, R, ?) also act while the image list has focus.
- Esc during a batch asks whether to cancel it. Closing during a batch offers only **Keep open** or **Stop and close**.
- A greyed control gives its reason only on hover. The **Remove** and **Show file** words on image rows are small targets.
- Notices can cover the last rows of a long image list. Ctrl+Z puts back removed images only.
- Undo after choosing Bolt can leave a stopped image set to Bolt if you selected a different image first. Check its settings before queueing it again.
- In windows smaller than about 1280 × 720, Detail, Protect and Output can scroll out of sight with no scroll bar.
- In small windows at 125 % display scaling, the start of a long result name can be cut off, so only its end shows (for example "…_cu2x_bolt.png").
- When full detail cannot be loaded at 100 %, the picture shows the preview, and only Activity says so.
- **Settings → Graphics memory** says 64 GB of system memory is "recommended". It is required.
- **Settings → Updates** says "Nothing is downloaded or installed until you choose to". The app never downloads or installs anything: **Download** opens the release page in your browser.
- At 100 % display scaling, Bolt's mark is drawn with a thin stepped line and looks fainter than Redux's. It is crisp at 125 % and 150 %.
- While the app opens, and when the image engine has stopped, the status bar at the bottom repeats the sentence on the page.
- **About → Licences** opens the folder of component and model licences. The app's own licence (LICENSE.txt) and THIRD-PARTY-NOTICES.txt are one level up, in the app folder.
- The terms in setup still call Bolt's model "Hyper-SDXL Fast mode". Fast was Bolt's name in the alphas.
