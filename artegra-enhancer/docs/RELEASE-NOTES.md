# Artegra Enhancer 0.1.0-alpha.1

Standalone Creative Upscaler based on the v5 early preview, including Standard and Fast modes.

## Included

- Existing Creative Upscaler controls, queue and viewer in a standalone Qt Quick host.
- Standard and the eight-step Fast recipe. Fast supports Light/Default, 2×, within its size cap, one GPU per image.
- Separate local settings, authenticated loopback connections and owned-process cleanup.
- Unsigned per-user Windows installer, portable ZIP, runtime setup tool, checksums and build-environment SBOM.

## Validation

252 CPU tests and 33 subtests passed. All 184 Standard/Fast prompt identity cases match the source preview. Frozen host smoke and install/uninstall smoke passed, including an installation path containing spaces and a non-ASCII character. No GPU was used in those smoke tests. Source and packaged-code privacy scans passed.

## Not yet qualified

Actual rendered-pixel comparison, full clean-account runtime installation, network capture and long-batch endurance remain outstanding. Automatic model acquisition is disabled pending licence review; weights are not bundled. The optional detailed-preview decoder differs in precision from the publisher file. This binary draft is not a supported public pilot release.

## Not included

Other image-enhancement products or features, Faster, single-image Fast sharing across GPUs, automatic updates, automatic uploads, bundled models or certification of untested GPUs.
