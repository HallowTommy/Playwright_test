from __future__ import annotations
from pathlib import Path
import csv
from typing import Iterable, Dict, Any

HISTORY_HEADERS = [
    "created_at",
    "phone",
    "full_name",
    "first_name",
    "last_name",
    "birth_date",
    "nickname",
    "email",
    "password",
]



def export_csv(rows: Iterable[Dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    if not rows:
        with out_path.open("w", encoding="utf-8", newline="") as f:
            f.write(
                "phone,full_name,first_name,last_name,birth_date,nickname,email,password,created_at\n")
        return

    headers = list(rows[0].keys())
    with out_path.open("w", encoding="utf-8", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=headers)
        wr.writeheader()
        wr.writerows(rows)

def export_xlsx(rows: Iterable[Dict[str, Any]], out_path: Path) -> None:
    try:
        from openpyxl import Workbook
    except ModuleNotFoundError as e:
        raise RuntimeError("Нужен openpyxl: python -m pip install openpyxl") from e

    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    wb = Workbook()
    ws = wb.active
    ws.title = "verified"

    if rows:
        headers = list(rows[0].keys())
        ws.append(headers)
        for r in rows:
            ws.append([r.get(h) for h in headers])
    else:
        ws.append(["phone","full_name","first_name","last_name","birth_date","nickname","email","password","created_at"])

    wb.save(out_path)
    wb.close()

def write_history_csv(rows: Iterable[Dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)

    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=HISTORY_HEADERS)
        w.writeheader()
        for r in rows:
            # пишем только нужные колонки в правильном порядке
            w.writerow({k: r.get(k, "") for k in HISTORY_HEADERS})