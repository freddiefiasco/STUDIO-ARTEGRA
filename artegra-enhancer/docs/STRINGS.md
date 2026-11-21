# Host strings

Every sentence follows Studio Artegra's copy policy: plain words, sentence case, say what happened and what to do.

## Names

- Artegra Enhancer (Beta)
- Version 5.0.1 Beta 1
- Redux (the API mode `standard`) and Bolt (`fast`)

## Header and pages

- About · Settings · Activity · Shortcuts · Show panels / Hide panels · Back to images · Back
- Welcome to Artegra Enhancer (Beta).
- Demo: no graphics card is used.
- Made by Studio Artegra. Uses Qt under the LGPLv3. The model licences are listed in MODEL-LICENSES.md in the app folder.
- Release notes · Source on GitHub · Licences

## Updates

- Updates
- Check GitHub for a newer version. Nothing is downloaded or installed until you choose to.
- Check for updates
- Checking for updates…
- Artegra Enhancer (Beta) 5.0.1 Beta 1 is up to date.
- Artegra Enhancer (Beta) 5.0.1 Beta 2 is available. (with **Download**, which opens the release page in the browser)
- Couldn't reach GitHub. Check your connection and try again.

## Uninstall

- Uninstall Artegra Enhancer…
- Uninstall Artegra Enhancer (Beta)?
- The app closes and Windows removes it. You can keep or remove the downloaded enhancement files and your settings. Your enhanced images are never removed.
- Uninstall · Keep it
- Uninstall works in an installed copy. Use Installed apps in Windows Settings.
- The uninstaller could not start. Use Installed apps in Windows Settings to remove the app.
- Installer: Uninstall %1? Your enhanced images are never removed. Next, you can choose whether to also remove the downloaded enhancement files and your settings.
- Installer: This removes the app. Your enhanced images are never removed.
- Installer: Also remove downloaded enhancement files (about 21 GiB) · Also remove settings and logs
- Installer: Artegra Enhancer (Beta) is still running. Close it, then try again.

## Modes

The image controls keep the enhancement tab's existing wording with the new names, for example:

- Quicker drafts. Use Redux for finals.
- Bolt upscales 2× only. Choose Redux for 4× and above.
- Bolt offers Light and Default only. Choose Redux for Strong, Heavy, Extreme or Custom.
- Bolt works on images up to about 9 MP. Choose Redux for larger images.
- Bolt needs more memory for this image than this computer has. Choose Redux, which uses a lighter setting to fit.
- Bolt needs more memory for this image than this computer has.
- Too large for Bolt on this computer: runs in Redux. · Too large for Bolt on this computer. · Images too large for Bolt run in Redux.
- Bolt is not ready yet: its files are still being checked. Try again in a moment.
- This image is too large for Bolt, so it was not upscaled. Queue it again in Redux.
- Upscale again in Redux · Try again in Redux · Mode set to Redux
- Mode set to Redux · Mode stays Redux · Images you queue next set to Redux · Images you queue next stay in Redux, with the reason: Strong, Heavy and Extreme are Redux only. · 4× and above are Redux only. · Fine-tuning is Redux only.
- 1 waiting Bolt image put in Redux: Bolt upscales 2× only, and it is back at 4×.
- Saved as name_cu2x_bolt.png

## Out of memory

- Try again with Save GPU memory (tooltip: Turns on Save GPU memory, then tries this image again)
- Try again with Save GPU memory?
- Save GPU memory uses less graphics memory, so <image> may fit. It stays on for later images, which can take longer and may differ slightly. You can change it in Settings.
- Turn on and try again · Not now
- Save GPU memory could not be turned on.

## System memory

- This upscale would need about <N> GB of memory, more than the <M> GB the app may use. Choose a smaller upscale or a smaller image.
- Uses a lighter setting to fit this computer's memory. · Uses a lighter setting at this size. · Later passes use a lighter setting at this size.
- Waiting for memory: another image is using the memory this one needs. It starts when that one finishes.
- Waiting for memory: this image needs more memory than the app may use now. Queue it again at a smaller upscale.

## Setup and errors

- Install Artegra Enhancer (Beta) · Set up Artegra Enhancer · Resume setup · Try again · Setup stopped
- Opening your workspace · Starting the image engine…
- The image engine is not running
- Your images and the waiting list are kept. Unfinished images carry on when the engine starts again.
- The image engine stopped unexpectedly. Choose Try again to start it.
- Artegra Enhancer (Beta) needs 64 GB of system memory for normal enhancement. Setup stopped before the large downloads. A larger pagefile does not replace this.
- Artegra Enhancer could not start. Run the installer again to repair it. Your images and enhancement files are kept.
- Validation and connection errors in host/config.py and host/app.py name the missing folder, incomplete runtime, stopped engine or log action.

## Engines (5.0.2)

5.0.2 has two engines. The Classic engine is 5.0.1's and runs every plan it can run on this computer, with 5.0.1's passes and, apart from large Protect passes (see the release notes), its pixels. The Large-image engine runs only sizes the Classic engine cannot run here. Every plan and result names its engine. The copy gives measured facts only: which engine, the time, the output size, the disk space needed and the memory class. It never claims more than those facts. Lines marked (log) appear in Activity and the log only.

### Plan card, queue row and caption

- Engine: Classic
- Engine: Large-image (this size is beyond the Classic engine on this computer)
- Engine: Large-image (developer comparison run) — developer builds only
- Includes the edge-halo fix; the Classic engine keeps 5.0.1's look. — only for a plan whose finish carries a ported halo fix; none does in this build, so no plan card shows it
- about <N> GB free disk space for the work files
- Memory class: <48, 64 or 128 GB> PC
- Classic — the queue row's tag beside the size, for example "Becomes 7,000 × 4,376 px, Classic"
- Large-image — the queue row's tag, for example "Becomes 28,000 × 17,504 px, Large-image"
- Classic engine — on a result's caption
- Large-image engine — on a result's caption

### Large-image plans the engine refuses

These are the Large-image planner's reasons. When it refuses a size, the app shows the Classic engine's own refusal instead, as in 5.0.1.

- Choose an upscale of 2×, 4×, 6× or 8×.
- Bolt is not available for the Large-image engine in this version.
- This image is outside the supported sizes.
- <F>× would make <W> × <H> px, over the <32,000> px limit for the longest side.
- The Large-image engine needs a computer with at least 48 GB of memory.
- The Large-image engine is not yet proven for a <N> MP result on a <M> computer.
- This image is too small for the Large-image engine.
- This image needs about <N> GB of memory with the Large-image engine, more than the <M> GB it may use on this computer.
- The forced Large-image plan needs about <N> GB, over the cap. — developer builds only

### Large-image passes

- Pass <N> of <M> · Large-image engine
- Pass <N> of <M> started (Large-image engine<, part A or B>) — (log)
- Pass <N> of <M> sent to the engine (Large-image) — (log)
- Pass <N> of <M>: the finish runs in a fresh engine process — (log)
- Pass <N> of <M> finished in <S> s — (log)
- Upscaled <name> in <S> s — (log)
- The Large-image engine is not installed correctly, so this image was not upscaled. Choose Repair installation in Settings.
- The work files for this image are missing. Add the image again and start a new upscale.
- An intermediate result has an unexpected size, so this image was stopped.
- This image was stopped because of an internal size mismatch. Details are in the log.
- The engine result for pass <N> of <M> is missing or has the wrong size, so this image was stopped.
- The engine could not be restarted for the last step of this pass.
- The engine could not accept pass <N> of <M>: it is missing a part it needs (the Large-image engine). Details are in the log.
- The engine stopped answering at the start of pass <N> of <M>.
- The finished image is missing or damaged in the work folder, so it could not be saved.
- The finished image has an unexpected size, so it was not saved.

### Large-image admission, split finish and resume (5.0.2 build wave 1)

Graphics-card admission, the memory check across a split finish, and resuming a pass from its saved first part.

- The Large-image engine needs a graphics card with at least 8 GB of memory. — refused before the start
- The Large-image engine is not yet proven on <M> GB graphics cards. — refused before the start (8, 10 and 11 GB cards until the 8 GB emulation passes)
- A <M> GB graphics card can render up to <L> MP with the Large-image engine; this image needs <R> MP. — refused before the start
- This image's Large-image plan was made by another version of the app, and this version cannot make it. Queue the image again.
- The engine did not give its memory back when it was restarted for the last step of pass <N> of <M>, so this image was stopped.
- The saved first part of pass <N> of <M> could not be used (<why>), so the pass is made again from its start. — the image's line and the log
- Pass <N> of <M> goes on from its saved first part — (log)
- Pass <N> of <M>: memory across the split finish — (log)
- Pass <N> of <M>: the memory the engine gave back could not be measured — (log)
- The split record could not be stored: <reason> — (log)
- The live preview picture could not be made for this pass: <reason> — (log)
- <name> uses the Large-image engine, so Speed up upscaling is not used for it — (log)

### Large-image result files and viewer

- JPEG allows at most <N> px per side
- TIFF data passed 4 GiB; write it as BigTIFF — (log)
- Unknown output format <name> — (log)
- Region width and height must be 1 to <N> px
- The region is outside the image
- The viewer copy of the result could not be made: <reason> — (log)
- Temporary file <path> could not be removed: <reason> — (log)

### Developer builds

- This developer setting is not available in this build.
- A job asked for a developer setting this build does not have — (log)
- Developer build: the Large-image engine is admitted up to the developer sizes — (log)

### Setup on 48 GB PCs

Shown only when Setup's 48 GB switch is on, which waits for the 48 GB measurements (gate R6). Until then Setup says the 64 GB sentence under Setup and errors.

- Artegra Enhancer (Beta) needs 48 GB of system memory or more. A 48 GB PC makes 2× of 3500 × 2188 and 2800 × 3500 renders and 4× of a 1280 × 1600 image, at the lighter setting their size needs; larger upscales need more memory. Setup stopped before the large downloads. A larger pagefile does not replace this.
