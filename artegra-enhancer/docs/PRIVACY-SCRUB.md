# Public-content audit

Only allowlisted source was imported. Private planning notes, original deployment files, application binaries, runtime folders, model weights and original history are excluded from the repository.

`tools/public_scan.py` checks every tracked file, and with `--history` every blob and commit message reachable from any branch or tag. It always rejects absolute workstation paths, Windows network paths, credential formats, model payloads and other prohibited binaries, and binary files that are not pinned. Licensed font/image assets are individually hash-pinned in `asset-hashes.json`; their binary bytes are not mistaken for textual drive paths.

The specific private words (user and machine names, the studio's server and internal folder names, internal tool names, and the names of features and another product that are not part of Artegra Enhancer) are not kept in the repository in any form. A maintainer keeps them, one per line, in `.local/private-terms.txt`, which git ignores. Where that file is present, the scan also rejects each listed word in any case, in file contents, file names and commit messages, and a listed two-word name with up to three joining characters between its words. The one exception is the installer's line that links to the studio's public website, and only in its exact form. Where the file is absent, as in GitHub CI and in a fresh clone, the scan checks only the generic patterns above, so the release checklist runs it on a maintainer's machine with the file in place.

`tools/check_secrets.py` exports exactly the staged files to an isolated temporary directory and scans it with Gitleaks and TruffleHog. With `--history` it also scans every commit of every branch and tag with both scanners. Candidate secrets are not printed or checked against remote services. The public history receives an additional content scan (`tools/public_scan.py --history`).

Source scans do not establish the safety of arbitrary logs a user later chooses to share. Review user-provided diagnostics separately. Binary package inspection and screenshot review are separate release checks.
