# Privacy

The app processes images locally and does not upload images, logs or feedback. There is no analytics service and no automatic update check.

**Check for updates** runs only when you choose it. It sends one HTTPS request to api.github.com for the list of Artegra Enhancer releases. The request names the app and its version (for example `ArtegraEnhancer/5.0.0-beta.1`) and carries what any web request carries: your IP address and connection details. It sends no account, token, image, file name, folder, log or identifier. Nothing is downloaded or installed. **Download** opens the release page in your browser.

The host and its service communicate through authenticated loopback connections. Worker connections also bind to loopback. Model and runtime downloads happen during setup or repair, after you start them; publishers receive the normal network information of those downloads.

Local logs can contain file names and other details of jobs. Review logs and remove personal paths before attaching them to a public issue. Never attach credentials, access tokens or client images unless you have permission to share them. The uninstaller can remove the logs when you choose **Also remove settings and logs**.
