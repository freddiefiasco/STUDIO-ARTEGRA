# Beta limits

- Physical GPU qualification is RTX 5090 32 GB. Windows 10 and other physical GPU models are unverified. See [COMPATIBILITY.md](docs/COMPATIBILITY.md).
- Bolt supports Light and Default at 2×, for images up to about 9 MP. A single Bolt image shares two cards only on two identical desktop RTX 5090 cards with the original memory settings. "Speed up upscaling" (Faster) stays off.
- Redux can share one image across two cards of any kind, as in the alphas. That was proven on two RTX 5090 cards only; mixed or other cards are unverified.
- A two-card Bolt image could not be re-run for this beta (the test machines have one card each). Its code and prompts are the same as the final v5's, which was proven on two RTX 5090 cards.
- From the final v5 (planned for the next version): if Bolt is requested in the first seconds while its files are still being checked, the request can wait up to 20 seconds; a live preview that reconnects mid-pass loses that pass's name; the remaining time of an image shared by two cards is covered by unit tests only; the first answer for a Bolt batch can show the two-card figure.
- The Beta needs 64 GB of system memory. The planner needs at least 30 GiB of application memory, so 32 GB machines are refused even with a large pagefile.
- Save GPU memory keeps the original tile sizes and numerical options; selected outputs passed visual review but are not pixel-identical to the original settings.
- The installer downloads the required software and models after you accept the terms; the first installation needs internet access. Models are not bundled. Updates are never downloaded or installed automatically.
- Going back from the Beta to an alpha (installing an alpha over it) is not supported.
- The uninstaller's options page and its single confirmation are written for Inno Setup but were not yet run on a test machine for this build; see [VALIDATION.md](docs/VALIDATION.md).
- If you saved images inside the app's image engine folder, **Also remove downloaded enhancement files** keeps them and that folder. Move them out before you install again: setup can refuse an image engine folder that holds other files.
- Model terms differ. The tile model publisher declares the OpenRAIL family without an exact version; its card and restrictions are shown before download. SAM has custom terms.
- The existing FP16 detailed-preview decoder is recognised and kept; a new publisher download is FP32. Preview precision differs; the saved-image pipeline is unchanged.
- The build is unsigned, so Windows may show a publisher or reputation warning. Download it from the linked Studio Artegra GitHub release. Checksums are supplied.
