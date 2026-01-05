from __future__ import annotations
import os
from pathlib import Path

def project_root() -> Path:
    # src/config.py -> src -> project root
    return Path(__file__).resolve().parents[1]

ROOT = project_root()

DATA_DIR = ROOT / "data"
IMPORT_DIR = DATA_DIR / "import"
EXPORT_DIR = DATA_DIR / "export"
STORAGE_DIR = DATA_DIR / "storage"

DB_PATH = STORAGE_DIR / "profiles.db"

PROFILE_SECRET = os.getenv("PROFILE_SECRET", "change-me-secret")
DEFAULT_EXPORT_PATH = EXPORT_DIR / "verified.csv"
HISTORY_CSV_PATH = STORAGE_DIR / "history.csv"

def ensure_dirs() -> None:
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
