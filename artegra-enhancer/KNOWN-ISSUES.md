# Alpha limits

- Physical GPU qualification is RTX 5090 32 GB. Windows 10 and other physical GPU models remain unverified. See [COMPATIBILITY.md](docs/COMPATIBILITY.md).
- The Minimum memory experiment failed visual quality review despite completing. Smaller-memory profiles are withheld pending a verified fix.
- 64 GB system RAM is recommended. The conservative planner needs at least 30 GiB of application memory budget, so 32 GB physical-RAM machines are currently refused even with a large pagefile.
- Fast supports Light/Default, 2×, and the verified size cap. It does not split one image across two GPUs. Faster is disabled.
- Runtime and model downloads require internet access during explicit setup. Models are not bundled; no automatic updates run.
- Model terms differ. The tile model publisher declares the OpenRAIL family without an exact version; its published card and restrictions are shown before download. SAM has custom terms.
- The existing FP16 detailed-preview decoder is recognised and preserved; a new publisher download is FP32. Preview precision differs; the saved-image pipeline is unchanged.
- GPU parity was checked on a representative 768×768 crop, not every image size or GPU tier. No overnight endurance claim is made.
- The build is unsigned. Check the release SHA-256 before running it.
