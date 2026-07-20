"""Snapshot the project to a zip file in _releases/v1.1-quality/.

Excludes:
- .env (secrets)
- bot_data.db, backups/ (runtime state)
- __pycache__, .pytest_cache, .ruff_cache (build artifacts)
- _releases/ (meta)
"""

import os
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RELEASE_DIR = PROJECT_ROOT / "_releases" / "v1.1-quality"
ZIP_PATH = RELEASE_DIR / "mikrotik_bot.zip"

EXCLUDE_DIRS = {
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "_releases",
    "backups",
    ".git",
    "venv",
    ".venv",
    "node_modules",
}

EXCLUDE_FILES = {
    ".env",
    "bot_data.db",
    "bot_data.db-journal",
    "bot_data.db-wal",
    "bot_data.db-shm",
    "mikrotik_bot.lock",
    "Thumbs.db",
    ".DS_Store",
}

EXCLUDE_EXTENSIONS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".so",
    ".dll",
    ".dylib",
}


def should_exclude(path: Path) -> bool:
    """Return True if path should be excluded from the zip."""
    parts = set(path.parts)
    if parts & EXCLUDE_DIRS:
        return True
    if path.name in EXCLUDE_FILES:
        return True
    if path.suffix in EXCLUDE_EXTENSIONS:
        return True
    return False


def build_zip() -> int:
    """Create the snapshot zip. Returns number of files added."""
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    count = 0
    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(PROJECT_ROOT):
            # Filter excluded dirs in-place to prevent descent
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for file in files:
                filepath = Path(root) / file
                if should_exclude(filepath):
                    continue
                # Make path relative to project root
                arcname = filepath.relative_to(PROJECT_ROOT)
                zf.write(filepath, arcname)
                count += 1
    return count


if __name__ == "__main__":
    n = build_zip()
    size_kb = ZIP_PATH.stat().st_size / 1024
    print(f"Created {ZIP_PATH} ({size_kb:.1f} KB, {n} files)")
