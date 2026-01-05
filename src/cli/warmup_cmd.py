"""
CLI команды для разогрева браузера.
"""
from __future__ import annotations

import importlib
import typer
from rich import print

from src.warmup.orchestrator import WarmupOrchestrator

app = typer.Typer(help="Команды для разогрева браузера")

# Сценарии по номеру: 1,2,3...
# 1 = твой нулевой день (рандомизированный)
SCENARIOS = {
    1: ("Warmup 1", "src.warmup.scenarios.scenario_1", "scenario_1"),
}

def _load_scenario(num: int):
    if num not in SCENARIOS:
        available = ", ".join(str(x) for x in sorted(SCENARIOS.keys()))
        raise typer.BadParameter(f"Сценарий {num} не найден. Доступны: {available}")

    _, module_path, func_name = SCENARIOS[num]
    module = importlib.import_module(module_path)
    fn = getattr(module, func_name, None)

    if not callable(fn):
        raise ImportError(f"В модуле {module_path} нет функции {func_name}")

    return fn


@app.command("run")
def run_warmup(
    num: int = typer.Argument(..., help="Номер сценария (1, 2, 3...)"),
    cdp_endpoint: str = typer.Option("http://localhost:9222", "--cdp", help="CDP endpoint браузера (по умолчанию 9222)"),
):
    """
    Запуск сценария разогрева в уже открытом браузере (CDP).

    Пример:
      chrome.exe --remote-debugging-port=9222
      python -m src.main warmup run 1
    """
    scenario_func = _load_scenario(num)
    title, _, _ = SCENARIOS[num]
    print(f"[cyan]Запуск сценария {num}:[/cyan] {title}")

    orchestrator = WarmupOrchestrator(cdp_endpoint=cdp_endpoint)

    try:
        orchestrator.start()
        orchestrator.run_scenario(scenario_func)
    except KeyboardInterrupt:
        print("\n[yellow]Разогрев прерван пользователем[/yellow]")
    except Exception as e:
        print(f"[red]Ошибка: {e}[/red]")
        raise typer.Exit(code=1)
    finally:
        orchestrator.stop()


@app.command("list")
def list_scenarios():
    """Показать список доступных сценариев"""
    print("[cyan]Доступные сценарии:[/cyan]")
    for num in sorted(SCENARIOS.keys()):
        title, module_path, func_name = SCENARIOS[num]
        print(f"  {num}: {title}  ({module_path}.{func_name})")


if __name__ == "__main__":
    app()
