# Source provenance

The user-selected source is the v5 early preview deployed on 13 November 2026 at 11:09 local time. It was imported from an immutable, allowlisted local snapshot. The original source and preview installation were not edited.

Reference snapshot tree SHA-256:

`cd2fd9c2f7eec3c7347d57afbd5260a1aaf61e4637a7952999fd1ee0763f6342`

The import includes only `engine/`, `service/`, `node_pack/`, the Creative Upscaler QML components, gallery components, and the service entry point. The preview's installed QML overrides for its wrapper, tab and API client were included in the reference. No original application binary, window-frame source or internal history was imported.

`SOURCE-MAP.json` records original and public hashes for each imported path and labels additions. Per-file hashes represent the exact snapshot rather than a moving branch.

Public adaptation removes private paths, comments and historical metadata. The service gets portable configuration, process-ID ownership, an authenticated endpoint and a separate notification identity. The QML API client uses the endpoint supplied by the new host. Preferences use the standalone application's namespace. The host's frame and Settings are new.

The tests compare 184 generated Standard/Fast graph cases to SHA-256 values calculated from the immutable source snapshot, covering all five Looks, four image sizes, chained 4× stages, speed-stack states, Standard pass ordering and Fast preview modes. This is prompt identity evidence, not rendered-pixel identity evidence.

## 5.0.0-beta.1: the final v5

"The final v5" here is version 5 of Studio Artegra's in-house app (its Creative Upscaler tab), the source this standalone is made from; it is not a release of Artegra Enhancer. The Beta takes the final v5's tab, service and finish-time logic (after its four QA and fix rounds, 16 November 2026) through a three-way merge: base = the early preview above, ours = the standalone, theirs = the final v5. A frozen copy of the final v5's in-scope files had the tree hash

`3ccc1ddcfbda32a0a1dcbbe2b0eb389d14a86777f5e9ed643858f862b2e07127`

(SHA-256 over the sorted lines `path NUL sha256 LF` of 136 files under engine/, service/, node_pack/, ui/qml/ and cu_service.py). Of these, 99 needed nothing (the final v5 had not changed them), 21 took the final v5's code with comments removed (the standalone had changed only comments), 2 more merged cleanly, 3 had one conflict each (the old port range and one helper line; the standalone's side was kept) and the window wrapper stayed the standalone's. The final v5's engine and node pack are byte-identical to the early preview, so the standalone's engine and node pack are unchanged. One exception came later (release QA, 18 November 2026): in `node_pack/claude_creative/live.py` the detailed-preview decoder's fallback, a fixed location, is now empty, so without a decoder in the models folder the preview uses the rough picture. SOURCE-MAP marks the file with the beta layer. Saved images do not use that decoder.

The final v5's tab had two more fix rounds after that copy was taken (17 November 2026: the Mode follows a Look, factor or fine-tuning Bolt cannot make; an Undo puts back only each image's own factor; a change made while Bolt's files are checked stays on the waiting images). They changed only `ui/qml/creative/CreativeUpscalerTab.qml` and `ui/qml/creative/CuSettingsPanel.qml`, and came into the Beta by a forward three-way merge (base = the copy above, theirs = the final v5 after the rounds, both with comments removed and the Redux and Bolt names applied; ours = the Beta), which merged without conflicts. The final v5's tree after the rounds is

`5a960d40d4c196e8f4cd4bd7acbeb4ea34c0a7e9e6c4a05e8a05602f01ea7cfc`

(the same 136 files and method). No engine, node pack or service file changed in those rounds.

`SOURCE-MAP.json` records, per file, the final v5's SHA-256 and this release's. The Beta's own changes (the Redux and Bolt names and marks, the two-card Bolt rule, the update check, the uninstaller, the About page and the name) are listed in CHANGELOG.md, with the hardening round's small fixes from a UI/UX audit (modal Settings and About, honest start-up and engine-stopped states, the Save GPU memory retry, track contrast, preferences kept per state folder, the stale close prompt, the Shortcuts list, Windows reduced motion). `tests/test_service_prompt_identity.py` checks that the prompts the service sends for every Look, scale and mode equal the final v5's.

