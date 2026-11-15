# Alpha limits

- Physical GPU qualification is RTX 5090 32 GB. Smaller-card profiles are compatibility candidates; Windows 10 and other physical GPU models remain unverified. See [COMPATIBILITY.md](docs/COMPATIBILITY.md).
- 64 GB system RAM is recommended. The conservative planner needs at least 30 GiB of application memory budget, so 32 GB physical-RAM machines are currently refused even with a large pagefile.
- Low-memory profiles can change output pixels and may be slower. Large full-image preprocessing buffers can still exhaust VRAM; tile size is not a guarantee that every image fits.
- Fast supports Light/Default, 2Ã—, and the verified size cap. It does not split one image across two GPUs. Faster is disabled.
- Runtime and model downloads require internet access during explicit setup. Models are not bundled; no automatic updates run.
- Model terms differ. The tile model publisher declares the OpenRAIL family without an exact version; its published card and restrictions are shown before download. SAM has custom terms.
- The existing FP16 detailed-preview decoder is recognised and preserved; a new publisher download is FP32. Preview precision differs; the saved-image pipeline is unchanged.
- GPU parity was checked on a representative 768Ã—768 crop, not every image size or GPU tier. No overnight endurance claim is made.
- The build is unsigned. Check the release SHA-256 before running it.
