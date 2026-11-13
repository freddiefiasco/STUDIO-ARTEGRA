"""Fetch pinned audit tools from their official, checksum-verified releases."""
import hashlib
import io
from pathlib import Path
import tarfile
from urllib.request import Request, urlopen
import zipfile


def get(url):
    with urlopen(Request(url, headers={"User-Agent": "Artegra-release-audit"}), timeout=90) as response:
        return response.read()


def main():
    destination = Path(".local/tools")
    destination.mkdir(parents=True, exist_ok=True)
    releases = (
        ("gitleaks/gitleaks", "v8.30.1", "gitleaks_8.30.1_windows_x64.zip", "gitleaks_8.30.1_checksums.txt"),
        ("trufflesecurity/trufflehog", "v3.99.9", "trufflehog_3.99.9_windows_amd64.tar.gz", "trufflehog_3.99.9_checksums.txt"),
    )
    for repository, version, archive, checksum in releases:
        base = f"https://github.com/{repository}/releases/download/{version}/"
        sums = get(base + checksum).decode()
        expected = next(line.split()[0] for line in sums.splitlines() if line.split()[-1].lstrip("*") == archive)
        data = get(base + archive)
        if hashlib.sha256(data).hexdigest() != expected:
            raise RuntimeError("Audit tool checksum mismatch")
        if archive.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(data)) as bundle:
                for name in bundle.namelist():
                    if name.endswith(".exe"):
                        (destination / Path(name).name).write_bytes(bundle.read(name))
        else:
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as bundle:
                for member in bundle.getmembers():
                    if member.name.endswith(".exe"):
                        (destination / Path(member.name).name).write_bytes(bundle.extractfile(member).read())
        print(repository + " " + version + " verified")


if __name__ == "__main__":
    main()
