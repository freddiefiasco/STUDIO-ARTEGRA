# Separate image-engine runtime

The app and installer never download a runtime or models automatically.
The standalone app can open its demo without this runtime. Production setup is
experimental; full GPU and image-output validation remains outstanding.

To explicitly install the pinned runtime from a terminal, choose a **new** folder:

```powershell
.\SetupRuntime.exe --install --directory "$env:LOCALAPPDATA\ArtegraEnhancerRuntime"
```

From a source checkout, the equivalent command is:

```powershell
python -m runtime.setup_runtime --install --directory "$env:LOCALAPPDATA\ArtegraEnhancerRuntime"
```

Setup refuses every existing destination, including an empty directory. It does
not discover, upgrade, alter, or reuse another ComfyUI environment. It downloads
several gigabytes from official Python, PyPI and PyTorch sources, verifies pinned
hashes, and writes `runtime-receipt.json` only after installation and version checks
complete. An interrupted setup leaves `SETUP-INCOMPLETE.txt`; remove that newly
created folder yourself before retrying. No models are bundled or downloaded.
Choose the completed runtime folder, an existing model folder and an output folder
in the app. Do not copy model files into the application installation directory.

## Source provenance

Python is the official CPython 3.13.14 Windows x64 embedded distribution. PyTorch
is exactly 2.14.1+cu132, with torchvision 0.29.1+cu132 from the official cu132 index.
All dependency versions and distribution hashes are recorded in
`requirements-win.lock`. The lock was resolved for Windows x64 / Python 3.13;
the entire resolved dependency closure matches the verified reference runtime.
`constraints-win.txt` records those reference versions, including transformers
5.19.0 and Pillow 12.3.0. Large downloads, temporary files and the pip cache stay
on the chosen runtime volume.

ComfyUI source is the official `Comfy-Org/ComfyUI` v0.42.4 commit
`3f438ca69f3d0efc5f748de055daeea9ba26ee50`, plus the bundled plain source patch.
The patched source reproduces commit `bcba14f618eaea6e63dac15d1ef45051945ea54e`.
The patch includes the top-p threshold correction, CLIP device retarget correction,
and SageAttention3 option and eligibility logic. Every resulting file is checked
against the Git blob hashes in `source-manifest.json` (1,311 files). ComfyUI and
the patch are GPL-3.0; see the included license notices. The full source revision
is preserved even though this app does not enable the optional SageAttention backends.

The setup program installs wheels only and does not build native extensions.
The lock excludes optional SageAttention/xformers additions, drivers and models.
Fresh Windows installation, all 86 pinned dependency versions, dependency
consistency, and a CPU-only local-server startup have been verified. GPU output
quality and compatibility are qualified separately; these setup checks do not
claim GPU compatibility.
