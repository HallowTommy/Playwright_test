from __future__ import annotations

import csv
import sqlite3

import typer
from rich import print

from .common import setup
from src.config import IMPORT_DIR, PROFILE_SECRET
from src.profile.generator import generate, normalize_phone
from src.cli.history_sync import sync_history

from api.hero_sms.client import (
    HeroSMSClient,
    HeroSMSError,
    HeroSMSAuthError,
    HeroSMSNoMoneyError,
    HeroSMSNoNumbersError,
    HeroSMSBadParamsError,
)

app = typer.Typer(help="Команды для работы с Hero-SMS")

# Алиасы "человеческих" названий -> коды SMS-activate протокола
SERVICE_ALIASES = {
    "gmail": "go",
    "google": "go",
    "telegram": "tg",
    "tg": "tg",
    "whatsapp": "wa",
    "wa": "wa",
}


def _normalize_service(service: str) -> str:
    s = (service or "").strip().lower()
    return SERVICE_ALIASES.get(s, s)


@app.command("get-phone")
def get_phone(
    country_id: int = typer.Option(43, "--country", "-c", help="ID страны (Германия = 43)"),
    service: str = typer.Option("gmail", "--service", "-s", help="Сервис (gmail/telegram/whatsapp и т.д.)"),
    secret: str = typer.Option(PROFILE_SECRET, "--secret", help="Секрет для генерации профиля"),
    api_key: str = typer.Option("", "--api-key", help="API ключ Hero SMS (или через HEROSMS_API_KEY в .env)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Режим разработки - без реальных запросов (безопасно)"),
    test_mode: bool = typer.Option(False, "--test/--real", help="Оставлено для совместимости (обычно не нужно)"),
    show_activation_id: bool = typer.Option(True, "--show-activation/--hide-activation", help="Показывать activation id"),
):
    """
    Получить номер через Hero-SMS и автоматически сгенерировать профиль.

    По умолчанию номер берётся по САМОЙ дешёвой доступной цене (getPrices -> min cost -> getNumber).
    """
    db = setup()

    service_code = _normalize_service(service)

    # 1) Клиент
    try:
        client = HeroSMSClient(
            api_key=api_key if api_key else None,
            dry_run=dry_run,
            test_mode=test_mode,
        )
    except ValueError as e:
        print(f"[red]Ошибка: {e}[/red]")
        if not dry_run:
            print("[yellow]Создай .env в корне проекта:[/yellow]")
            print("[cyan]HEROSMS_API_KEY=your_api_key_here[/cyan]")
            print("\n[yellow]Или используй безопасный режим:[/yellow]")
            print("[cyan]python -m src.main get-phone --dry-run[/cyan]")
        raise typer.Exit(code=1)

    # 2) Баланс (не критично)
    try:
        print("[cyan]Проверяю баланс аккаунта...[/cyan]")
        balance = client.get_balance()
        print(f"[green]Баланс: {balance}[/green]")
    except Exception as e:
        print(f"[yellow]Не удалось проверить баланс (продолжаю): {e}[/yellow]")

    # 3) Получаем номер (ВСЕГДА cheapest)
    print(f"[cyan]Запрашиваю номер (cheapest): country={country_id}, service={service_code} (from '{service}')...[/cyan]")
    try:
        number_data = client.get_number_cheapest(country_id=country_id, service=service_code)
    except HeroSMSAuthError as e:
        print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)
    except HeroSMSNoMoneyError as e:
        print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)
    except HeroSMSNoNumbersError as e:
        print(f"[red]{e}[/red]")
        raise typer.Exit(code=2)
    except HeroSMSBadParamsError as e:
        print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)
    except HeroSMSError as e:
        print(f"[red]Hero-SMS ошибка: {e}[/red]")
        raise typer.Exit(code=1)

    phone_number = (number_data.get("number") or "").strip()
    activation_id = (number_data.get("id") or "").strip()

    if not phone_number:
        print("[red]Не удалось получить номер от API[/red]")
        raise typer.Exit(code=1)

    print(f"[green]Получен номер: {phone_number}[/green]")
    if show_activation_id and activation_id:
        print(f"[dim]activation_id: {activation_id}[/dim]")

    # 4) Нормализуем номер
    phone_normalized = normalize_phone(phone_number)

    # 5) Сохраняем в БД
    usage_count = db.upsert_phone(phone_normalized, phone_number)

    # 6) Обновляем phones.csv
    phones_csv_path = IMPORT_DIR / "phones.csv"
    all_phones = db.get_all_phones_sorted()

    with phones_csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["phone"])
        for p in all_phones:
            for _ in range(p["usage_count"]):
                writer.writerow([p["phone"]])

    if usage_count == 1:
        print(f"[cyan]Номер добавлен в {phones_csv_path}[/cyan]")
    else:
        print(f"[cyan]Номер добавлен в {phones_csv_path} (использование #{usage_count})[/cyan]")

    # 7) Генерация профиля
    print(f"[cyan]Генерирую профиль для {phone_normalized}...[/cyan]")

    MAX_TRIES = 50
    saved = False
    gp = None

    for variant in range(MAX_TRIES):
        try:
            gp = generate(phone_normalized, secret=secret, variant=variant)
            db.create_profile(
                phone_normalized,
                gp.first_name,
                gp.last_name,
                gp.full_name,
                gp.birth_date,
                gp.email,
                gp.nickname,
                gp.password,
                activation_id=activation_id if activation_id else None,
            )
            saved = True
            print(f"[green]Профиль создан: {gp.full_name}[/green]")
            break
        except sqlite3.IntegrityError:
            continue

    if not saved or gp is None:
        print(f"[red]Не удалось сгенерировать уникальный профиль после {MAX_TRIES} попыток[/red]")
        print("[yellow]Попробуй другой номер[/yellow]")
        raise typer.Exit(code=1)

    # 8) Синхронизация истории
    sync_history(db)

    # 9) Итог
    if usage_count == 1:
        print(f"[green]Готово! Номер: {phone_normalized}, Профиль: {gp.full_name}[/green]")
    else:
        print(f"[green]Готово! Номер: {phone_normalized} (использование #{usage_count}), Профиль: {gp.full_name}[/green]")


@app.command("get-sms")
def get_sms(
    activation_id: str = typer.Option(..., "--id", "-i", help="Activation ID из get-phone"),
    api_key: str = typer.Option("", "--api-key", help="API ключ (или HEROSMS_API_KEY)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Без реальных запросов"),
):
    """
    Получить SMS код по activation_id.
    """
    try:
        client = HeroSMSClient(api_key=api_key if api_key else None, dry_run=dry_run)
    except ValueError as e:
        print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)

    try:
        status = client.get_status(activation_id)
        print(f"[cyan]Статус: {status}[/cyan]")

        code = client.get_sms_code(activation_id)
        if code:
            print(f"[green]Код: {code}[/green]")
        else:
            print("[yellow]Кода ещё нет (STATUS_WAIT_CODE или другой статус)[/yellow]")

    except HeroSMSError as e:
        print(f"[red]Hero-SMS ошибка: {e}[/red]")
        raise typer.Exit(code=1)
