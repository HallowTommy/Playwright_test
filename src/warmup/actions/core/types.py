from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple, Dict, Any, Callable
import random


# --- exceptions ---
class NeedLogin(Exception):
    pass

class ActionStalled(Exception):
    pass


# --- Humanization / Runtime flags ---
@dataclass
class HumanBehavior:
    """
    Поведение "человекоподобности" (НЕ антидетект, а UX-поведение).
    Эти параметры должны использоваться только core helper'ами.
    """
    # modes: debug (ультра быстро), fast (быстро), human (обычно), slow (медленнее)
    mode: str = "human"

    # Base speed multiplier (env override friendly)
    speed: float = 1.0

    # Pauses / thinking
    think_pause_chance: float = 0.35
    think_pause_range: Tuple[float, float] = (0.4, 2.0)

    # Micro-noise
    mouse_wander_chance: float = 0.75
    scroll_noise_chance: float = 0.70
    tab_switch_chance: float = 0.20
    backtrack_chance: float = 0.15

    # Typing
    typing_chunked: bool = True
    typing_delay_range_ms: Tuple[int, int] = (35, 120)     # per key delay
    typing_word_pause_range: Tuple[float, float] = (0.02, 0.15)

    # Scroll
    scroll_step_range_px: Tuple[int, int] = (220, 900)
    scroll_steps_range: Tuple[int, int] = (1, 4)

    # Mouse movement
    mouse_move_steps_range: Tuple[int, int] = (3, 18)

    # Timeouts (base, will be jittered)
    nav_timeout_ms: int = 45000
    action_timeout_ms: int = 8000

    # If an action exceeds (max_sec * hard_cap_mult) -> treat as stalled
    hard_cap_mult: float = 1.35

    # Popup handling
    popup_escape_chance: float = 0.35

    # Debug: force more logging/snapshots
    debug_snapshots: bool = False


@dataclass
class ContextFingerprint:
    """
    Параметры контекста Playwright (реальные опции BrowserContext).
    Это НЕ "магические антидетект флаги", это обычные настройки окружения.
    """
    # Locale / timezone / language
    locale: Optional[str] = None              # e.g. "ru-RU"
    timezone_id: Optional[str] = None         # e.g. "Europe/Moscow"
    geolocation: Optional[Dict[str, float]] = None  # {"latitude":..., "longitude":...}
    permissions: Tuple[str, ...] = ()         # e.g. ("geolocation",)

    # Viewport / display
    viewport: Optional[Dict[str, int]] = None         # {"width": 1366, "height": 768}
    device_scale_factor: Optional[float] = None
    is_mobile: Optional[bool] = None
    has_touch: Optional[bool] = None

    # Network / identity
    user_agent: Optional[str] = None
    extra_http_headers: Optional[Dict[str, str]] = None
    color_scheme: Optional[str] = None        # "dark" | "light" | "no-preference"
    reduced_motion: Optional[str] = None      # "reduce" | "no-preference"
    forced_colors: Optional[str] = None       # "active" | "none"

    # Playwright context options (use carefully)
    bypass_csp: Optional[bool] = None
    ignore_https_errors: Optional[bool] = None
    java_script_enabled: Optional[bool] = None

    # Recording
    record_har: bool = False
    record_video: bool = False


@dataclass
class BehaviorProfile:
    seed: int
    day: int = 1
    human: HumanBehavior = field(default_factory=HumanBehavior)
    ctx_fp: ContextFingerprint = field(default_factory=ContextFingerprint)

    # content choices
    search_queries: Tuple[str, ...] = (
        "best note taking apps",
        "productivity tips",
        "gmail tips",
        "news today",
        "lofi music",
    )
    common_queries: Tuple[str, ...] = (
        "gym near me",
        "pharmacy near me",
        "grocery store near me",
        "atm near me",
        "opening hours",
        "phone repair near me",
        "pizza near me",
    )
    youtube_queries: Tuple[str, ...] = (
        "lofi",
        "ambient music",
        "study with me",
        "pomodoro timer",
        "productivity",
    )
    maps_queries: Tuple[str, ...] = (
        "coffee near me",
        "restaurant",
        "park",
        "library",
        "museum",
        "gym",
        "pharmacy",
    )

    def rng(self) -> random.Random:
        return random.Random(self.seed)


@dataclass
class Action:
    name: str
    fn: Callable  # (page, rng, profile, report?) -> page ; report optional
    min_sec: int
    max_sec: int
    tags: Tuple[str, ...] = ()


@dataclass
class StepResult:
    outcome: str  # "ok" | "skip_login" | "error"
    elapsed: float
    meta: Dict[str, Any] = field(default_factory=dict)
