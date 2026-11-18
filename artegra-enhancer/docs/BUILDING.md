# Building a Windows release

This page is for maintainers. End users open the release installer; Python,
compiler tools and terminal commands are not part of installation.

Use Windows x64, Python 3.13, the exact dependencies in `uv.lock`, the Windows
.NET Framework C# compiler, and Inno Setup 7.1 or newer (alpha 4 and the Beta used Inno
Setup 7.1.1; the uninstall options form uses Inno Setup 7's `CreateCustomForm`). `host/config.py` VERSION (`5.0.0-beta.1`) and `pyproject.toml` (`5.0.0b1`)
must name the same release; the build checks this and passes the display version
to the installer and the PEP 440 version to the file names. Run the tests and public-content checks before building:

```text
python -m pytest -q
python tools/public_scan.py
python tools/build_release.py --installer
```

The public-content scan checks the studio's private words only where `.local/private-terms.txt` is present (one word
per line; git ignores `.local/`). Without it the scan runs its generic checks and says so. Run it with the file in
place before a release.

## Distribution layout

The Windows entry points are small, readable C# launchers compiled from
`installer/launcher.cs`. They start the official CPython embeddable distribution
and ordinary unpacked application files. The desktop entry point opens no
terminal. The internal setup helper forwards progress into the installer and
returns its worker's exit code. The Windows-supplied .NET Framework supports the
launchers; no separate .NET download is required on the supported Windows builds.

The desktop runtime uses the same Python 3.13.14 publisher archive and SHA-256
pin as `runtime/setup_runtime.py`. Its executable and DLL files are copied from
that verified archive without modification, and its Python licence is retained.
A local `._pth` file restricts imports to this runtime, the bundled packages and
the application directory. Launchers use isolated Python with explicit UTF-8,
without importing a user's Python installation or startup customisations.

The build copies PySide6, PySide6-Essentials, PySide6-Addons, shiboken6, NumPy and
Pillow from the locked environment, checks their versions against `uv.lock`,
and verifies copied files against their wheel RECORD hashes. Qt and the numeric
libraries remain normal replaceable DLLs. Unused WebEngine and PDF distributions
and development entry-point scripts are not included. Wheel licence files and
package metadata are retained; existing third-party notices are also included.

Before importing PyTorch, engine validation, graphics checks and the image worker
register the packaged shiboken6 DLL directory through `os.add_dll_directory`.
The process retains that directory handle. This supplies its bundled Microsoft
runtime libraries without depending on a machine-wide developer installation;
source checkouts without the desktop package retain their normal environment.

`PACKAGE-PROVENANCE.json` records the Python archive pin, included distributions,
launcher source and compiler hashes, and launcher hashes. The SBOM describes the
package: Artegra Enhancer (Beta) as its root component, the GPL node pack, the
Python distributions unpacked into the desktop runtime (the build stops if they
differ from the provenance record), the CPython embeddable runtime and the
bundled font files. Build and test tools are not listed because they are not
shipped. The image engine that setup downloads is pinned by
`runtime/source-manifest.json`, not by the SBOM. Model weights are downloaded from
their publishers after consent, never included in the release archives.

There is no PyInstaller bootloader or executable archive in this packaging.
Earlier unpublished candidates using both distributed and locally compiled
PyInstaller launchers passed static scans but were quarantined during worker
startup. They are not release candidates. The generated output folder is
replaced as a whole; its previous contents are retained under the private build
folder, preventing old bundle files from leaking into a new package.

## Release checks

Scan the complete app tree and final installer with current Windows protection
enabled, then test installation, first launch, a real image, upgrade and removal.
A clean static scan alone is insufficient. Do not add exclusions or ask users to
disable protection. Source provenance and code signing do not constitute
antivirus clearance. Record final-artifact checks in `VALIDATION.md`.

Publish the installer, portable ZIP, SBOM and SHA-256 checksums together.
Verify that the downloaded public installer matches the tested artifact.
This beta is unsigned; a publisher-reputation prompt can still occur.

## Icon

`installer/ArtegraEnhancer.ico` is rendered from the brand kit's white brandmark on the app's ink colour by
`python tools/make_icon.py` and pinned in `asset-hashes.json`. Both launchers are compiled with it (`/win32icon`),
so the app, its shortcuts and Installed apps show it.

## README and guide images

The banner, the two mode marks and the app screens in `docs/assets` are made by `python -B docs/assets/make_assets.py`
(`graphics` or `screens` for one part). It draws offscreen, so no window opens. The screens come from the app in demo
mode, with synthetic test pictures the script draws and a neutral output folder label, so they show no user name,
folder or client image. Pass `--texts <folder>` to save the words each screen shows, and check every image for
private text before publishing. The script pins every PNG in `asset-hashes.json`. `docs/` ships in the installer
and the ZIP, so rebuild the release after regenerating the images.

## Uninstaller

The installer registers Inno Setup's uninstaller under the same AppId. Windows (or **Settings → Uninstall**, which
starts it with `/SILENT /ASKOPTIONS=1` after its own confirmation) asks once, then shows the two clean-up choices,
then runs `ArtegraEnhancer.exe --quit-running` and, before the app's files are removed,
`ArtegraEnhancer.exe --uninstall-cleanup` with the chosen options. Silent switches: `/VERYSILENT` or `/SILENT`
keep everything optional; add `/REMOVEFILES=1` and `/REMOVESETTINGS=1` to remove them. The state folder chosen at
install time (`/STATE=`) is saved as previous data (`StateDirectory`) and read back by the uninstaller.

The uninstall order and the options form must be checked with the Inno Setup version used for the build: one
confirmation, then the options, no second prompt. Record the result in `VALIDATION.md`.
