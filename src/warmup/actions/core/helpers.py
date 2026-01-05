from __future__ import annotations

import time
import random
from typing import Optional, Tuple

from playwright.sync_api import Page, Error as PWError
from .types import BehaviorProfile


def mode_multiplier(profile: BehaviorProfile) -> float:
    m = (profile.human.mode or "human").lower()
    if m == "debug":
        base = 0.05
    elif m == "fast":
        base = 0.15
    elif m == "slow":
        base = 1.35
    else:
        base = 1.0
    return base * max(0.01, profile.human.speed)


def human_sleep(rng: random.Random, profile: BehaviorProfile, a: float, b: float) -> None:
    t = rng.uniform(a, b) * mode_multiplier(profile)
    if t > 0:
        time.sleep(t)


def jitter_ms(rng: random.Random, profile: BehaviorProfile, ms: int, pct: float = 0.35) -> int:
    delta = int(ms * pct)
    base = max(50, ms + rng.randint(-delta, delta))
    return max(10, int(base * mode_multiplier(profile)))


def typing_delay_ms(rng: random.Random, profile: BehaviorProfile, a: int = 35, b: int = 120) -> int:
    lo, hi = profile.human.typing_delay_range_ms
    a = max(0, a if a else lo)
    b = max(a, b if b else hi)
    return max(0, int(rng.randint(a, b) * mode_multiplier(profile)))


def is_alive(page: Optional[Page]) -> bool:
    try:
        return page is not None and not page.is_closed()
    except Exception:
        return False


def ensure_page(page: Page) -> Page:
    try:
        if is_alive(page):
            return page
    except Exception:
        pass
    ctx = page.context
    for p in ctx.pages:
        if is_alive(p):
            return p
    return ctx.new_page()


def safe_press(page: Page, keys: str) -> Page:
    page = ensure_page(page)
    try:
        page.keyboard.press(keys)
    except PWError:
        page = ensure_page(page)
    return page


def safe_click(locator, rng: random.Random, profile: BehaviorProfile, timeout_ms: Optional[int] = None) -> bool:
    t = timeout_ms if timeout_ms is not None else jitter_ms(rng, profile, profile.human.action_timeout_ms)
    try:
        locator.first.click(timeout=t)
        human_sleep(rng, profile, 0.15, 0.55)
        return True
    except Exception:
        return False


def human_type(locator, text: str, rng: random.Random, profile: BehaviorProfile) -> None:
    if not text:
        return
    if profile.human.typing_chunked:
        for w in text.split(" "):
            locator.type(w, delay=typing_delay_ms(rng, profile))
            locator.type(" ", delay=typing_delay_ms(rng, profile))
            lo, hi = profile.human.typing_word_pause_range
            human_sleep(rng, profile, lo, hi)
    else:
        locator.type(text, delay=typing_delay_ms(rng, profile))


def human_scroll(page: Page, rng: random.Random, profile: BehaviorProfile, steps: Optional[int] = None) -> Page:
    page = ensure_page(page)
    lo, hi = profile.human.scroll_steps_range
    steps = steps if steps is not None else rng.randint(lo, hi)
    for _ in range(steps):
        px = rng.randint(*profile.human.scroll_step_range_px)
        try:
            page.mouse.wheel(0, px)
        except PWError:
            page = ensure_page(page)
        human_sleep(rng, profile, 0.08, 0.35)
    return page


def human_mouse_wander(page: Page, rng: random.Random, profile: BehaviorProfile, moves: Optional[int] = None) -> Page:
    page = ensure_page(page)
    moves = moves if moves is not None else rng.randint(2, 5)
    vp = page.viewport_size or {"width": 1200, "height": 800}
    w, h = vp["width"], vp["height"]
    for _ in range(moves):
        x = rng.randint(20, max(21, w - 20))
        y = rng.randint(20, max(21, h - 20))
        steps = rng.randint(*profile.human.mouse_move_steps_range)
        try:
            page.mouse.move(x, y, steps=steps)
        except PWError:
            page = ensure_page(page)
        human_sleep(rng, profile, 0.05, 0.25)
    return page


def maybe_think(rng: random.Random, profile: BehaviorProfile) -> None:
    if rng.random() < profile.human.think_pause_chance:
        a, b = profile.human.think_pause_range
        human_sleep(rng, profile, a, b)


def back(page: Page, rng: random.Random, profile: BehaviorProfile) -> Page:
    page = ensure_page(page)
    try:
        page.go_back(timeout=jitter_ms(rng, profile, 12000))
        return page
    except Exception:
        # ✅ correct key name for Playwright
        return safe_press(page, "Alt+ArrowLeft")


def maybe_backtrack(page: Page, rng: random.Random, profile: BehaviorProfile) -> Page:
    if rng.random() < profile.human.backtrack_chance:
        page = back(page, rng, profile)
        human_sleep(rng, profile, 0.2, 0.7)
    return page


def maybe_switch_tabs(page: Page, rng: random.Random, profile: BehaviorProfile) -> Page:
    if rng.random() < profile.human.tab_switch_chance:
        ctx = page.context
        newp = ctx.new_page()
        try:
            newp.goto("https://www.google.com", wait_until="domcontentloaded", timeout=jitter_ms(rng, profile, 30000))
            human_sleep(rng, profile, 0.2, 0.6)
        except Exception:
            pass
        finally:
            try:
                newp.close()
            except Exception:
                pass
        human_sleep(rng, profile, 0.15, 0.45)
    return ensure_page(page)


def maybe_micro_noise(page: Page, rng: random.Random, profile: BehaviorProfile) -> Page:
    if rng.random() < profile.human.mouse_wander_chance:
        page = human_mouse_wander(page, rng, profile)
    if rng.random() < profile.human.scroll_noise_chance:
        page = human_scroll(page, rng, profile)
    return page


def detect_login_google(page: Page) -> bool:
    try:
        return "accounts.google.com" in (page.url or "")
    except Exception:
        return True


def detect_login_youtube(page: Page) -> bool:
    # soft heuristic
    try:
        if detect_login_google(page):
            return True
        sign_in = page.locator(
            'a:has-text("Sign in"), tp-yt-paper-button:has-text("Sign in"), '
            'a:has-text("Войти"), tp-yt-paper-button:has-text("Войти")'
        )
        return sign_in.count() > 0
    except Exception:
        return True


# --- consent/popups (shared) ---
CONSENT_SELECTORS = [
    'button:has-text("Accept all")',
    'button:has-text("I agree")',
    'button:has-text("Agree")',
    'button:has-text("Accept")',
    'button:has-text("Reject all")',
    'button:has-text("Принять все")',
    'button:has-text("Принять")',
    'button:has-text("Согласен")',
    'button:has-text("Отклонить все")',
]

POPUP_SELECTORS = [
    'button:has-text("Not now")',
    'button:has-text("No thanks")',
    'button:has-text("Skip")',
    'button:has-text("Later")',
    'button[aria-label="Close"]',
    'button:has-text("Не сейчас")',
    'button:has-text("Нет, спасибо")',
    'button:has-text("Пропустить")',
    'button:has-text("Позже")',
    'button[aria-label="Закрыть"]',
]


def maybe_handle_consent(page: Page, rng: random.Random, profile: BehaviorProfile) -> Page:
    page = ensure_page(page)
    for sel in CONSENT_SELECTORS:
        try:
            loc = page.locator(sel)
            if loc.count() > 0 and safe_click(loc, rng, profile, timeout_ms=jitter_ms(rng, profile, 2000)):
                return page
        except Exception:
            continue

    # iframes
    for frame in page.frames:
        for sel in CONSENT_SELECTORS[:6]:
            try:
                loc = frame.locator(sel)
                if loc.count() > 0:
                    loc.first.click(timeout=jitter_ms(rng, profile, 1500))
                    human_sleep(rng, profile, 0.2, 0.6)
                    return page
            except Exception:
                continue
    return page


def maybe_handle_popups(page: Page, rng: random.Random, profile: BehaviorProfile) -> Page:
    page = ensure_page(page)
    for sel in POPUP_SELECTORS:
        try:
            loc = page.locator(sel)
            if loc.count() > 0:
                safe_click(loc, rng, profile, timeout_ms=jitter_ms(rng, profile, 2500))
                human_sleep(rng, profile, 0.15, 0.5)
        except Exception:
            continue
    if rng.random() < profile.human.popup_escape_chance:
        page = safe_press(page, "Escape")
    return page


def goto(page: Page, url: str, rng: random.Random, profile: BehaviorProfile, timeout_ms: Optional[int] = None) -> Page:
    page = ensure_page(page)
    t = timeout_ms if timeout_ms is not None else jitter_ms(rng, profile, profile.human.nav_timeout_ms)
    page.goto(url, wait_until="domcontentloaded", timeout=t)
    human_sleep(rng, profile, 0.2, 0.7)
    page = maybe_handle_consent(page, rng, profile)
    page = maybe_handle_popups(page, rng, profile)
    return page


def human_clear(locator, rng: random.Random, profile: BehaviorProfile) -> None:
    """
    Human-like clearing of input:
    sometimes Ctrl+A, sometimes shift-select, sometimes backspaces.
    """
    try:
        mode = rng.random()
        # common: Ctrl+A + Backspace
        if mode < 0.65:
            locator.press("Control+A")
            human_sleep(rng, profile, 0.04, 0.18)
            locator.press("Backspace")
            human_sleep(rng, profile, 0.03, 0.12)
            return

        # alternative: Home + Shift+End + Backspace
        if mode < 0.85:
            locator.press("Home")
            human_sleep(rng, profile, 0.03, 0.12)
            locator.press("Shift+End")
            human_sleep(rng, profile, 0.04, 0.14)
            locator.press("Backspace")
            human_sleep(rng, profile, 0.03, 0.12)
            return

        # "messy" backspaces
        # (works if field already focused)
        n = rng.randint(4, 18)
        for _ in range(n):
            locator.press("Backspace")
            human_sleep(rng, profile, 0.01, 0.05)

    except Exception:
        # don't fail action just because clearing failed
        return


def _typo_variant(rng: random.Random, ch: str) -> str:
    """
    Simple typo generator:
    - duplicate char
    - skip char (handled by caller)
    - random neighbor-ish: for latin letters we can do a cheap approximation
    """
    if not ch:
        return ch
    r = rng.random()
    if r < 0.40:
        return ch + ch  # duplicate
    if r < 0.70:
        # random ascii letter, cheap "wrong key"
        import string
        return rng.choice(string.ascii_lowercase)
    return ch


def human_type_with_typos(
    locator,
    text: str,
    rng: random.Random,
    profile: BehaviorProfile,
    *,
    typo_chance: float = 0.035,
    fix_chance: float = 0.92,
    sensitive: bool = False,
) -> None:
    """
    Type like a human: occasional typos + corrections.
    Use sensitive=True for passwords/OTP/email -> disables typos.
    """
    if not text:
        return

    if sensitive:
        human_type(locator, text, rng, profile)
        return

    # type char-by-char to allow typos
    for ch in text:
        # optional pause between words
        if ch == " ":
            locator.type(" ", delay=typing_delay_ms(rng, profile))
            lo, hi = profile.human.typing_word_pause_range
            human_sleep(rng, profile, lo, hi)
            continue

        if rng.random() < typo_chance:
            # introduce typo
            variant = _typo_variant(rng, ch)
            locator.type(variant, delay=typing_delay_ms(rng, profile))

            # maybe fix it
            if rng.random() < fix_chance:
                # short "noticed" delay
                human_sleep(rng, profile, 0.05, 0.25)
                # if duplicated or wrong letter(s) -> backspace 1-2 times
                bs = 2 if len(variant) > 1 else 1
                for _ in range(bs):
                    locator.press("Backspace")
                    human_sleep(rng, profile, 0.02, 0.07)
                # type correct char
                locator.type(ch, delay=typing_delay_ms(rng, profile))
            continue

        locator.type(ch, delay=typing_delay_ms(rng, profile))


def human_hover_locator(locator, rng: random.Random, profile: BehaviorProfile) -> bool:
    """
    Hover a locator like a human: scroll into view + hover + tiny pause.
    """
    try:
        loc = locator.first
        loc.scroll_into_view_if_needed(timeout=jitter_ms(rng, profile, 1500))
        human_sleep(rng, profile, 0.03, 0.15)
        loc.hover(timeout=jitter_ms(rng, profile, 1500))
        human_sleep(rng, profile, 0.06, 0.22)
        return True
    except Exception:
        return False


def human_click(locator, rng: random.Random, profile: BehaviorProfile, timeout_ms: Optional[int] = None) -> bool:
    """
    Click with human-ish pre-hover and hesitation.
    """
    # sometimes hover first
    if rng.random() < 0.70:
        human_hover_locator(locator, rng, profile)
    # hesitation
    human_sleep(rng, profile, 0.03, 0.22)
    return safe_click(locator, rng, profile, timeout_ms=timeout_ms)


def maybe_read_pause(rng: random.Random, profile: BehaviorProfile, *, a: float = 0.2, b: float = 1.4, chance: float = 0.55) -> None:
    """
    Pause as if reading content.
    """
    if rng.random() < chance:
        human_sleep(rng, profile, a, b)
