# Image-processing installation (maintainer reference)

The Windows installer automatically prepares this private, pinned environment and the Standard/Fast models. End users do not run this module, choose a runtime folder or install Python. See [Install Artegra Enhancer](../INSTALL.md).

`host.installation.Installation` owns defaults, consent, hardware/space checks, model acquisition and readiness. `runtime.setup_runtime.install` owns verified runtime acquisition, resumable setup, hidden subprocesses and the final runtime receipt. Both the installer and the app's recovery screen use this shared flow. An interrupted owned installation can be retried; unrelated existing environments are never overwritten.

## Source provenance

Python is the official CPython 3.13.14 Windows x64 embedded distribution. PyTorch is pinned to 2.14.1+cu132 and torchvision to 0.29.1+cu132. Distribution versions and hashes are recorded in `requirements-win.lock`; `constraints-win.txt` records the reference dependency versions, including transformers 5.19.0 and Pillow 12.3.0. Downloads, temporary files and package cache stay on the selected data volume.

ComfyUI uses official commit `3f438ca69f3d0efc5f748de055daeea9ba26ee50` plus the bundled source patch reproducing `bcba14f618eaea6e63dac15d1ef45051945ea54e`. Every resulting source file is verified against `source-manifest.json`. ComfyUI and the patch retain GPL-3.0 terms. Optional SageAttention/xformers backends are not enabled.

Only pinned binary wheels are installed. Setup does not compile native extensions, install drivers, change the pagefile or modify another ComfyUI installation. Model files are acquired directly from their publishers after the consolidated terms are accepted; they are not redistributed inside the installer.

See [release validation](../docs/VALIDATION.md) for actual test scope and [compatibility](../docs/COMPATIBILITY.md) for hardware limits.
