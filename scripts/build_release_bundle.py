from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
DOWNLOADS = ROOT / "frontend" / "downloads"
BUNDLE_SCRIPTS = ROOT / "scripts"
BUNDLE_PATH = DOWNLOADS / "safeagent-deployment-bundle.zip"

FILES_TO_PACKAGE = [
    DOWNLOADS / "safeagent-release-manifest.json",
    DOWNLOADS / "docker-compose.release.yml",
    DOWNLOADS / ".env.release.example",
    DOWNLOADS / "install-guide.md",
    DOWNLOADS / "install.bat",
    DOWNLOADS / "install.sh",
    DOWNLOADS / "prepare-release-images.ps1",
    DOWNLOADS / "prepare-release-images.sh",
    BUNDLE_SCRIPTS / "build_release_images.ps1",
    BUNDLE_SCRIPTS / "build_release_images.sh",
    DOWNLOADS / "safeagent-api-v0.2.0.tar",
    DOWNLOADS / "safeagent-dashboard-v0.2.0.tar",
]


def main() -> None:
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    with ZipFile(BUNDLE_PATH, "w", compression=ZIP_DEFLATED) as zf:
        for path in FILES_TO_PACKAGE:
            if not path.exists():
                raise FileNotFoundError(f"required bundle file is missing: {path}")
            arcname = path.name if path.parent == DOWNLOADS else f"scripts/{path.name}"
            zf.write(path, arcname=arcname)
    print(f"release bundle created: {BUNDLE_PATH}")


if __name__ == "__main__":
    main()
