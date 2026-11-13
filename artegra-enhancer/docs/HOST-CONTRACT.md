# Standalone host contract

- `host.app` owns one local service and all descendants through a Windows Job object. Closing or losing the host ends its owned child processes.
- The host writes a random per-run token file, supplies its PID to the service, then validates the service PID and loopback port from the handshake. Only ports 18950–18969 are accepted.
- QML receives `hostEndpoint` and `hostToken`. It never scans legacy endpoints. JSON requests use a Bearer header; image requests use the same token in their local URL because QML Image cannot attach headers. Token query values are redacted from logs.
- App settings are stored under the standalone organisation/application namespace. No other application's preferences are consulted.
- A second launch signals the first window through a local socket.
- The host owns the frame, folder setup and close handling. Imported components retain the image queue, viewer, controls and activity presentation.
- Demo and smoke modes use a fake engine and separate state. They never imply GPU image validation.

