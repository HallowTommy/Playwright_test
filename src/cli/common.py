from __future__ import annotations
from dotenv import load_dotenv

from src.config import ensure_dirs, DB_PATH
from src.storage.db import DB

def setup() -> DB:
    load_dotenv()
    ensure_dirs()
    db = DB(DB_PATH)
    db.init()
    return db
