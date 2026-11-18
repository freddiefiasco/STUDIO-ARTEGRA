# Beta limits

- Physical GPU qualification is RTX 5090 32 GB. Windows 10 and other physical GPU models are unverified. See [COMPATIBILITY.md](docs/COMPATIBILITY.md).
- Bolt supports Light and Default at 2×, for images up to about 9 MP. A single Bolt image shares two cards only on two identical desktop RTX 5090 cards with the original memory settings. "Speed up upscaling" (Faster) stays off.
- Redux can share one image across two cards of any kind, as in the alphas. That was proven on two RTX 5090 cards only; mixed or other cards are unverified.
- A two-card Bolt image could not be re-run for this beta (the test machines have one card each). Its code and prompts are the same as in Studio Artegra's in-house build, where it was proven on two RTX 5090 cards.
- Planned for a later version: if Bolt is requested in the first seconds while its files are still being checked, the request can wait up to 20 seconds; a live preview that reconnects mid-pass loses that pass's name; the remaining time of an image shared by two cards is covered by unit tests only; the first answer for a Bolt batch can show the two-card figure.
- The Beta needs 64 GB of system memory. The planner needs at least 30 GiB of application memory, so 32 GB machines are refused even with a large pagefile.
- Save GPU memory keeps the original tile sizes and numerical options; selected outputs passed visual review but are not pixel-identical to the original settings.
- The installer downloads the required software and models after you accept the terms; the first installation needs internet access. Models are not bundled. Updates are never downloaded or installed automatically.
- Going back from the Beta to an alpha (installing an alpha over it) is not supported.
- The portable ZIP opens only from a short folder path. Extracted under a folder path longer than about 110 characters (a deep folder or a long network path), Windows cannot load some of its files and the window does not open. Extract it to a short folder on a local drive, for example a folder named ArtegraEnhancer at the top of drive C. The installer always uses a short folder.
- With the AI files on a network drive, the uninstaller takes about two minutes to show its options after you confirm, while it measures them, and removing them takes about ten minutes. Nothing is removed before you choose.
- Every install, upgrade and repair checks each AI file again; they are not downloaded again. With the files on a network drive, installing over an existing installation took about two and a half minutes.
- Installed apps shows the size of the app itself, about 400 MB. The AI files and the image engine, about 21 GiB, are not counted there; the uninstaller shows their size.
- The app's program file has no version details in its Windows properties (they read 0.0.0.0). Installed apps and About show the right version.
- If you saved images inside the app's image engine folder, **Also remove downloaded enhancement files** keeps them and that folder. Move them out before you install again: setup can refuse an image engine folder that holds other files.
- Model terms differ. The tile model publisher declares the OpenRAIL family without an exact version; its card and restrictions are shown before download. SAM has custom terms.
- The existing FP16 detailed-preview decoder is recognised and kept; a new publisher download is FP32. Preview precision differs; the saved-image pipeline is unchanged.
- The build is unsigned, so Windows may show a publisher or reputation warning. Download it from the linked Studio Artegra GitHub release. Checksums are supplied.

## Interface limits (planned for a later version)

- One set of settings applies to all waiting images. A change made during a batch reaches every image still waiting.
- With a finished image selected, the panel shows the settings for the next run. **Use these settings** loads what that image was made with.
- The selected image's row does not repeat its status; the line under the picture shows it.
- The chosen option and the selected image are marked by a slightly lighter background, which can be hard to see on a bright screen or a projector.
- The settings panel moves down by a line when a batch starts or an image finishes.
- During a batch, an image that ran out of graphics memory offers the same request again. **Try again with Save GPU memory** appears once no other image is working. Nothing warns before a run that memory is tight.
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
- When full detail cannot be loaded at 100 %, the picture shows the preview, and only Activity says so.
