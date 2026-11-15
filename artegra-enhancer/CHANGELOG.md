# Changelog

## 0.1.0-alpha.4

- Rebuilt Windows installation as a guided app, engine and Standard/Fast setup with one terms review and clear progress.
- Added automatic storage and output locations, computer/space checks, verified downloads, retry/resume and a graphics readiness check.
- Added first-launch recovery and Repair installation; normal use no longer requires terminal commands, runtime folder selection or manually starting the engine.
- Preserved existing settings, enhancement files and output images during upgrades and removal.
- Fixed engine startup in folders containing non-ASCII characters.
- Kept the established image-processing recipes and conservative memory behaviour unchanged.

## 0.1.0-alpha.3

- Added Auto, Original settings and Save GPU memory controls with persistent preferences and safe idle-worker changes.
- Auto selects sequential tile processing and CPU model loading on cards with 24 GB or less. Original tile sizes, model weights and numerical options are retained.
- Qualified the conservative memory-saving path with actual service renders and constrained allocator checks on RTX 5090; other physical GPU models remain unverified.
- Kept the failed smaller-tile experiments and unverified quantized replacements out of the release.

## 0.1.0-alpha.2

- Added first-image RAM/commit checks and safer application memory budgets.
- Added Windows version/native x64 and NVIDIA driver checks, with a documented hardware qualification matrix.
- Improved settings on smaller and scaled displays, installation guidance and software interface rendering fallback.
- Smaller-memory profiles remain withheld after the Minimum candidate failed visual review.

## 0.1.0-alpha.1

- Extracted the Creative Upscaler v5 early preview into a standalone Qt Quick host.
- Preserved Standard and the preview's proven eight-step Fast recipe, including its size and Look restrictions.
- Added separate settings, authenticated local connections and owned-process shutdown.
- Removed private deployment paths and unrelated application integration.
- Added dependency locking, privacy checks, source provenance and packaging scripts.
- Published installer and portable builds with representative reference/runtime parity and installer checks.
