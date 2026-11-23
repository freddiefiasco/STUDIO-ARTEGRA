# Troubleshooting

Find the message you see, then do what the right-hand column says. Messages are quoted as the app shows them; *N* stands for a number and *folder* or *name* for the one in your message. If nothing here helps, [report the problem](#still-stuck).

Two fixes solve most problems:

- **Repair.** **Settings → Repair installation** checks every installed file and downloads anything missing. Running the installer again does the same. Your images and settings are kept.
- **Support details.** **Settings → Save support details** saves a ZIP of the app's logs, with paths, file names and addresses replaced by `<redacted>`. Check it, then attach it to an issue.

## Downloading and opening the installer

| Message | What to do |
| --- | --- |
| Windows protected your PC (SmartScreen) | This Beta is not code-signed. Choose **More info**, check the file name is `ArtegraEnhancer-5.0.1b1-Setup.exe`, then **Run anyway**. To be sure of the file, compare it with `SHA256SUMS.txt` ([how](../INSTALL.md#download-and-check-the-file)). |
| Your browser says the file is not commonly downloaded | Keep the file. Download it only from the Studio Artegra release page. |
| Artegra Enhancer needs Windows 10 22H2, or Windows 11 22H2 or newer. Update Windows, then run setup again. | Install the Windows updates offered in **Settings → Windows Update**, then open the installer again. Windows 11 21H2 must be updated to 22H2 or newer. |

## Installing and setting up

These come from the installer or from the app's own setup page. Your downloaded files are kept in every case: after you fix the cause, choose **Retry**, **Try again** or **Resume setup**, run the installer again, or open the app.

### Your computer

| Message | What to do |
| --- | --- |
| Artegra Enhancer (Beta) needs 64 GB of system memory for normal enhancement. Setup stopped before the large downloads. A larger pagefile does not replace this. | This Beta needs a computer with 64 GB of memory. There is no setting that works around it. |
| Artegra Enhancer needs an NVIDIA RTX card with at least 8 GB of graphics memory and a compatible driver. Install a current NVIDIA Studio driver, then choose Retry. | Check the card in **Task Manager → Performance → GPU**. If it is an RTX card with 8 GB or more, install a current [NVIDIA Studio driver](https://www.nvidia.com/en-us/drivers/), restart Windows and choose **Retry**. |
| An NVIDIA graphics card and driver are required. Install the NVIDIA Studio driver, restart Windows, then choose Retry. | Install the NVIDIA Studio driver for your card, restart Windows, then **Retry**. |
| Windows could not read your NVIDIA graphics card. Update its driver and restart Windows, then choose Retry. | Update the driver, restart Windows, then **Retry**. |
| The graphics-card check did not pass. Install a current NVIDIA Studio driver and restart Windows, then choose Retry. Your downloaded files are saved. | Driver 595 or newer is recommended and 580 is the oldest that works. Update, restart and **Retry**. |
| The graphics-card check took too long. Close other graphics-heavy apps, then choose Retry. | Close 3D apps, games and other AI tools, then **Retry**. |

### Space and location

| Message | What to do |
| --- | --- |
| Setup needs about *N* GB of free space on the selected drive. Free some space, or choose another storage location, then retry. | Free that much space, or run the installer again and choose another drive on the **Installation location** page. |
| There is not enough free space for this model. Free space or choose another drive, then resume. | As above. |
| There is not enough free space to restart this download. | Free some space on the drive that holds the AI files, then retry. |
| Choose a folder on a drive with enough free space, or keep the recommended location. | The folder you chose on the **Installation location** page cannot be used. Choose another, or keep the suggested one. |
| The selected storage drive is unavailable. Reconnect it or choose another location, then Retry. | Reconnect the drive (or the network drive), or choose another location, then **Retry**. |
| This folder belongs to another installation. Choose a different location. | Choose an empty folder, or the folder this copy used before. |
| The installation folder contains a link. Choose another location. | Choose a plain folder, not a link or junction. |
| The existing image-processing installation needs repair. Choose a new installation location. | Choose another folder for the AI files. Your old folder is left as it was. |
| An existing model has different contents. Keep it safe: choose another model folder or move it aside before downloading. | A file with a model's name is not the expected file. Move it out of the folder, or choose another folder. Setup never overwrites it. |
| A model appeared at the destination during setup. It was left untouched. | Something else wrote to the models folder. Close other tools that use it, then retry. |
| Installation files must stay in the application data folder. | Run the installer again and keep the suggested location, or choose another drive on the **Installation location** page. |
| Your licence choice could not be saved. Check the app's settings folder. | The settings folder could not be written. Check the drive has space and that the folder is not read-only. |

### Downloads

| Message | What to do |
| --- | --- |
| Setup could not finish preparing the required files. Check your internet connection and free space, then try again. | Check both, then choose **Retry**. **Cancel** closes setup; open Artegra Enhancer later to continue. |
| Setup could not finish. Your downloaded files are saved. Check your connection and free disk space, then choose Retry. | As above. |
| Setup couldn't finish. Check your connection and free space, then try again. | As above. |
| The connection was interrupted. Reconnecting… | Nothing; setup carries on by itself. |
| The download connection was interrupted. Check your connection, then download again to resume. | Check the connection, then retry. The download resumes where it stopped. |
| The connection ended early. Download again to resume the saved transfer. | Retry. |
| The connection ended early. Retry to continue the download. | Retry. |
| The download did not match the publisher's SHA-256. The incomplete copy was removed; download again. | Retry. If it happens again, a proxy or security tool may be changing downloads: try another network. |
| Runtime download checksum did not match. Setup stopped. | As above. |
| The publisher did not return a model download. Try again later. | The model's publisher is not answering. Try again later. |
| The publisher sent an encoded download. Try again later. | Try again later, or from another network. |
| The publisher returned an invalid resumed download. Your saved transfer is unchanged; try again later. | Try again later. |
| The publisher redirected to an unexpected download location. | Setup only accepts the publisher's own addresses. Try again later, or from another network. |
| The publisher sent more data than expected. No model was installed. | Try again later. |
| The download server did not return an installation file. | Try again later. |
| The download server returned an inconsistent file size. | Try again later. |
| The download exceeded its expected size. | Try again later. |
| The download could not be resumed safely. Please retry installation. | Retry. Setup starts that file again. |
| The model could not be saved. Check free space, folder permissions and drive connection, then resume. | Check those three, then resume. |
| The model file could not be read. Check the folder and drive connection. | Reconnect the drive, then retry. |

### Pauses, terms and other setup windows

| Message | What to do |
| --- | --- |
| Setup is paused. Open Artegra Enhancer or run the installer again to resume. | Open the app or run the installer to continue. Downloads resume. |
| Your setup is paused | The app's setup page after **Pause setup**. Choose **Resume setup**. |
| Setup needs to finish, or Setup is paused (last installer page) | The app is installed but its AI files are not ready. Open Artegra Enhancer to carry on. |
| Review and accept the application and model terms to continue. | Read the terms, tick the box, then continue. |
| Read and accept this model's publisher terms before downloading. | As above. |
| Installation is already running. Wait for the other setup window. | Another setup window is open. Finish or close it. |
| Another model setup is using this folder. Wait for it to finish. | As above. |
| Windows could not complete setup. Close other installations and try again. | Close other installers and Windows Update, then run setup again. |
| Setup could not read its progress. Close setup and open Artegra Enhancer to continue. | Close setup, then open the app; it continues from the files already downloaded. |
| Windows could not start setup. Reopen the installer to repair the application. Your downloaded files have been kept. | Run the installer again. |
| Your previous save location is unavailable. Images will save to Pictures / Artegra Enhancer. | Your earlier output folder could not be found (for example, a drive that is not connected). Choose another in Settings if you want to. |

## Opening the app

| Message | What to do |
| --- | --- |
| Artegra Enhancer could not start. Run the installer again to repair it. Your images and enhancement files are kept. | Run the installer again. |
| Required application files are missing. | Run the installer again. A security tool may have removed a file; check its quarantine. |
| Windows did not start the application. | Restart Windows, then run the installer again. |
| The application window could not load. Details: *log file* | Run the installer again. If that does not help, save support details and report it. |
| The application is already opening. Try again in a moment. | Artegra Enhancer is already starting. Wait, or look for its window on the taskbar. |
| Opening the workspace took too long. Try again, or choose Repair installation. | Choose **Try again**. If it happens again, use **Repair installation**. |
| The image tools aren't installed yet. Complete setup or choose Repair installation. | Finish setup, or use Repair. |
| The image tools aren't set up correctly. Choose Repair installation to restore them. | Use Repair. |
| Some image tools are missing. Choose Repair installation to restore them. | Use Repair. |
| The installation is incomplete. Choose Repair installation to finish it. | Use Repair. |
| The installation needs attention. Choose Repair installation to restore the image tools. | Use Repair. |
| The saved settings could not be read. Choose Repair installation to restore them. | Use Repair. Your images are not affected. |
| Artegra Enhancer installation is incomplete. Open setup to continue. | Open the app from the Start menu to finish setup. |
| The image engine is not running | The engine stopped. Choose **Try again**. Unfinished images carry on when it starts. If it keeps stopping, use **Repair installation** on the same page. |
| The image engine stopped unexpectedly. Choose Try again to start it. | Choose **Try again**. |
| The engine could not start. Open Settings to check your folders, then try again. | Check the output folder in Settings exists and can be written, then choose **Try again**. |
| The engine did not start. Open Settings to check your folders, then try again. | As above. |
| The connection to the engine was lost and it has not come back. Choose Try again; if it keeps happening, restart Artegra Enhancer. | Choose **Try again**, or close and reopen the app. |
| Images cannot be added while the engine has a problem. | Choose **Try again** first. |
| Images cannot be added yet. Try again in a moment. | The engine is still starting. Wait a few seconds. |

The portable ZIP's window does not open at all when it is extracted under a long folder path. Extract it to a short folder on a local drive, for example a folder named ArtegraEnhancer at the top of drive C.

## Enhancing images

### Memory

| Message | What to do |
| --- | --- |
| The graphics card ran out of memory. Close other programs that use it, then try again. | Choose **Try again with Save GPU memory** if it is offered, or close 3D apps, games and other AI tools and try again. |
| The graphics card ran out of memory. Try a smaller upscale, or close other programs that use it. | Try a smaller scale, turn on Save GPU memory, or close other programs that use the card. |
| GPU *N* ran out of memory. … | The same, for one of two cards. |
| Try again with Save GPU memory? | Choose **Turn on and try again**. Save GPU memory then stays on for later images, which can take longer; you can turn it off in Settings. |
| Save GPU memory could not be turned on. | It can only change while no image is working. Wait for the batch to finish, then turn it on in Settings. |
| The engine ran out of system memory (limit *N* GB). Close other programs, then try again. | Close other large programs. If it happens with nothing else open, try a smaller scale. |
| Waiting for memory: another image is using the memory this one needs. It starts when that one finishes. | Nothing; it starts on its own. |
| Waiting for memory: this image needs more memory than the app may use now. Queue it again at a smaller upscale. | Remove it and queue it again at a smaller scale. |
| Waiting for memory: close other memory-heavy apps to free system RAM. | Close 3D apps, renderers and other large programs; the image starts when enough memory is free. |
| Waiting for memory: Windows has insufficient commit headroom. Close other apps or enable a system-managed pagefile on a drive with free space. | Close other large programs. If the image still waits, open **Settings → System → About → Advanced system settings**, choose **Settings** under Performance, then **Advanced → Change** under Virtual memory, and turn on **Automatically manage paging file size for all drives** (or select a drive with free space, choose **System managed size** and **Set**). Choose **OK**, and restart Windows if it asks. |
| This upscale would need about *N* GB of memory, more than the *M* GB the app may use. Choose a smaller upscale or a smaller image. | Choose a smaller scale. The [known issues](../KNOWN-ISSUES.md) list the upscales a 64 GB PC refuses and a 128 GB PC runs. |
| Uses a lighter setting to fit this computer's memory. | Nothing; the image is made at the size you chose. For the full setting, make it on a computer with more memory. |

### Image size and scale

| Message | What to do |
| --- | --- |
| This image is very large (*N* MP). Images up to 80 MP are supported. | Reduce the image to 80 MP or less before adding it. |
| The largest supported output is about 150 MP. | Choose a smaller scale. |
| Too large at every scale, or Fits at *N*× | The image can only go up to the scale shown, or not at all. |
| *N*× is too large for every image in the list. | Choose a smaller scale. |
| Pass *N* of *N* is larger than the engine can take, so this image was not finished. Choose a smaller upscale for it. | Queue it again at a smaller scale. |

### Bolt

| Message | What to do |
| --- | --- |
| Bolt upscales 2× only. Choose Redux for 4× and above. | Use Redux, or 2×. |
| Bolt offers Light and Default only. Choose Redux for Strong, Heavy, Extreme or Custom. | Use Redux, or Light or Default. |
| Bolt works on images up to about 9 MP. Choose Redux for larger images. | Use Redux for that image. |
| Bolt needs more memory for this image than this computer has. Choose Redux, which uses a lighter setting to fit. | Use Redux for that image. |
| Bolt needs more memory for this image than this computer has. | Redux cannot fit it at this scale either. Use a computer with more memory, or a smaller image. |
| This image is too large for Bolt, so it was not upscaled. Queue it again in Redux. | Choose **Try again in Redux** on the image. |
| Bolt is not ready yet: its files are still being checked. Try again in a moment. | Wait a few seconds; the Mode shows Redux until the check is done. |
| Bolt cannot be used: a file it needs cannot be read | Use **Repair installation**. |
| Mode set to Redux: Bolt cannot be used now | As above. |
| Mode set to Redux, with a reason such as "4× and above are Redux only." | You chose a setting only Redux can do, so the Mode changed. To use Bolt, choose 2× and Light or Default, then choose Bolt. |

<!-- release-draft: engines. Kept, changed or removed by the release step from the proof record. -->

### The Large-image engine

| Message | What to do |
|---|---|
| The Large-image engine is not installed correctly, so this image was not upscaled. Choose Repair installation in Settings. | Choose **Repair installation** in Settings, then queue the image again. |
| The work files for this image are missing. Add the image again and start a new upscale. | Something removed the work files while the image waited. Add the image again. |
| The Large-image engine could not be restarted for the last step of this pass. | Choose **Try again**. If it happens again, restart the app and queue the image again. |
| The finished image is missing or damaged in the work folder, so it could not be saved. | Check that the work drive has the free space the plan asked for, then queue the image again. |

**The first Large-image image waits before it starts.** Unless your kind of processor was measured before this release, the app first measures how your computer's processor runs the Large-image engine's finish, and the image waits while it does. On our test PC's processor this took about 22 to 25 minutes; on a slower processor it takes longer. Leave the app open until it finishes. If it cannot finish, the largest Large-image sizes are refused and the refusal says that the processor has not been measured: choose a smaller upscale, and if it happens again, [report the problem](#still-stuck) with the support details.

**A Large-image upscale restarts the image engine between passes.** This gives back the memory the last pass held before the next pass starts. The estimated time in the plan counts each restart, so nothing needs doing.

<!-- /release-draft -->

### The engine

| Message | What to do |
| --- | --- |
| The engine is missing a part it needs (model or plug-in). Details are in the log. | Use **Repair installation**. |
| The engine could not accept pass *N* of *N*: it is missing a part it needs (model or plug-in). Details are in the log. | Use **Repair installation**. |
| The engine stopped with an error. Details are in the log. | Queue the image again. If it fails again, save support details and report it. |
| The engine stopped unexpectedly. / The engine stopped on this image. | As above. |
| The engine did not answer in time. It may be busy; the tab will keep trying. | Wait; it usually recovers. |
| The connection to the engine was lost. Try again in a moment. | Wait a moment, then repeat what you did. |
| The engine did not accept the request. Try again, or copy the details. | Try again. If it repeats, save support details and report it. |
| The images could not be added. / The upscale could not start. / The images could not be queued. | Try again in a moment. If it repeats, restart the app. |

## Saving results

| Message | What to do |
| --- | --- |
| This folder cannot be written to. Choose another folder. | Choose a folder you can write to in **Settings → Save enhanced images to** or under **Output**. |
| Choose an output folder. | As above. |
| The output folder isn't available. Choose another save location in Settings. | Reconnect the drive, or choose another folder. |
| Not enough free space in *folder*: needs about *N* GB, *N* GB free. | Free space there, or choose another output folder. |
| Not enough free disk space for the work files: needs about *N* GB, *N* GB free. Free some space and start again. | Free at least the amount named, then start again. |
| Saved; waiting for the output folder to write the recipe file | The output folder is slow (often a network drive). Leave the app open; it keeps trying. |
| Still waiting for the output folder after *N* min | As above. Check the network drive is still connected. |
| The finished image is missing from the work folder, so it could not be saved. | Queue the image again. A security tool may have removed the file. |
| The app could not save its job list. Free some space on drive C: or restart the app. | Free some space on the system drive, then restart the app. |
| transparency not kept in JPEG | JPEG has no transparency. Choose PNG or TIFF under **Output** to keep it. |

## Updates, uninstalling and support details

| Message | What to do |
| --- | --- |
| Couldn't reach GitHub. Check your connection and try again. | Check the connection, then choose **Check for updates** again. A firewall or proxy may block api.github.com. You can also look at the [releases page](https://github.com/freddiefiasco/STUDIO-ARTEGRA/releases) in your browser. |
| Uninstall works in an installed copy. Use Installed apps in Windows Settings. | This copy came from the portable ZIP: delete its folder to remove it. |
| The uninstaller could not start. Use Installed apps in Windows Settings to remove the app. | Uninstall from **Windows Settings → Apps → Installed apps**. |
| Finish or cancel the current image work first. | Wait for the batch to end, or cancel it, then uninstall. |
| Artegra Enhancer (Beta) is still running. Close it, then try again. | Close the app, then start the uninstaller again. |
| The diagnostic bundle could not be saved. Choose a writable folder and try again. | Save it somewhere else, such as Documents. |
| Could not open the log folder. | Open `%LOCALAPPDATA%\Studio Artegra\Artegra Enhancer\production` in Explorer. |

## Still stuck

1. Use **Settings → Save support details** and open the ZIP to check what it holds.
2. [Open an issue](https://github.com/freddiefiasco/STUDIO-ARTEGRA/issues/new/choose) with the app version (in **About**), your Windows version, graphics card and driver, the mode, the image size and the steps that lead to the problem.
3. Attach the support ZIP. Do not attach client images; a synthetic example is enough.

Known limits that are not errors are listed in [KNOWN-ISSUES.md](../KNOWN-ISSUES.md).
