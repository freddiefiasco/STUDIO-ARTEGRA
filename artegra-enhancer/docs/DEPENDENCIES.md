# Dependencies and runtime

The desktop build uses `uv.lock` with exact versions and distribution hashes. Its principal runtime dependencies are Python 3.13, Qt/PySide6 6.12.0, NumPy and Pillow. PyInstaller is a build tool. `THIRD-PARTY-NOTICES.txt` is generated from installed package licence files by `tools/generate_notices.py`; it is not a hand-written list of assumed licences.

Qt libraries remain dynamically linked in the portable directory. Replacing them with a compatible build is permitted by the applicable LGPL terms. The complete LGPL and GPL texts are included in `licenses/`. Exact upstream source is available from Qt's public repositories. The application does not include proprietary fonts; bundled fonts carry OFL texts alongside them.

The separate image engine is pinned in `runtime/source-manifest.json` and `runtime/requirements-win.lock`. Its source consists of a public ComfyUI base and the distributed GPL patch, with a complete file-hash manifest. Setup installs into a new user-selected folder and verifies the source before writing its installation receipt. It does not modify other runtimes.

The runtime has not yet completed an end-to-end clean-machine installation or GPU image qualification. Its dependency lock and source checks establish intended inputs, not demonstrated output parity. Runtime wheel licence inventory must also be reviewed before a fully qualified binary pilot.

