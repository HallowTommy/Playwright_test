from __future__ import annotations

import os
import time
import random
import json
from dataclasses import dataclass
from typing import Optional, Dict, Any

import requests
from rich import print
from dotenv import load_dotenv

load_dotenv()


# --- Exceptions ---------------------------------------------------------------

class HeroSMSError(RuntimeError):
    """Base error for Hero-SMS client."""


class HeroSMSAuthError(HeroSMSError):
    """BAD_KEY / authorization related."""


class HeroSMSNoMoneyError(HeroSMSError):
    """NO_MONEY / insufficient balance."""


class HeroSMSNoNumbersError(HeroSMSError):
    """NO_NUMBERS / no available numbers."""


class HeroSMSBadParamsError(HeroSMSError):
    """BAD_* params like BAD_SERVICE/BAD_COUNTRY/etc."""


class HeroSMSUnexpectedResponse(HeroSMSError):
    """Unexpected response format."""


# --- Helpers -----------------------------------------------------------------

def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


def _looks_like_price(s: str) -> bool:
    try:
        float(s)
        return True
    except Exception:
        return False


def _raise_for_api_error(text: str) -> None:
    """
    Common SMS-Activate style errors:
    BAD_KEY, NO_MONEY, NO_NUMBERS, BAD_SERVICE, BAD_COUNTRY, ERROR_SQL, etc.
    """
    t = (text or "").strip()

    if t in {"BAD_KEY", "ERROR_KEY"}:
        raise HeroSMSAuthError("Hero-SMS: неверный API ключ (BAD_KEY).")

    if t in {"NO_MONEY", "NO_BALANCE"}:
        raise HeroSMSNoMoneyError("Hero-SMS: недостаточно средств (NO_MONEY).")

    if t in {"NO_NUMBERS", "NO_NUMBER"}:
        raise HeroSMSNoNumbersError("Hero-SMS: нет доступных номеров (NO_NUMBERS).")

    if t.startswith("BAD_"):
        raise HeroSMSBadParamsError(f"Hero-SMS: ошибка параметров ({t}).")

    if t.startswith("ERROR") or t.startswith("WRONG") or t in {"BANNED", "ACCOUNT_BLOCKED"}:
        raise HeroSMSError(f"Hero-SMS: ошибка API: {t}")


# --- Client -------------------------------------------------------------------

@dataclass
class HeroSMSClient:
    """
    Hero-SMS client (SMS-Activate compatible).

    Base:
      https://hero-sms.com/stubs/handler_api.php?action=...&api_key=...

    Notes:
      - Responses are TEXT (some actions return JSON-as-text).
      - "test_mode" is kept only for CLI compatibility; real API doesn't use it here.
    """

    api_key: Optional[str] = None
    dry_run: bool = False
    test_mode: bool = False
    timeout: int = 30
    max_retries: int = 2
    retry_backoff: float = 1.0
    debug: bool = True

    BASE_URL: str = "https://hero-sms.com/stubs/handler_api.php"

    def __post_init__(self) -> None:
        if not self.api_key:
            self.api_key = os.getenv("HEROSMS_API_KEY", "")

        if not self.dry_run and not self.api_key:
            raise ValueError(
                "API ключ обязателен! Установите HEROSMS_API_KEY в .env "
                "или передайте api_key. Для разработки используйте --dry-run."
            )

        if self.dry_run:
            print("[yellow]⚠️  DRY-RUN: ответы будут симулированы, реальные запросы не выполняются[/yellow]")

    # --- Low-level request ----------------------------------------------------

    def _request(self, action: str, params: Optional[Dict[str, Any]] = None) -> str:
        params = params or {}

        if self.dry_run:
            return self._mock(action, params)

        q: Dict[str, Any] = {"action": action, "api_key": self.api_key}
        q.update(params)

        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 2):
            try:
                if self.debug:
                    safe_q = dict(q)
                    safe_q["api_key"] = _mask_key(str(safe_q.get("api_key", "")))
                    print(f"[dim]→ GET {self.BASE_URL} params={safe_q}[/dim]")

                r = requests.get(self.BASE_URL, params=q, timeout=self.timeout)

                if self.debug:
                    print(f"[dim]← {r.status_code} {r.reason}[/dim]")

                r.raise_for_status()
                text = (r.text or "").strip()

                if self.debug:
                    preview = text if len(text) <= 200 else text[:200] + "…"
                    print(f"[dim]← body: {preview}[/dim]")

                _raise_for_api_error(text)
                return text

            except (requests.RequestException, HeroSMSError) as e:
                last_exc = e
                # semantic API errors don't need retries
                if isinstance(e, HeroSMSError) and not isinstance(e, requests.RequestException):
                    raise
                if attempt <= self.max_retries:
                    time.sleep(self.retry_backoff * attempt)
                    continue
                break

        raise HeroSMSError(f"Hero-SMS request failed after retries: {last_exc}") from last_exc

    # --- Public API -----------------------------------------------------------

    def get_balance(self) -> float:
        text = self._request("getBalance")
        if text.startswith("ACCESS_BALANCE:"):
            _, amount = text.split(":", 1)
            try:
                return float(amount)
            except ValueError:
                raise HeroSMSUnexpectedResponse(f"Не удалось распарсить баланс: {text}")
        raise HeroSMSUnexpectedResponse(f"Неожиданный ответ getBalance: {text}")

    def get_countries(self) -> Dict[str, Any]:
        text = self._request("getCountries")
        try:
            return json.loads(text)
        except Exception as e:
            raise HeroSMSUnexpectedResponse(f"Неожиданный ответ getCountries: {text[:2000]}") from e

    def get_services(self) -> Any:
        text = self._request("getServicesList")
        if text.startswith("{") or text.startswith("["):
            try:
                return json.loads(text)
            except Exception:
                return text
        return text

    def get_prices(self, country_id: int, service: str) -> Dict[str, Any]:
        """
        action=getPrices&country=...&service=...

        Реальный формат Hero-SMS (как в твоём логе):
          {"43":{"go":{"cost":0.35,"count":1184,"physicalCount":1134}}}

        Иногда у SMS-activate совместимых API бывает "карта цен":
          {"43":{"go":{"0.12":5,"0.15":10}}}
        """
        text = self._request("getPrices", {"country": country_id, "service": service})
        try:
            return json.loads(text)
        except Exception as e:
            raise HeroSMSUnexpectedResponse(f"Неожиданный ответ getPrices: {text[:2000]}") from e

    def _debug_prices(self, country_id: int, service: str, data: Dict[str, Any]) -> None:
        """
        Pretty debug print for getPrices response (transparent pricing).
        """
        if not self.debug:
            return

        country_key = str(country_id)

        # Hero-SMS format: {"43":{"go":{"cost":0.35,"count":1184,"physicalCount":1134}}}
        try:
            by_country = data.get(country_key) if isinstance(data, dict) else None
            by_service = by_country.get(service) if isinstance(by_country, dict) else None
            if isinstance(by_service, dict) and "cost" in by_service:
                cost = by_service.get("cost")
                count = by_service.get("count")
                physical = by_service.get("physicalCount")
                extra = f", physicalCount={physical}" if physical is not None else ""
                print(f"[dim]prices: country={country_id}, service={service}, cost={cost}, count={count}{extra}[/dim]")
                return
        except Exception:
            pass

        # Fallback: price map
        price_map = None

        if isinstance(data, dict) and country_key in data:
            by_country = data.get(country_key)
            if isinstance(by_country, dict) and isinstance(by_country.get(service), dict):
                price_map = by_country.get(service)

        if price_map is None and isinstance(data, dict) and isinstance(data.get(service), dict):
            price_map = data.get(service)

        if price_map is None and isinstance(data, dict) and data and all(isinstance(k, str) and _looks_like_price(k) for k in data.keys()):
            price_map = data

        if isinstance(price_map, dict):
            items = []
            for k, v in price_map.items():
                try:
                    p = float(k)
                    c = int(v)
                except Exception:
                    continue
                items.append((p, c))
            items.sort(key=lambda x: x[0])
            preview = ", ".join([f"{p}:{c}" for p, c in items[:5]])
            print(f"[dim]prices: country={country_id}, service={service}, cheapest_map=[{preview}][/dim]")
            return

        # Unknown format
        raw = str(data)
        raw = raw if len(raw) <= 200 else raw[:200] + "…"
        print(f"[dim]prices: country={country_id}, service={service}, raw={raw}[/dim]")

    def pick_cheapest_price(self, country_id: int, service: str) -> Optional[float]:
        """
        Возвращает минимальную доступную цену.
        Для Hero-SMS это обычно поле `cost`, при условии что `count > 0`.
        """
        data = self.get_prices(country_id=country_id, service=service)
        self._debug_prices(country_id, service, data)

        country_key = str(country_id)

        # 1) HERO-SMS format: {"43":{"go":{"cost":0.35,"count":1184}}}
        try:
            if isinstance(data, dict) and country_key in data:
                by_country = data.get(country_key)
                if isinstance(by_country, dict) and service in by_country:
                    by_service = by_country.get(service)
                    if isinstance(by_service, dict) and "cost" in by_service:
                        count_raw = by_service.get("count", 0)
                        try:
                            count = int(count_raw)
                        except Exception:
                            count = 0
                        if count > 0:
                            return float(by_service["cost"])
                        return None
        except Exception:
            pass

        # 2) Fallback: price map (price -> count)
        price_map: Optional[Dict[str, Any]] = None

        if isinstance(data, dict) and country_key in data:
            by_country = data.get(country_key)
            if isinstance(by_country, dict):
                by_service = by_country.get(service)
                if isinstance(by_service, dict):
                    price_map = by_service

        if price_map is None and isinstance(data, dict) and service in data and isinstance(data[service], dict):
            price_map = data[service]

        if price_map is None and isinstance(data, dict) and data and all(_looks_like_price(k) for k in data.keys()):
            price_map = data

        if not isinstance(price_map, dict):
            return None

        candidates: list[float] = []
        for price_str, count in price_map.items():
            try:
                p = float(price_str)
                c = int(count)
            except Exception:
                continue
            if c > 0:
                candidates.append(p)

        return min(candidates) if candidates else None

    def get_number(self, country_id: int, service: str, max_price: Optional[float] = None) -> Dict[str, Any]:
        """
        action=getNumber
        Params: country=<id>, service=<code>, [maxPrice=<float>]
        Response: ACCESS_NUMBER:<activation_id>:<number>
        """
        params: Dict[str, Any] = {"country": country_id, "service": service}
        if max_price is not None:
            params["maxPrice"] = max_price

        text = self._request("getNumber", params)
        if text.startswith("ACCESS_NUMBER:"):
            parts = text.split(":")
            if len(parts) >= 3:
                act_id = parts[1]
                number = parts[2]
                return {"id": act_id, "number": number, "country": country_id, "service": service}
        raise HeroSMSUnexpectedResponse(f"Неожиданный ответ getNumber: {text}")

    def get_number_cheapest(self, country_id: int, service: str, retries: int = 3) -> Dict[str, Any]:
        """
        Всегда пытается купить "самый дешёвый" пул:
          getPrices -> cheapest(cost) -> getNumber(maxPrice=cheapest)

        Если дешёвый пул кончился в гонке — может вернуться NO_NUMBERS:
        пересчитаем и повторим.
        """
        last_exc: Optional[Exception] = None

        for attempt in range(1, retries + 1):
            try:
                cheapest = self.pick_cheapest_price(country_id=country_id, service=service)
                if cheapest is None:
                    if self.debug:
                        print("[yellow]Не удалось определить cheapest price через getPrices — беру обычный getNumber[/yellow]")
                    return self.get_number(country_id=country_id, service=service)

                if self.debug:
                    print(f"[cyan]Cheapest price: {cheapest} → getNumber(maxPrice={cheapest})[/cyan]")

                return self.get_number(country_id=country_id, service=service, max_price=cheapest)

            except HeroSMSNoNumbersError as e:
                last_exc = e
                if attempt < retries:
                    time.sleep(0.35 * attempt)
                    continue
                raise

            except Exception as e:
                last_exc = e
                raise

        raise HeroSMSError(f"Не удалось получить номер cheapest-логикой: {last_exc}") from last_exc

    def get_status(self, activation_id: str) -> str:
        return self._request("getStatus", {"id": activation_id})

    def get_sms_code(self, activation_id: str) -> Optional[str]:
        status = self.get_status(activation_id)
        if status.startswith("STATUS_OK:"):
            return status.split(":", 1)[1].strip() or None
        return None

    def set_status(self, activation_id: str, status: int) -> str:
        return self._request("setStatus", {"id": activation_id, "status": status})

    # --- DRY RUN mock ---------------------------------------------------------

    def _mock(self, action: str, params: Dict[str, Any]) -> str:
        if self.debug:
            safe = dict(params)
            print(f"[dim]🔧 [MOCK] action={action} params={safe}[/dim]")

        time.sleep(0.05)

        if action == "getBalance":
            return "ACCESS_BALANCE:100.50"

        if action == "getCountries":
            return json.dumps({
                "43": {"id": 43, "rus": "Германия", "eng": "Germany", "visible": 1},
                "49": {"id": 49, "rus": "Латвия", "eng": "Latvia", "visible": 1},
            })

        if action == "getServicesList":
            return "go,tg,wa"

        if action == "getPrices":
            country = int(params.get("country", 43))
            service = str(params.get("service", "go"))
            # Mock REAL Hero-SMS format:
            return json.dumps({str(country): {service: {"cost": 0.35, "count": 12, "physicalCount": 10}}})

        if action == "getNumber":
            country = int(params.get("country", 43))
            service = str(params.get("service", "go"))

            seed = int(time.time() * 1000) + hash(f"{country}:{service}")
            random.seed(seed)

            if country == 43:  # Германия
                mobile_prefix = random.choice(["151", "152", "153", "155", "156", "157", "159", "160"])
                rest = random.randint(1000000, 9999999)
                number = f"49{mobile_prefix}{rest}"
            else:
                rest = random.randint(100000000, 999999999)
                number = f"{country}{rest}"

            act_id = f"mock{int(time.time())}{random.randint(1000,9999)}"
            return f"ACCESS_NUMBER:{act_id}:{number}"

        if action == "getStatus":
            if random.random() < 0.6:
                return "STATUS_WAIT_CODE"
            return f"STATUS_OK:{random.randint(100000, 999999)}"

        if action == "setStatus":
            return "ACCESS_READY"

        return "OK"
