from __future__ import annotations
from src.config import HISTORY_CSV_PATH
from src.io.exporter import write_history_csv
from src.storage.db import DB

def sync_history(db: DB) -> None:
    rows = db.history_rows()
    write_history_csv(rows, HISTORY_CSV_PATH)
