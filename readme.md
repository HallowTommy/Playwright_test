# Profile Tool

Инструмент для покупки номеров через API Hero SMS и автоматической генерации профилей.

## Основные команды

### Получить номер и сгенерировать профиль

```bash
# Базовое использование (США, Gmail)
python -m src.main get-phone --country 43 --service gmail

# Короткая форма
python -m src.main get-phone -c 187 -s gmail

# Для Telegram
python -m src.main get-phone -c 43 -s telegram

# Для WhatsApp
python -m src.main get-phone -c 43 -s whatsapp
```

**Параметры:**
- `--country` или `-c` - ID страны (см. список ниже)
- `--service` или `-s` - сервис (`gmail`, `telegram`, `whatsapp`)

### Экспорт профилей

```bash
# Экспорт в CSV (по умолчанию)
python -m src.main export

# Экспорт в XLSX
python -m src.main export --out .\data\export\profiles.xlsx

# Экспорт в указанный файл
python -m src.main export --out путь\к\файлу.csv
```

### Очистка данных

```bash
# ⚠️ ВНИМАНИЕ: Необратимое действие!
python -m src.main clean --yes
```

Удаляет все данные: базу данных, историю, номера и экспорт.

## Доступные страны для Gmail

| ID  | Country          |
|-----|------------------|
| 187 | USA              |
| 36  | Canada           |
| 6   | Indonesia        |
| 4   | Philippines      |
| 37  | Morocco          |
| 31  | South Africa     |
| 33  | Colombia         |
| 7   | Malaysia         |
| 50  | Austria          |
| 43  | Germany          |
| 10  | Vietnam          |
| 41  | Cameroon         |
| 56  | Spain            |
| 14  | Hong Kong        |
| 78  | France           |
| 8   | Kenya            |
| 84  | Hungary          |
| 25  | Laos             |
| 24  | Cambodia         |
| 23  | Ireland          |

## Примеры использования

```bash
# Получить номер из США для Gmail
python -m src.main get-phone -c 187 -s gmail

# Получить номер из Канады для Gmail
python -m src.main get-phone -c 36 -s gmail

# Получить номер из Германии для Gmail
python -m src.main get-phone -c 43 -s gmail

# Получить номер из Индонезии для Gmail (дешевле)
python -m src.main get-phone -c 6 -s gmail

# Экспортировать все профили
python -m src.main export

# Очистить все данные
python -m src.main clean --yes
```

## Справка

```bash
python -m src.main --help
python -m src.main get-phone --help
python -m src.main export --help
python -m src.main clean --help
```

## Ручной запуск браузера для тестов (CDP)

Для локального и ручного тестирования используется стандартный браузер **Google Chrome** с включённым CDP (remote debugging).

Запуск тестового браузера выполняется **из PowerShell** командой:

```powershell
.\tests\start_test_chrome_cdp.ps1
```

После того как Chrome успешно запущен и слушает CDP-порт, запускается прогрев:

```bash
python -m src.main warmup run 1
```

Пояснение аргументов:

- warmup — режим прогрева аккаунта
- run — запуск сценария
- 1,2,3 — номер сценария

## 📼 Просмотр отчёта (Playwright Trace Viewer)

После выполнения сценария прогрева создаётся trace-архив (`.zip`) — это интерактивный “видео-отчёт” Playwright: шаги, клики, скриншоты, DOM-снимки, консоль и сеть.

Trace сохраняется в:

tests/report/scenario_1_report/traces/<trace_name>.zip

### ▶️ Как открыть trace

```powershell
playwright show-trace tests\report\scenario_1_report\traces\scenario_1_seed1736904352_20260105_111534.zip
```



