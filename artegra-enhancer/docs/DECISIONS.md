# Release decisions

## 13 November 2026

- Build from the existing implementation and publish a pruned standalone source repository on GitHub.
- The final source selection is the v5 early preview, with Fast enabled. It supersedes the earlier selection of v4.
- Keep Standard's image graph and the selected Fast recipe intact. Do not enable single-image Fast splitting or Faster.
- Use a fresh Qt Quick host and separate per-user settings and authenticated local service.
- Publish source with fresh history. Do not carry internal history, deployment scripts, private records or model weights.
- Retain ownership of project code while identifying the GPL node package and third-party components separately.
- Leave model auto-download disabled until the outstanding model-licence questions are resolved.
- Qualifying the binary release and the final tester terms remain outstanding. Source publication does not assert completion of those gates.

## 17 November 2026: 5.0.0-beta.1

- The product becomes Artegra Enhancer (Beta), version 5.0.0-beta.1. The internal names that set the state folder and the settings namespace stay, so an alpha upgrades in place.
- The latest enhancement tab, service and finish-time logic from Studio Artegra's in-house app (its v5) are merged into the standalone with a three-way merge (base: the early v5 preview). The standalone's host contract, memory profiles and privacy scrub are kept. The engine and node pack are unchanged because the in-house v5 did not change them (one later exception: see 18 November).
- Standard is renamed Redux and Fast is renamed Bolt wherever a person reads them. Redux is the API mode `standard`; Bolt is `fast`. The engine keeps its own labels; the service gives the new ones.
- A single Bolt image shares two cards only on the proven hardware: two identical desktop RTX 5090 cards with the original memory settings.
- Check for updates is manual only. There is no background check.
- The installer registers an uninstaller with two optional clean-up choices, both off by default. Images are never in scope. Removing settings and logs works from a list of the app's own entries, not by removing everything except the known output folder, because an output folder can be any writable folder, including one inside the app's state folder. The app's own folders (media, work, workers) hold the app's own copies and previews, so they are not kept just for holding pictures; they are kept when a record names an output folder in them or when they hold a file named like a result. Removing the downloaded files works the same way in the managed engine folder, because a person can save there too (its ComfyUI output folder, or any folder inside the data folder chosen at setup). Only setup's own entries are removed, by exact name. The app never writes in the engine's ComfyUI folder after setup, so its exact file list is known: only files that match the pinned source byte for byte are removed, and an image there stays even when no record names its folder. The output folders are read once, before either option runs. The consent files (LICENSE.txt and the model manifest) are unchanged so the upgrade needs no new consent.
- The pilot notice becomes the beta notice, marked as a draft for legal review.

## 17 November 2026: hardening from a UI/UX audit

Max: a polish pass, not a rebuild; comprehensive amends wait for a later version. Each audit item was placed in one of three groups: fixed here, a known issue, or a later version. Only small, local fixes to defects a colleague could hit were made.

- Settings and About are made modal by hiding the workspace while they are up, not by a new dialog. The tab already gates every shortcut, key handler and timer on its own visibility, because the internal app hides it behind other pages, so no tab code changed for this. Hiding alone left the keyboard on a control clicked before the page opened (Qt keeps focus on a hidden item), so the page on screen takes the keyboard as it appears, and focus that lands in the hidden workspace later goes to the page. The workspace is not disabled instead: a disabled white block is not drawn, so it would fade back in each time a page closes. When the engine stops, a question the workspace had open is closed with its safe answer.
- Start-up and an engine stop keep the existing setup page but show only what is true: no install steps, no setup note, and no progress bar without a real fraction. Opening straight into the workspace and restarting the engine by itself are left for a later version.
- After an out-of-memory failure the retry offers Save GPU memory, the memory setting the app already has, only when the failed card does not use it yet and no other image is working (the engine refuses the change then). Because it is a setting for every later image, and on two RTX 5090 cards it also ends two-card Bolt, it is asked first and stays visible in Settings.
- Contrast is fixed where a token value can do it: the slider and progress tracks. The chosen and selected states cannot be fixed by a token value without dropping the secondary text on them below 4.5:1, so they wait for a new state mark in a later version.
- The UI keeps Helvetica Neue by family name with the bundled Instrument Sans as the fallback (the studio's brand rule). Whether to set the UI in one bundled family everywhere is left to Max for a later version.
- The tab's preferences move from the registry into each state folder's preferences.ini, once, on the first start of an installed copy; demo never reads or writes the registry's.

## 18 November 2026: release QA fixes

- A ported test named a folder at a private network location. The beta's commits had not been pushed, so the test was changed in the commit that added it and the later commits were replayed; no commit to be published carries the path. The public-content scan now refuses network paths and private server and folder names.
- The node pack's live preview fell back to a fixed location for its decoder when the models folder had none. That fallback is now empty: the preview uses the rough picture. This is the node pack's only change; saved images do not use that decoder.
- The SBOM describes the shipped package, not the build environment.

