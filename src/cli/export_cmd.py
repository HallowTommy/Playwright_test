from __future__ import annotations

from pathlib import Path
import typer
from rich import print

from .common import setup
from src.config import DEFAULT_EXPORT_PATH
from src.io.exporter import export_csv, export_xlsx

app = typer.Typer()

@app.command("export")
def export(
    out: str = typer.Option(str(DEFAULT_EXPORT_PATH), "--out", help="Output file (.csv or .xlsx)"),
):
    """Экспортирует все профили в файл"""
    db = setup()
    rows = db.export_all()
    out_path = Path(out).expanduser().resolve()

    suffix = out_path.suffix.lower()
    if suffix == ".xlsx":
        export_xlsx(rows, out_path)
    else:
        # по умолчанию csv (даже если расширения нет)
        if suffix != ".csv":
            out_path = out_path.with_suffix(".csv")
        export_csv(rows, out_path)

    print(f"[cyan]Exported[/cyan] {len(rows)} профилей -> {out_path}")
