from __future__ import annotations
import typer

from src.cli.export_cmd import app as export_app
from src.cli.clean_cmd import app as clean_app
from src.cli.herosms_cmd import app as herosms_app
from src.cli.warmup_cmd import app as warmup_app

app = typer.Typer()

app.add_typer(herosms_app)   # <- добавит get-phone и get-sms
app.add_typer(export_app)
app.add_typer(clean_app)
app.add_typer(warmup_app, name="warmup")  # <- добавит warmup run и warmup list

if __name__ == "__main__":
    app()
