"""
Оркестратор для выполнения сценариев разогрева браузера.
"""
from __future__ import annotations

from typing import Callable
from rich import print

from .base import BrowserConnector


class WarmupOrchestrator:
    """
    Оркестратор для управления выполнением сценариев разогрева.
    
    Работает независимо от профилей из базы данных.
    Пользователь сам управляет браузером и профилями в нем.
    """
    
    def __init__(
        self,
        cdp_endpoint: str = "http://localhost:9222",
    ):
        """
        Args:
            cdp_endpoint: CDP endpoint для подключения к браузеру
        """
        self.connector = BrowserConnector(cdp_endpoint)
        self.browser = None
        self.context = None
        self.page = None
    
    def start(self):
        """Инициализация подключения к браузеру"""
        print("[cyan]Подключаюсь к открытому браузеру...[/cyan]")
        try:
            self.browser = self.connector.connect()
            self.context = self.connector.get_context()
            self.page = self.connector.get_page()
            print("[green]✓ Подключение к браузеру установлено[/green]")
            print("[dim]Браузер должен быть открыт и готов к работе[/dim]")
        except ConnectionError as e:
            print(str(e))
            raise
        except Exception as e:
            print(f"[red]Ошибка подключения к браузеру: {e}[/red]")
            raise
    
    def run_scenario(self, scenario_func: Callable):
        """
        Запуск сценария разогрева.
        
        Args:
            scenario_func: Функция сценария, которая принимает page (Page object)
        """
        if not self.page:
            self.start()
        
        print(f"[cyan]Запускаю сценарий: {scenario_func.__name__}[/cyan]")
        try:
            scenario_func(self.page)
            print(f"[green]✓ Сценарий {scenario_func.__name__} выполнен успешно[/green]")
        except Exception as e:
            print(f"[red]Ошибка выполнения сценария {scenario_func.__name__}: {e}[/red]")
            raise
    
    def stop(self):
        """Остановка оркестратора"""
        print("[cyan]Отключаюсь от браузера...[/cyan]")
        self.connector.close()
        print("[green]✓ Отключено[/green]")

