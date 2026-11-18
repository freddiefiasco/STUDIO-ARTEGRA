# Public-content audit

Only allowlisted source was imported. Private planning notes, original deployment files, application binaries, runtime folders, model weights and original history are excluded from the repository.

`tools/public_scan.py` rejects private identifiers, the studio's server and internal folder names, absolute workstation paths, network paths, credential formats, unapproved binaries and model payloads. Licensed font/image assets are individually hash-pinned in `asset-hashes.json`; their binary bytes are not mistaken for textual drive paths.

`tools/check_secrets.py` exports exactly the staged files to an isolated temporary directory and scans it with Gitleaks and TruffleHog. With `--history` it also scans every commit of every branch and tag with both scanners. Candidate secrets are not printed or checked against remote services. The public history receives an additional content scan (`tools/public_scan.py --history`).

Source scans do not establish the safety of arbitrary logs a user later chooses to share. Review user-provided diagnostics separately. Binary package inspection and screenshot review are separate release checks.
