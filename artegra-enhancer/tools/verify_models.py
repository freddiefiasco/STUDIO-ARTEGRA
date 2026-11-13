"""Verify existing model files in place; never download, copy or modify them."""
import argparse
import hashlib
import json
from pathlib import Path


def verify(directory: Path, models: list[dict]) -> list[dict]:
    root = directory.resolve()
    results = []
    for model in models:
        relative = Path(model["folder"]) / model["filename"]
        path = (root / relative).resolve()
        if not path.is_relative_to(root):
            raise ValueError("A model manifest entry escapes the chosen model folder.")
        result = {"file": relative.as_posix(), "ok": False}
        if not path.is_file():
            result["reason"] = "missing"
        elif path.stat().st_size != model["size_bytes"]:
            result["reason"] = "size differs from publisher"
        else:
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
                    digest.update(chunk)
            result["ok"] = digest.hexdigest() == model["sha256"]
            if not result["ok"]:
                result["reason"] = "hash differs from publisher"
        results.append(result)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--manifest", type=Path, default=Path(__file__).resolve().parents[1] / "models.manifest.json")
    args = parser.parse_args()
    results = verify(args.directory, json.loads(args.manifest.read_text())["models"])
    print(json.dumps(results, indent=2))
    return int(any(not item["ok"] for item in results))


if __name__ == "__main__":
    raise SystemExit(main())
