# Security

## Report a security problem

Do not post the details of a security problem in a public issue. Instead, [open an issue](https://github.com/freddiefiasco/STUDIO-ARTEGRA/issues/new/choose) that asks for a private way to report, without any details of the problem. If the repository offers GitHub's private vulnerability reporting (**Report a vulnerability** on its **Security** tab), you can use that instead.

In the private report, include the app version (shown in **About**), what an attacker could do, and the steps to reproduce it. Never include credentials, private images or unredacted logs.

## Supported versions

Fixes are made in new releases, so use the newest one. At the time of writing that is 5.0.2 Beta 1, which installs over 5.0.1 Beta 1.

## How the app protects you

- The app's service listens on your own computer only (loopback), and every request needs the session token that the app creates when it starts. Do not expose its port through a proxy or a firewall rule.
- Setup downloads the image engine and the models over HTTPS from their publishers' own addresses, and checks each file against the SHA-256 pinned in the app before using it. A file that does not match is removed.
- The app closes only the processes it started itself.
- **Check for updates** never downloads or runs anything; **Download** opens the release page in your browser.

## Check what you download

The installer and the portable ZIP are not code-signed in this Beta. Download them only from the [Studio Artegra release page](https://github.com/freddiefiasco/STUDIO-ARTEGRA/releases) and compare each file with `SHA256SUMS.txt`, as described in the [installation guide](INSTALL.md#download-and-check-the-file). `SBOM.cdx.json` lists the components the app ships.
