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
- This image needs about <N> GB of memory with the Large-image engine to make <W> × <H> px, more than the <M> GB it may use on this computer.
- The forced Large-image plan needs about <N> GB, over the cap. — developer builds only
- The Large-image engine cannot make <W> × <H> px on this computer: it can finish a pass of up to <N> MP here, and this image needs a <M> MP pass. — while the banded exact finish is not available on this computer, so that each pass runs 5.0.1's whole finish (up to 300 MP)
- This image is too tall and narrow for the Large-image engine: <W> × <H> px is more than <N> times taller than wide.
- Bolt upscales 2× only. Choose Redux for 4× and above. — a Bolt Large-image plan (developer builds only, until banded Bolt is proven)
- Bolt works on images up to about 9 MP. Choose Redux for larger images. — the same

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
- The engine could not accept pass <N> of <M>: it is missing a part of the Large-image engine. Details are in the log.
- The engine stopped answering at the start of pass <N> of <M>.
- The finished image is missing or damaged in the work folder, so it could not be saved.
- The finished image has an unexpected size, so it was not saved.

### Large-image admission, split finish and resume (5.0.2 build wave 1)

Graphics-card admission, the memory check across a split finish, and resuming a pass from its saved first part.

- The Large-image engine needs a graphics card with at least 8 GB of memory. — refused before the start, then the size line under build wave 2 below
- The Large-image engine is not yet proven on <M> GB graphics cards. — refused before the start (8, 10 and 11 GB cards until the 8 GB emulation passes), then the size line under build wave 2 below
- This image's Large-image plan was made by another version of the app, and this version cannot make it. Queue the image again.
- The engine did not give its memory back when it was restarted for the last step of pass <N> of <M>, so this image was stopped.
- The saved first part of pass <N> of <M> could not be used (<why>), so the pass is made again from its start. — the image's line and the log
- Pass <N> of <M> goes on from its saved first part — (log)
- Pass <N> of <M>: memory across the split finish — (log)
- Pass <N> of <M>: the memory the engine gave back could not be measured — (log)
- The split record could not be stored: <reason> — (log)
- The live preview picture could not be made for this pass: <reason> — (log)
- <name> uses the Large-image engine, so Speed up upscaling is not used for it — (log)

### Large-image admission and start-up (5.0.2 build wave 2)

Every Large-image refusal names the size it refuses. The physical-memory lines count the Large-image work files that sit in the computer's memory while the image runs.

- <An or A> <W> × <H> px result needs the Large-image engine on this computer. — after a graphics-card refusal above (8, 10 and 11 GB cards; cards under 8 GB)
- This developer comparison run makes <a or an> <W> × <H> px result with the Large-image engine. — the same, for a developer comparison run (developer builds only)
- <A or An> <M> GB graphics card can render up to <L> MP with the Large-image engine; <a or an> <W> × <H> px result needs <R> MP. — refused before the start, then one of the two lines that follow the next one
- <An or A> <W> × <H> px result needs about <N> GB of graphics memory with the Large-image engine; <this card has or the largest graphics card in use has> <M> GB. — refused before the start
- A smaller image fits this card at <F>×: up to a result of about <W> × <H> px. — after a Classic graphics-memory refusal
- A smaller image fits this card at <F>× with the <Classic or Large-image> engine: up to a result of about <W> × <H> px. — after a Large-image graphics-memory refusal
- No smaller image of this shape fits this card at <F>× with either engine. — after a Large-image graphics-memory refusal when no smaller size fits
- Waiting for memory: the <W> × <H> px result needs about <N> GB of free system memory (RAM) to start, counting its Large-image work files. Close other memory-heavy apps.
- Waiting for memory: another image is using the system memory (RAM) that the <W> × <H> px result needs for its Large-image work files. It starts when that one finishes.
- The <W> × <H> px result needs about <N> GB of free system memory (RAM) to start, counting its Large-image work files, more than this computer can free (<M> GB in all). — refused before the start
- Parts of the Large-image engine did not load when the engine started, so this image was not upscaled. Choose Repair installation in Settings.
- Measuring this graphics card's speed before its first image — the image's line, once for each graphics card of 24 GB or less that has not been timed
- <card name>: measuring its speed before its first image — (log)
- <card name>: <S> s per window — (log)
- The graphics card could not be timed before its first image: <reason> — (log); the image goes on at the card's listed speed
- The engine closed during the graphics card measurement. — (log, as the reason above)
- The engine stopped with an error during the graphics card measurement. — (log, as the reason above)
- The graphics card measurement took too long and was stopped. — (log, as the reason above)
- The card timing could not be read: <reason> — (log)
- The graphics card timing could not be saved: <reason> — (log)
- The viewer copy of a Large-image result could not be made: <reason> — (log)
- The viewer copy of a Large-image result could not be made again: its own picture files are gone from the work folder and the viewer folder — (log)
- <file> belongs to a Large-image result; it is never decoded whole — (log)

### Classic graphics-memory admission (5.0.2; cards of 24 GB or less)

A card of more than 24 GB is not checked, as in 5.0.1.

- This image needs about <N> GB of graphics memory with the <Classic> engine; <this card has or the largest graphics card in use has> <M> GB. — refused before the start, then "A smaller image fits this card ..." above or the next line
- No smaller image of this shape fits this card at <F>× with the Classic engine.

### Large-image engine errors (engine log only)

The Large-image engine's own messages when one of its steps cannot run. They are written to the engine's log and the support bundle. The person sees the app's sentence instead: "The engine stopped with an error in pass <N> of <M>. Details are in the log."

- the classic node pack (claude_creative) is not loaded in this engine
- <node> is not built in this version of the Large-image engine
- a plane (<role>) is not a tensor: <operation> is not allowed (PlaneHint)
- the Large-image engine expects the x4 model
- CUMaskUnionPlane: connect at least one mask
- CUMaskUnionPlane: masks of different sizes
- the canvas (<W> x <H> px) fits one <1024> px window; the Large-image engine does not run such canvases (the Classic engine does)
- ClaudeSpotTilesBanded: the canvas fits one window; the Large-image engine does not run such canvases (the Classic engine does)
- this VAE is not supported by the Large-image engine (it needs an image VAE such as SDXL's)
- a video VAE is not supported by the Large-image engine
- the canvas (<W> x <H> px) must be a whole multiple of <8> px
- the decoded render (<W> x <H>) is not the output (<W> x <H>) times one supersample >= 1
- the hint plane is <W> x <H> px, the canvas <W> x <H>: the Large-image engine never resamples a hint
- ControlNet hint resampling <method> is not supported by the Large-image engine
- ControlNets that preprocess their hint are not supported by the Large-image engine
- the hint must be a plane (PLANE) from the Large-image engine
- a ControlNet hint plane has 1 or 3 channels (got <n>)
- a ControlNet hint plane is u8 or f32 (got <type>)
- a ControlNet hint plane is not a tensor: <operation> is not allowed (PlaneHint)
- a ControlNet hint plane is not a tensor (PlaneHint)
- a hint plane is read only as hint[..., y0:y1, x0:x1] (PlaneHint)
- hint window <y0>:<y1>, <x0>:<x1> outside a <W> x <H> plane
- ClaudeSpotTilesBanded: the ControlNet hint must be a plane (CUControlNetApplyPlane)
- ClaudeSpotTilesBanded splits the windows statically between cards (balance static)
- ClaudeSpotTilesBanded: a latent pixel got no window in this evaluation (wsum min <value>)
- ClaudeSpotTilesBanded brownian_cache must be 1 to 45 (got <value>)
- the Brownian cache cap was proven with torchsde <version>; this engine has <version>
- this torchsde is not the one the Brownian cache cap was proven with
- the Brownian cache cap could not be installed: another noise sampler patch is active
- the Brownian tree was queried before its cache could be capped
- brownian_cache must be 1 to <44> to install a cap (got <value>)
- ClaudeSpotTiles weights must be numbers separated by commas (got <text>)
- ClaudeSpotTiles weights list <n> values for <m> graphics cards
- ClaudeSpotTiles: <n> window group(s) were not evaluated
- ClaudeSpotTiles batch_windows must be >= 1 (got <value>)
- ClaudeSpotTiles balance must be auto, queue or static (got <value>)
- ClaudeSpotTiles seam_overlap must be between 0 and a quarter of the window, <n> latent px (got <value>)
- ClaudeSpotTiles seam_dual must be >= 0 (got <value>)
- ClaudeSpotTiles <pag_end or cfg_end> must be between 0 and 1 (got <value>)
- ClaudeSpotTiles: ControlNets with VAE-encoded hints or extra concat are not supported
- ClaudeSpotTiles: the ControlNet has no clone on <device>; put MultiGPU_WorkUnits after ClaudeSpotTiles so ComfyUI prepares one per card
- static_split needs at least one device
- device weights must be non-negative numbers with a positive sum (got <weights>)
- unknown balance mode <mode>
- CUEncodePlane needs an RGB canvas plane
- encode_state must be one of <states> (got <value>)
- a canvas plane holds one image
- a canvas plane window narrows rows (2) or columns (3), not <dims>
- CUDecodePlane needs the stage plane folder
- CUDecodePlane role must be creative or structure (got <value>)
- CUDecodePlane decodes one image latent
- CUDecodePlane wrote <n> of <m> rows
- decode tile row <n> needs rows <a>-<b>, over the <m>-row buffer
- a decoded tile of <size> px for a latent tile of <size>
- decode rows <a>-<b> taken out of order (next <n>, released <m>)
- decode rows out of order
- CUCannyPlane needs the stage plane folder
- CUCannyPlane needs an RGB canvas plane
- CUSam3DetectLean needs an RGB input plane
- CUSam3DetectLean needs its plane folder
- the classic node pack in this engine has no lean SAM node (ClaudeSAM3DetectLean)
- the lean SAM node gave masks of <shape>, expected (1, <H>, <W>)
- the banded finish cannot run here (<reason>); the whole finish runs only up to <300> MP
- the banded finish makes the 8-bit product finish only — a reason of the line above
- the G1 table was measured on another environment (<library, processor or capability keys>) — a reason of the line above
- no G1 table — a reason of the line above
- the banded finish is not built in this version; the whole finish runs only up to <300> MP
- this build makes the finish variant bxf-1 only (got <variant>)
- CUFinishBanded: smooth_hi must be > smooth_lo
- the banded finish cannot run on this computer (<reason>), and this plan counted only the banded finish — a plan that counted the banded finish never runs the whole one
- numpy <version> has no <helper>: exact selection cannot use numpy's own arithmetic — a reason of the lines above
- CUFinishBanded: band_gb must be one of <2, 3, 6> GiB (got <value>)
- CUFinishBanded: processes must be one of <1, 2, 4> (got <value>)
- CUFinishBanded: finish_tier must be one of <ladder, bxf, tier3> (got <value>)
- the tile ControlNet hint has no canvas plane beside it (canvas.plane in the stage plane folder), so its memory format cannot be read
- a canvas plane is u8 or f32 (got <type>)

### Engine start and the start-up probe (5.0.2 build wave 2)

Every engine loads both node packs. The engine's start check stays the Classic one, so these lines are written to the Activity log only, and a Classic engine image is never stopped by them. The probe's lines are its error output; this build does not run the probe yet (the app's start-up wiring comes later), and once it does, the app will show its own sentence.

- The Large-image engine parts on <engine> could not be checked: <reason> — (log)
- The engine on <engine> lacks Large-image engine parts; it runs Classic engine images only — (log)
- The Large-image engine parts on <engine> do not take every input its graphs send — (log)
- selfprobe: <reason>; no table was written — the probe's error output, with one of the two reasons that follow
- the self-probe ran out of time after <n> s (limit <limit> s) — a reason of the line above
- the probe needs about <N> GiB at <W> px (<rows> rows), over the cap of <cap> GiB — a reason of the line above
- selfprobe: the probe failed (<error type>: <error>); no table was written
- selfprobe: --width must be a positive number of pixels
- selfprobe: --band-gb must be a registered band budget (2, 3 or 6 GiB)

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
