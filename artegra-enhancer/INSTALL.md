# Install and run

This is a developer preview. A clean-machine installer qualification has not yet been completed.

1. Extract the portable application, or run the per-user installer when a qualified artifact is provided. No model weights are bundled.
2. Prepare a separate runtime with `SetupRuntime.exe` or the source runtime setup command. This downloads Python, pinned engine dependencies and ComfyUI from their publishers. Setup requires an internet connection and enough free disk space. It does not modify other engine installations.
3. In Settings, choose a Models folder and open **Set up or verify models**. Review the Publisher, Terms and Saved terms for each selected model, accept each individually, then choose **Download selected**. Standard requires five files; Fast adds its LoRA. You can pause and resume. Existing matching models are retained; different files are never overwritten. **Verify existing files** performs no download. Read [MODEL-LICENSES.md](MODEL-LICENSES.md), including the disclosed TTPlanet licence uncertainty.
4. Open Artegra Enhancer. In Settings, choose the runtime, models and output folders, then start the engine.
5. Add an image, choose Standard or Fast, and upscale. Fast requires its exact eight-step LoRA and accepts only Light or Default at 2×.

The runtime setup will stop rather than substitute an unavailable pinned component. A setup failure is not a completed installation.

Application settings and job state are stored beneath the current user's local application-data folder, under `Studio Artegra/Artegra Enhancer`. Output images go to the selected output folder. Closing the application ends its owned service and workers.

To remove a portable copy, close the app and remove its extracted folder. The installer removes its installed files. Keep or remove application state separately. Model folders and output images are not removed by uninstall.

Unsigned preview builds may display a Windows warning. Check the artifact's SHA-256 against the published checksum before deciding whether to run it. No certificate or administrator password is required by the per-user installer.


Model setup downloads from the named publishers, including their official file-delivery hosts. It does not upload images or collect publisher account credentials. Licence links open only when requested. Six Standard/Fast files use about 13.77 GiB; reserve additional space for the runtime and outputs. Saved publisher terms are available offline in `licenses/models`.

To report a problem, use **Save diagnostic bundle** in Settings. Review the resulting ZIP before sharing it; the app does not upload it.
