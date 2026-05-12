from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
DOWNLOADS = FRONTEND / "downloads"
BUNDLE_PATH = DOWNLOADS / "safeagent-dashboard-static-site.zip"

STATIC_FILES = [
    FRONTEND / "index.html",
    FRONTEND / "styles.css",
    FRONTEND / "app.js",
    FRONTEND / "nginx.conf",
    FRONTEND / "Dockerfile",
    FRONTEND / "DEPLOY.md",
]


def iter_download_files() -> list[Path]:
    if not DOWNLOADS.exists():
        return []
    return sorted(path for path in DOWNLOADS.rglob("*") if path.is_file())


def main() -> None:
    DOWNLOADS.mkdir(parents=True, exist_ok=True)

    with ZipFile(BUNDLE_PATH, "w", compression=ZIP_DEFLATED) as zf:
        for path in STATIC_FILES:
            if path.exists():
                zf.write(path, arcname=path.name)

        for path in iter_download_files():
            if path.resolve() == BUNDLE_PATH.resolve():
                continue
            zf.write(path, arcname=str(path.relative_to(FRONTEND)))

    print(f"frontend portal bundle created: {BUNDLE_PATH}")


if __name__ == "__main__":
    main()
