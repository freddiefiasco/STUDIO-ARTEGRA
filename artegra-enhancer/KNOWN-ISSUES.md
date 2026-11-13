# Known issues

- This standalone package has not completed rendered-pixel comparison, a clean-account install/uninstall cycle, long-batch endurance, or network-capture qualification.
- Fast uses one GPU per image. Two-GPU splitting for a single Fast image is disabled in the source preview.
- Automatic model downloads are disabled. The exact terms for the tile ControlNet remain unresolved; SAM has custom licence conditions.
- The runtime is large and downloads separately. Setup fails if any exact upstream version is unavailable.
- GPU support beyond the reference RTX 5090 is unqualified. The inherited size limits do not establish support for every GPU.
- The standalone frame and settings differ from the original host. The Creative Upscaler controls and generated image workflows are preserved.
- No automatic updates, telemetry or image uploads are implemented.

