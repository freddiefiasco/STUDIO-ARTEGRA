# Source provenance

The user-selected source is the v5 early preview deployed on 13 November 2026 at 11:09 local time. It was imported from an immutable, allowlisted local snapshot. The original source and preview installation were not edited.

Reference snapshot tree SHA-256:

`cd2fd9c2f7eec3c7347d57afbd5260a1aaf61e4637a7952999fd1ee0763f6342`

The import includes only `engine/`, `service/`, `node_pack/`, the Creative Upscaler QML components, gallery components, and the service entry point. The preview's installed QML overrides for its wrapper, tab and API client were included in the reference. No original application binary, window-frame source or internal history was imported.

`SOURCE-MAP.json` records original and public hashes for each imported path and labels additions. Per-file hashes represent the exact snapshot rather than a moving branch.

Public adaptation removes private paths, comments and historical metadata. The service gets portable configuration, process-ID ownership, an authenticated endpoint and a separate notification identity. The QML API client uses the endpoint supplied by the new host. Preferences use the standalone application's namespace. The host's frame and Settings are new.

The tests compare 184 generated Standard/Fast graph cases to SHA-256 values calculated from the immutable source snapshot, covering all five Looks, four image sizes, chained 4× stages, speed-stack states, Standard pass ordering and Fast preview modes. This is prompt identity evidence, not rendered-pixel identity evidence.

