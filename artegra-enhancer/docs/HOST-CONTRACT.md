# Standalone host contract

- `host.app` owns one local service and all descendants through a Windows Job object. Closing or losing the host ends its owned child processes.
- The host writes a random per-run token file, supplies its PID to the service, then validates the service PID and loopback port from the handshake. Only ports 18950–18969 are accepted.
- QML receives `hostEndpoint` and `hostToken`. It never scans legacy endpoints. JSON requests use a Bearer header; image requests use the same token in their local URL because QML Image cannot attach headers. Token query values are redacted from logs.
- App settings are stored under the standalone organisation/application namespace. No other application's preferences are consulted.
- A second launch signals the first window through a local socket.
- The host owns the frame, folder setup and close handling. Imported components retain the image queue, viewer, controls and activity presentation.
- Demo and smoke modes use a fake engine and separate state. They never imply GPU image validation.
- While the window is open the host keeps a run record, `<state>/run/host.json`: its own process and the desktop launcher that started it, each as PID, creation time and executable path. It is removed on a normal exit.
- The single-instance connection accepts `activate` (bring the window forward) and `quit` (stop and close without a prompt; setup pauses safely and unfinished images resume on the next start).
- `ArtegraEnhancer.exe --quit-running [--state <root>] [--timeout <s>]` sends `quit` and waits for the recorded processes. Only if they do not end does it end the ones whose PID, creation time and path still match; it never looks processes up by name. Exit code 0: nothing of the app is left; 2: something could not be closed.
- `ArtegraEnhancer.exe --uninstall-cleanup [--remove-files] [--remove-settings] [--measure --out <file>] [--state <root>]` removes only app-managed files (see INSTALL.md). Images are never in scope.
- Check for updates: one GET to `https://api.github.com/repos/freddiefiasco/STUDIO-ARTEGRA/releases?per_page=50` with the User-Agent `ArtegraEnhancer/<version>`, only when the person clicks. The newest non-draft `artegra-enhancer-v*` release, pre-releases included, is compared with the running version.
- Redux is the API mode `standard`; Bolt is `fast`. `/api/controls` gives the names people read.

