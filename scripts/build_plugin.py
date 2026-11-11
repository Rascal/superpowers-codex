#!/usr/bin/env python3
"""Build a local Codex marketplace archive from an explicit release allowlist."""

import argparse
import hashlib
import json
from pathlib import Path
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def build(destination):
    manifest = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))
    name, version = manifest["name"], manifest["version"]
    marketplace = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text(encoding="utf-8"))
    marketplace["plugins"][0]["source"]["path"] = "./plugins/" + name
    files = [ROOT / "plugin.json", ROOT / "README.md"]
    files += [path for folder in ("skills", "hooks") for path in (ROOT / folder).rglob("*")
              if path.is_file() and "__pycache__" not in path.parts and path.suffix in (".py", ".md", ".json")]
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / (name + "-" + version + ".zip")
    prefix = name + "-" + version + "/"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        output.writestr(prefix + ".agents/plugins/marketplace.json", json.dumps(marketplace, indent=2) + "\n")
        for path in sorted(files):
            if path.is_symlink():
                raise ValueError("Release files cannot be symlinks: " + str(path))
            output.write(path, prefix + "plugins/" + name + "/" + path.relative_to(ROOT).as_posix())
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(checksum + "  " + archive.name + "\n", encoding="utf-8")
    return {"archive": str(archive.resolve()), "sha256": checksum, "files": len(files) + 1}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(ROOT / ".review-gate/releases"))
    print(json.dumps(build(parser.parse_args().output), indent=2))
