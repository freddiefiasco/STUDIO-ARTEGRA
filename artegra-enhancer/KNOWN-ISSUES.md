# Alpha limits

- Tested GPU hardware is RTX 5090 32 GB. Other cards remain unqualified; the planner enforces its memory/size limits.
- Fast supports Light/Default, 2×, and the verified size cap. It does not split one image across two GPUs. Faster is disabled.
- Runtime and model downloads require internet access during explicit setup. Models are not bundled; no automatic updates run.
- Model terms differ. The tile model publisher declares the OpenRAIL family without an exact version; its published card and restrictions are shown before download. SAM has custom terms.
- The existing FP16 detailed-preview decoder is recognised and preserved; a new publisher download is FP32. Preview precision differs; the saved-image pipeline is unchanged.
- GPU parity was checked on a representative 768×768 crop, not every image size or GPU tier. No overnight endurance claim is made.
- The build is unsigned. Check the release SHA-256 before running it.
