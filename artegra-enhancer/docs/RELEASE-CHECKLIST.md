# Release checklist

1. Capture an immutable allowlisted source snapshot and record provenance. Preserve graph identity for every offered mode.
2. Review every file and commit for private information, excluded material and credentials. Run the custom scan, Gitleaks and TruffleHog on files and history.
3. Resolve model licences and verify exact publisher/local hashes. Obtain each user's model-term acceptance before an enabled download.
4. Lock and inventory runtime dependencies. Include corresponding source and full licences for GPL components, and required notices and replacement/relinking information for Qt.
5. Run CPU tests, the offscreen host smoke, and the packaged host smoke. Build twice and compare the resulting artifacts where reproducibility is claimed.
6. Compare actual Standard and Fast rendered pixels with the reference on the same hardware, settings and seed. Measure memory use and time; do not infer these from prompt identity.
7. Test a fresh Windows account, paths with spaces and non-ASCII characters, interrupted setup, host crash, restart recovery, a 50-image batch and uninstall. Verify no unrelated installation or process is changed.
8. Capture network traffic during setup and use. Review the screenshots and diagnostic bundle for private content.
9. Review release notes, hardware limits, model terms and pilot agreement. Publish checksums and an SBOM alongside a qualified binary release.
10. Invite testers only under the approved pilot arrangements. Record which checks are incomplete rather than marking them passed.

