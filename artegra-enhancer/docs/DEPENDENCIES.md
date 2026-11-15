# Dependencies and runtime

The desktop build uses `uv.lock` with exact versions and distribution hashes. Its principal runtime dependencies are official embedded Python 3.13, Qt/PySide6 6.12.0, NumPy and Pillow. Small Windows launchers start the unpacked application with its private interpreter; users do not install Python. Historical packaging tools may remain in the development environment but are not copied into the application. `THIRD-PARTY-NOTICES.txt` is generated from installed package licence files by `tools/generate_notices.py`; it is not a hand-written list of assumed licences.

Qt libraries remain dynamically linked in the portable directory. Replacing them with a compatible build is permitted by the applicable LGPL terms. The complete LGPL and GPL texts are included in `licenses/`. Exact upstream source is available from Qt's public repositories. The application does not include proprietary fonts; bundled fonts carry OFL texts alongside them.

The separate image engine is pinned in `runtime/source-manifest.json` and `runtime/requirements-win.lock`. Its source consists of a public ComfyUI base and the distributed GPL patch, with a complete file-hash manifest. Setup chooses a managed location automatically, or uses the drive selected in the installer, and verifies the source before writing its installation receipt. It does not modify other runtimes.

The isolated runtime installation, exact dependency and licence-file checks, service startup, and selected GPU parity checks passed on a separate Windows node. See VALIDATION.md for scope.

