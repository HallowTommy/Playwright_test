from __future__ import annotations

from pathlib import Path
import typer
from rich import print

from src.config import DB_PATH, HISTORY_CSV_PATH, STORAGE_DIR, IMPORT_DIR, DEFAULT_EXPORT_PATH

app = typer.Typer()

def _delete_if_exists(p: Path) -> bool:
    try:
        if p.exists():
            p.unlink()
            return True
    except Exception as e:
        print(f"[red]Не смог удалить[/red] {p}: {e}")
    return False

@app.command("clean")
def clean(
    yes: bool = typer.Option(False, "--yes", help="Подтвердить удаление данных (обязательно)"),
    db: bool = typer.Option(True, "--db/--no-db", help="Удалить базу (profiles.db)"),
    history: bool = typer.Option(True, "--history/--no-history", help="Удалить history.csv"),
    phones: bool = typer.Option(True, "--phones/--no-phones", help="Очистить импортированные номера (phones.csv)"),
    export: bool = typer.Option(True, "--export/--no-export", help="Удалить файл экспорта (verified.csv)"),
):
    """
    Удаляет все данные:
    - SQLite DB (и файлы WAL/SHM)
    - history.csv
    - phones.csv (импортированные номера)
    - verified.csv (файл экспорта)
    """
    if not yes:
        print("[yellow]Отмена.[/yellow] Добавь [bold]--yes[/bold], чтобы подтвердить удаление.")
        raise typer.Exit(code=2)

    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    removed_any = False

    if db:
        # SQLite в WAL режиме создаёт рядом db-wal и db-shm
        removed_any |= _delete_if_exists(DB_PATH)
        removed_any |= _delete_if_exists(Path(str(DB_PATH) + "-wal"))
        removed_any |= _delete_if_exists(Path(str(DB_PATH) + "-shm"))

        print(f"[cyan]DB cleanup[/cyan]: {DB_PATH}")

    if history:
        removed_any |= _delete_if_exists(HISTORY_CSV_PATH)
        print(f"[cyan]History cleanup[/cyan]: {HISTORY_CSV_PATH}")

    if phones:
        phones_csv = IMPORT_DIR / "phones.csv"
        removed_any |= _delete_if_exists(phones_csv)
        if phones_csv.exists():
            # Если файл существует, очищаем его содержимое, оставляя только заголовок
            with phones_csv.open("w", encoding="utf-8-sig", newline="") as f:
                f.write("phone\n")
            removed_any = True
            print(f"[cyan]Phones cleanup[/cyan]: {phones_csv}")

    if export:
        removed_any |= _delete_if_exists(DEFAULT_EXPORT_PATH)
        print(f"[cyan]Export cleanup[/cyan]: {DEFAULT_EXPORT_PATH}")

    if removed_any:
        print("[green]Готово.[/green] Все данные очищены.")
    else:
        print("[yellow]Нечего удалять.[/yellow] Файлы не найдены.")
