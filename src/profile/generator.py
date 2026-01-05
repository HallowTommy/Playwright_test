from __future__ import annotations

import hashlib
import hmac
import random
import re
from dataclasses import dataclass
from typing import Optional, Literal
from datetime import date

from faker import Faker

Gender = Literal["male", "female"]

EN_LOCALES = ["en_US", "en_GB"]
RESERVED_USERNAMES = {"abuse", "postmaster"}


@dataclass(frozen=True)
class GeneratedProfile:
    first_name: str
    last_name: str
    full_name: str
    birth_date: str  # YYYY-MM-DD
    email: str
    nickname: str
    password: str


def normalize_phone(phone: str) -> str:
    s = phone.strip().replace(" ", "").replace("-", "")
    if s.startswith("00"):
        s = "+" + s[2:]
    s = re.sub(r"[^\d+]", "", s)
    if "+" in s and not s.startswith("+"):
        s = "+" + re.sub(r"[^\d]", "", s)
    
    # Если номер начинается с цифры и длинный (>=10 цифр), добавляем "+"
    # Это для международных номеров без префикса
    if not s.startswith("+") and len(re.sub(r"[^\d]", "", s)) >= 10:
        # Проверяем, не является ли это локальным номером (начинается с 0)
        if not s.startswith("0"):
            s = "+" + s
    
    return s


def stable_seed(phone_norm: str, secret: str) -> int:
    digest = hmac.new(secret.encode("utf-8"), phone_norm.encode("utf-8"), hashlib.sha256).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def stable_hex(phone_norm: str, secret: str, n: int = 12) -> str:
    return hmac.new(secret.encode("utf-8"), phone_norm.encode("utf-8"), hashlib.sha256).hexdigest()[:n]


def atoms(s: str) -> str:
    a = str(s).lower()
    a = re.sub(r"[^a-z0-9]", "", a)
    return a or "user"


def clean_username(u: str) -> str:
    u = u.lower()
    u = re.sub(r"[^a-z0-9]", "", u)  # точки выкидываем полностью
    return u


def ensure_username_rules(u: str, fallback_digits: str) -> str:
    u = clean_username(u)
    if not u:
        u = "user"

    if u in RESERVED_USERNAMES:
        u = f"{u}{fallback_digits}"

    # длина 6–30
    if len(u) < 6:
        u = (u + fallback_digits + "123456")[:6]
    if len(u) > 30:
        u = u[:30]

    u = clean_username(u)
    if len(u) < 6:
        u = (u + "123456")[:6]

    if u in RESERVED_USERNAMES:
        u = (u + fallback_digits)[:30]

    return u


def faker_name(fake: Faker, gender: Gender) -> tuple[str, str]:
    if gender == "male":
        fn = getattr(fake, "first_name_male", None)
        ln = getattr(fake, "last_name", None)
    else:
        fn = getattr(fake, "first_name_female", None)
        ln = getattr(fake, "last_name", None)

    first = fn() if callable(fn) else fake.first_name()
    last = ln() if callable(ln) else fake.last_name()

    first = re.sub(r"\s+", " ", str(first)).strip()[:40]
    last = re.sub(r"\s+", " ", str(last)).strip()[:40]
    return first, last


def pick_word(fake: Faker, rng: random.Random) -> str:
    candidates: list[str] = []

    candidates.append(str(fake.word()))
    try:
        candidates.extend([str(w) for w in fake.words(nb=rng.choice([2, 3, 4]))])
    except Exception:
        pass

    candidates.append(str(fake.color_name()))
    candidates.append(str(fake.job()))
    candidates.append(str(fake.company()))
    candidates.append(str(fake.catch_phrase()))

    cleaned = [atoms(c) for c in candidates]
    cleaned = [w for w in cleaned if w and w != "user"]

    w = rng.choice(cleaned) if cleaned else "user"

    # делаем слово короче (2..6) чтобы итог был компактным
    if len(w) > 6:
        w = w[: rng.randint(3, 6)]
    elif len(w) < 2:
        w = "user"
    return w


def sep_digit_letter(rng: random.Random, suffix_digits: str) -> str:
    digit = rng.choice(suffix_digits)
    letter = rng.choice("abcdefghijklmnopqrstuvwxyz")
    return f"{digit}{letter}"


def build_wordy_id(
    rng: random.Random,
    fake: Faker,
    *,
    suffix_digits: str,
    target_min: int,
    target_max: int,
) -> str:
    n_words = rng.choice([2, 3, 2, 3])
    words = [pick_word(fake, rng) for _ in range(n_words)]

    s = words[0]
    for w in words[1:]:
        s += sep_digit_letter(rng, suffix_digits) + w

    # хвост: 1–3 цифры (чуть-чуть)
    tail_len = rng.randint(1, 3)
    tail = "".join(rng.choice(suffix_digits) for _ in range(tail_len))
    s = s + tail

    s = clean_username(s)

    if len(s) > target_max:
        s = clean_username(s[:target_max])

    while len(s) < target_min:
        if rng.random() < 0.6:
            s += sep_digit_letter(rng, suffix_digits)
        else:
            s += rng.choice("abcdefghijklmnopqrstuvwxyz0123456789")
        s = clean_username(s)
        if len(s) > target_max:
            s = clean_username(s[:target_max])
            break

    return ensure_username_rules(s, suffix_digits)


def build_password(rng: random.Random, *, length: int = 16) -> str:
    if length < 12:
        length = 12

    lowers = "abcdefghijklmnopqrstuvwxyz"
    uppers = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    digits = "0123456789"
    symbols = "!@#$%^&*()_+=[]{}:,.?~"

    chars = [
        rng.choice(lowers),
        rng.choice(uppers),
        rng.choice(digits),
        rng.choice(symbols),
    ]
    all_chars = lowers + uppers + digits + symbols
    chars += [rng.choice(all_chars) for _ in range(length - len(chars))]
    rng.shuffle(chars)

    pwd = "".join(chars)
    if pwd.lower().startswith("password"):
        rng2 = random.Random(rng.random())
        return build_password(rng2, length=length)
    return pwd


def build_birth_date(rng: random.Random, *, min_age: int = 21, max_age: int = 55) -> str:
    """
    Генерим дату рождения так, чтобы возраст был 21+.
    Чтобы всегда было валидно — day 1..28.
    """
    today = date.today()
    max_year = today.year - min_age
    min_year = today.year - max_age

    year = rng.randint(min_year, max_year)
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    return f"{year:04d}-{month:02d}-{day:02d}"


def generate(
    phone: str,
    *,
    secret: str,
    gender: Optional[Gender] = None,
    variant: int = 0,
) -> GeneratedProfile:
    phone_n = normalize_phone(phone)
    seed = stable_seed(phone_n, secret)

    rng_name = random.Random(seed + 5000003 * int(variant) + 33)  # зависит от variant
    rng_nick = random.Random(seed + 1000003 * int(variant) + 11)
    rng_email = random.Random(seed + 1000003 * int(variant) + 22)
    rng_pass = random.Random(seed + 2000003 * int(variant) + 424242)
    rng_dob = random.Random(seed + 333333 + 7000003 * int(variant))  # зависит от variant

    if gender is None:
        gender = "female" if rng_name.random() < 0.5 else "male"

    loc = rng_name.choice(EN_LOCALES)
    fake = Faker(loc)
    fake.seed_instance(seed + 5000003 * int(variant) + 33)  # зависит от variant

    first, last = faker_name(fake, gender)

    suf_hex = stable_hex(phone_n, secret, n=12)
    base_digits = int(suf_hex[:6], 16) % 10000
    suffix_digits = str((base_digits + 9973 * int(variant)) % 10000).zfill(4)

    nickname = build_wordy_id(
        rng_nick,
        fake,
        suffix_digits=suffix_digits,
        target_min=8,
        target_max=12,
    )

    email_local = build_wordy_id(
        rng_email,
        fake,
        suffix_digits=suffix_digits,
        target_min=10,
        target_max=14,
    )

    birth_date = build_birth_date(rng_dob, min_age=21, max_age=55)

    email = email_local.lower()
    password = build_password(rng_pass, length=16)

    return GeneratedProfile(
        first_name=first,
        last_name=last,
        full_name=f"{first} {last}",
        birth_date=birth_date,
        email=email,
        nickname=nickname,
        password=password,
    )
