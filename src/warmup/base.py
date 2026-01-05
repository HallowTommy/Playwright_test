"""
Базовые классы и функции для работы с браузером через Playwright.
Подключение к уже открытому браузеру пользователя.
"""
from __future__ import annotations

from typing import Optional
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
from rich import print


class BrowserConnector:
    """
    Класс для подключения к уже открытому браузеру через CDP (Chrome DevTools Protocol).
    
    Пользователь должен открыть браузер самостоятельно с remote debugging портом.
    """
    
    def __init__(self, cdp_endpoint: str = "http://localhost:9222"):
        """
        Args:
            cdp_endpoint: CDP endpoint (по умолчанию localhost:9222)
        """
        self.cdp_endpoint = cdp_endpoint
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
    
    def connect(self) -> Browser:
        """
        Подключение к уже открытому браузеру через CDP.
        
        Returns:
            Browser instance
            
        Raises:
            ConnectionError: Если не удалось подключиться к браузеру
        """
        try:
            self.playwright = sync_playwright().start()
            # Подключаемся к существующему браузеру через CDP
            self.browser = self.playwright.chromium.connect_over_cdp(self.cdp_endpoint)
            return self.browser
        except Exception as e:
            error_msg = str(e).lower()
            if "connection" in error_msg or "refused" in error_msg:
                raise ConnectionError(
                    f"\n[red]Не удалось подключиться к браузеру![/red]\n\n"
                    f"[yellow]Перед запуском скрипта откройте браузер с remote debugging:[/yellow]\n\n"
                    f"[cyan]Для Chrome/Chromium:[/cyan]\n"
                    f"  Запустите браузер с командой:\n"
                    f"  [green]chrome.exe --remote-debugging-port=9222[/green]\n\n"
                    f"[cyan]Или закройте все окна Chrome и запустите:[/cyan]\n"
                    f"  [green]\"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe\" --remote-debugging-port=9222[/green]\n\n"
                    f"[dim]После этого браузер будет открыт, и скрипт сможет к нему подключиться.[/dim]\n"
                    f"[dim]Оригинальная ошибка: {e}[/dim]"
                )
            else:
                raise ConnectionError(
                    f"Ошибка подключения к браузеру: {e}"
                )
    
    def get_context(self) -> BrowserContext:
        """Получить контекст браузера (или создать новый, если нет)"""
        if not self.browser:
            self.connect()
        
        # Пытаемся использовать первый доступный контекст
        contexts = self.browser.contexts
        if contexts:
            self.context = contexts[0]
        else:
            # Если контекстов нет, создаем новый
            self.context = self.browser.new_context()
        
        return self.context
    
    def get_page(self, index: int = 0) -> Page:
        """
        Получить страницу из контекста.
        
        Args:
            index: Индекс страницы (по умолчанию 0 - первая открытая вкладка)
            
        Returns:
            Page instance
        """
        context = self.get_context()
        pages = context.pages
        
        if pages and index < len(pages):
            self.page = pages[index]
        else:
            # Если страниц нет, создаем новую
            self.page = context.new_page()
        
        return self.page
    
    def close(self):
        """Закрыть соединение (не закрывает браузер пользователя)"""
        # Не закрываем браузер, так как он открыт пользователем
        # Просто останавливаем Playwright
        if self.playwright:
            self.playwright.stop()
            self.playwright = None
            self.browser = None
            self.context = None
            self.page = None

