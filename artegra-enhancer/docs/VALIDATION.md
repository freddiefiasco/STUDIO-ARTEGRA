# Validation status

This file reports the scope of evidence; it is not a release certificate.

| Check | Status |
|---|---|
| Source snapshot captured and file hashes recorded | Complete |
| Generated Standard/Fast prompts match source snapshot | 184 cases pass |
| Standalone host connects to simulated engine offscreen | Pass; Fast available; no GPU used |
| Service authentication and exact-host shutdown tests | 17 focused service boundary tests pass |
| Public source privacy and secret scans | Passed: custom content scan, Gitleaks and TruffleHog |
| Frozen application smoke and packaging | Pass; installer and portable ZIP built |
| Actual Standard/Fast output pixel comparison | Not run for standalone package |
| Installer round trip, path with spaces/non-ASCII | Pass on the build account; clean-account runtime setup not run |
| Network capture, 50-image endurance, out-of-memory recovery | Not run |
| Full model licence and automatic-acquisition approval | Incomplete |
| External pilot agreement | Draft only |

Reference-build proofs are not represented as fresh standalone-package GPU results. A release candidate must complete the remaining checks on appropriate test machines.


`BUILD-RESULTS.json` records the artifact hashes and exact validation scope. Binary artifacts remain a draft pending the outstanding qualification checks.
