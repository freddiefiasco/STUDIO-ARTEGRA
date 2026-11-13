# Artegra Enhancer 0.1.0-alpha.1

A standalone, pruned Windows build of the v5 Creative Upscaler, with Standard and Fast modes.

Includes the existing controls, queue and viewer; a separate application host; authenticated local connections; owned-process shutdown; explicit runtime setup; per-model terms and resumable verified downloads; and redacted diagnostic export.

Selected Standard/Fast outputs and the freshly installed runtime matched the reference at zero differing pixels. Remote automated, recovery, packaging and cleanup checks passed. The validation report records the scope.

Fast supports Light/Default at 2× within its size cap and uses one GPU per image. Faster, single-image Fast splitting, automatic updates and uploads are not included. Tested hardware is RTX 5090 32 GB; other hardware remains unqualified.

Models download from publishers after acceptance of their individual terms; no weights are bundled. This is an unsigned alpha: verify the published SHA-256 and review output before production use.
