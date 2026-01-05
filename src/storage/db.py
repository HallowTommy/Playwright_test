from __future__ import annotations
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Dict, Any

def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()

def format_date(iso_str: str) -> str:
    """Преобразует ISO дату в читаемый формат YYYY-MM-DD HH:MM:SS"""
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return iso_str

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS phones (
  phone TEXT PRIMARY KEY,
  raw_phone TEXT,
  usage_count INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profiles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  phone TEXT NOT NULL,
  first_name TEXT,
  last_name TEXT,
  full_name TEXT,
  birth_date TEXT,
  email TEXT,
  nickname TEXT,
  password TEXT,
  activation_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY(phone) REFERENCES phones(phone)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_profiles_email
ON profiles(email)
WHERE email IS NOT NULL AND email != '';

CREATE UNIQUE INDEX IF NOT EXISTS ux_profiles_nickname
ON profiles(nickname)
WHERE nickname IS NOT NULL AND nickname != '';
"""

class DB:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    def _ensure_column(self, con: sqlite3.Connection, table: str, col: str, col_def: str) -> None:
        cols = {r["name"] for r in con.execute(f"PRAGMA table_info({table})").fetchall()}
        if col not in cols:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")

    def init(self) -> None:
        """Инициализирует БД с упрощенной схемой"""
        with self.connect() as con:
            con.executescript(SCHEMA)
            # Миграции для старых схем
            try:
                # Миграция profiles: добавляем id если нет
                profile_cols = {r["name"] for r in con.execute("PRAGMA table_info(profiles)").fetchall()}
                if "id" not in profile_cols:
                    con.execute("""
                        CREATE TABLE profiles_new (
                          id INTEGER PRIMARY KEY AUTOINCREMENT,
                          phone TEXT NOT NULL,
                          first_name TEXT,
                          last_name TEXT,
                          full_name TEXT,
                          birth_date TEXT,
                          email TEXT,
                          nickname TEXT,
                          password TEXT,
                          created_at TEXT NOT NULL,
                          updated_at TEXT NOT NULL
                        )
                    """)
                    con.execute("""
                        INSERT INTO profiles_new (phone, first_name, last_name, full_name, birth_date, email, nickname, password, created_at, updated_at)
                        SELECT phone, first_name, last_name, full_name, birth_date, email, nickname, password, created_at, updated_at
                        FROM profiles
                    """)
                    con.execute("DROP TABLE profiles")
                    con.execute("ALTER TABLE profiles_new RENAME TO profiles")
                    con.execute("""
                        CREATE UNIQUE INDEX IF NOT EXISTS ux_profiles_email
                        ON profiles(email)
                        WHERE email IS NOT NULL AND email != ''
                    """)
                    con.execute("""
                        CREATE UNIQUE INDEX IF NOT EXISTS ux_profiles_nickname
                        ON profiles(nickname)
                        WHERE nickname IS NOT NULL AND nickname != ''
                    """)
                
                # Миграция phones: добавляем usage_count и updated_at если нет
                phone_cols = {r["name"] for r in con.execute("PRAGMA table_info(phones)").fetchall()}
                if "usage_count" not in phone_cols:
                    con.execute("ALTER TABLE phones ADD COLUMN usage_count INTEGER NOT NULL DEFAULT 1")
                if "updated_at" not in phone_cols:
                    con.execute("ALTER TABLE phones ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''")
                    # Устанавливаем updated_at для существующих записей
                    con.execute("UPDATE phones SET updated_at = created_at WHERE updated_at = ''")
                
                # Миграция profiles: добавляем activation_id если нет
                profile_cols_after = {r["name"] for r in con.execute("PRAGMA table_info(profiles)").fetchall()}
                if "activation_id" not in profile_cols_after:
                    con.execute("ALTER TABLE profiles ADD COLUMN activation_id TEXT")
            except Exception:
                pass  # Если ошибка - значит уже новая схема

    def upsert_phone(self, phone: str, raw_phone: str) -> int:
        """Добавляет или обновляет номер, возвращает количество использований"""
        with self.connect() as con:
            # Проверяем, существует ли номер
            existing = con.execute("SELECT usage_count FROM phones WHERE phone=?", (phone,)).fetchone()
            if existing:
                # Увеличиваем счетчик
                new_count = existing["usage_count"] + 1
                con.execute(
                    "UPDATE phones SET usage_count=?, updated_at=? WHERE phone=?",
                    (new_count, utcnow(), phone),
                )
                return new_count
            else:
                # Создаем новый
                con.execute(
                    "INSERT INTO phones(phone, raw_phone, usage_count, created_at, updated_at) VALUES(?,?,?,?,?)",
                    (phone, raw_phone, 1, utcnow(), utcnow()),
                )
                return 1
    
    def get_all_phones_sorted(self) -> list[dict]:
        """Получить все номера, отсортированные по дате создания (от старого к новому)"""
        with self.connect() as con:
            rows = con.execute(
                "SELECT phone, usage_count, created_at FROM phones ORDER BY created_at ASC"
            ).fetchall()
            return [dict(r) for r in rows]

    def create_profile(
        self,
        phone: str,
        first_name: str,
        last_name: str,
        full_name: str,
        birth_date: str,
        email: str,
        nickname: str,
        password: str,
        activation_id: str | None = None,
    ) -> None:
        """Создает профиль для номера (можно создавать несколько профилей для одного номера)"""
        with self.connect() as con:
            con.execute(
                "INSERT INTO profiles(phone, first_name, last_name, full_name, birth_date, email, nickname, password, activation_id, created_at, updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (phone, first_name, last_name, full_name, birth_date, email, nickname, password, activation_id, utcnow(), utcnow()),
            )
    
    def get_latest_profile(self) -> dict | None:
        """Получить последний созданный профиль из базы данных"""
        with self.connect() as con:
            profile = con.execute(
                "SELECT phone, first_name, last_name, full_name, birth_date, email, nickname, password, activation_id "
                "FROM profiles ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            if profile:
                return dict(profile)
            return None
    
    def update_profile_activation_id(self, phone: str, activation_id: str) -> bool:
        """Обновить activation_id для последнего профиля указанного номера"""
        with self.connect() as con:
            result = con.execute(
                "UPDATE profiles SET activation_id = ?, updated_at = ? "
                "WHERE phone = ? AND id = (SELECT id FROM profiles WHERE phone = ? ORDER BY created_at DESC LIMIT 1)",
                (activation_id, utcnow(), phone, phone)
            )
            con.commit()
            return result.rowcount > 0

    def export_all(self) -> list[Dict[str, Any]]:
        """Экспортирует все профили"""
        with self.connect() as con:
            rows = con.execute(
                "SELECT phone, full_name, first_name, last_name, birth_date, nickname, email, password, created_at "
                "FROM profiles ORDER BY created_at DESC"
            ).fetchall()
            # Форматируем дату
            result = []
            for r in rows:
                row_dict = dict(r)
                if 'created_at' in row_dict:
                    row_dict['created_at'] = format_date(row_dict['created_at'])
                result.append(row_dict)
            return result

    def history_rows(self) -> list[dict]:
        """Получить историю всех профилей"""
        with self.connect() as con:
            rows = con.execute(
                """
                SELECT
                  created_at,
                  phone,
                  full_name,
                  first_name,
                  last_name,
                  birth_date,
                  nickname,
                  email,
                  password
                FROM profiles
                ORDER BY created_at DESC
                """
            ).fetchall()
            # Преобразуем дату в читаемый формат
            result = []
            for r in rows:
                row_dict = dict(r)
                if 'created_at' in row_dict:
                    row_dict['created_at'] = format_date(row_dict['created_at'])
                result.append(row_dict)
            return result
