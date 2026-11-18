# Privacy

The app processes images locally and does not upload images, logs or feedback. There is no analytics service and no automatic update check.

## When the app goes online

- **Setup and Repair** download the image engine and the models directly from their publishers, after you start them and accept the terms. The publishers receive the normal network information of those downloads: your IP address and connection details.
- **Check for updates** runs only when you choose it. It sends one HTTPS request to api.github.com for the list of Artegra Enhancer releases. The request names the app and its version (for example `ArtegraEnhancer/5.0.0-beta.1`) and carries what any web request carries: your IP address and connection details. It sends no account, token, image, file name, folder, log or identifier. Nothing is downloaded or installed. **Download** opens the release page in your browser.
- **Release notes**, **Source on GitHub** and **Download** open pages in your browser. The app itself sends nothing with them.

The app and its image engine talk to each other through authenticated connections on your own computer only (loopback), and the engine's workers also listen on loopback only.

## What the app keeps on your computer

Each enhanced image has a .json file beside it, named after it. It records the settings used, when the image was made, the checksums of the original and the enhanced image, and their full paths, which usually include your Windows user name. The app never sends it anywhere. Remove these files before you send a folder to anyone. An enhanced image also keeps the details embedded in the original (EXIF), including any location, so check those too.

Local logs can contain file names and other details of jobs. The uninstaller removes them when you choose **Also remove settings and logs**.

## Support details

**Settings → Save support details** saves a ZIP file where you choose. It holds the app's own logs and settings only, never images, and replaces paths, file names, addresses and anything that looks like a token or password with `<redacted>`. Nothing is uploaded: you decide whether to attach it to an issue. Open it and check it before you share it.

Review any log excerpt before you post it in a public issue, and remove personal paths. Never attach credentials, access tokens or client images unless you have permission to share them.
