from __future__ import annotations

import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

from playwright.sync_api import Page
from rich import print

from ..actions.core.types import (
    BehaviorProfile,
    HumanBehavior,
    ContextFingerprint,
    Action,
)
from ..actions.core.report import Report
from ..actions.core.runner import run_action
from ..actions.core.chooser import (
    ChooseState,
    decay_repeats,
    apply_runtime_rules,
    novelty_bonus,
    jitter_weights,
    weighted_choice,
)

# ✅ only action for now
from ..actions.google_search.search_physical_scroll import run as act_search_physical

State = str


# -------------------------
# env helpers
# -------------------------
def _env_float(name: str, default: float) -> float:
    v = os.getenv(name, "").strip()
    if not v:
        return default
    try:
        return float(v)
    except Exception:
        return default


def _env_int(name: str, default: int) -> int:
    v = os.getenv(name, "").strip()
    if not v:
        return default
    try:
        return int(v)
    except Exception:
        return default


def _env_str(name: str, default: str) -> str:
    v = os.getenv(name, "").strip()
    return v if v else default


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.getenv(name, "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "y", "on")


def _env_tuple2_float(name: str, default: Tuple[float, float]) -> Tuple[float, float]:
    v = os.getenv(name, "").strip()
    if not v:
        return default
    try:
        a, b = v.split(",")
        return float(a), float(b)
    except Exception:
        return default


def _env_tuple2_int(name: str, default: Tuple[int, int]) -> Tuple[int, int]:
    v = os.getenv(name, "").strip()
    if not v:
        return default
    try:
        a, b = v.split(",")
        return int(a), int(b)
    except Exception:
        return default


# -------------------------
# profile builder
# -------------------------
def _build_profile(seed: int) -> BehaviorProfile:
    """
    Central place to tune all "human flags" defined in core.types.HumanBehavior.
    Everything is overridable by env vars.
    """

    # global run mode
    mode = _env_str("WARMUP_MODE", "human").lower()  # debug|fast|human|slow
    speed = _env_float("WARMUP_SPEED", 1.0)
    day = _env_int("WARMUP_DAY", 1)

    human = HumanBehavior(
        mode=mode,
        speed=speed,

        # pauses / thinking
        think_pause_chance=_env_float("WARMUP_THINK_CHANCE", 0.35),
        think_pause_range=_env_tuple2_float("WARMUP_THINK_RANGE", (0.4, 2.0)),

        # micro-noise
        mouse_wander_chance=_env_float("WARMUP_MOUSE_WANDER_CHANCE", 0.75),
        scroll_noise_chance=_env_float("WARMUP_SCROLL_NOISE_CHANCE", 0.70),
        tab_switch_chance=_env_float("WARMUP_TAB_SWITCH_CHANCE", 0.20),
        backtrack_chance=_env_float("WARMUP_BACKTRACK_CHANCE", 0.15),

        # typing
        typing_chunked=_env_bool("WARMUP_TYPING_CHUNKED", True),
        typing_delay_range_ms=_env_tuple2_int("WARMUP_TYPING_DELAY_MS", (35, 120)),
        typing_word_pause_range=_env_tuple2_float("WARMUP_TYPING_WORD_PAUSE", (0.02, 0.15)),

        # scroll
        scroll_step_range_px=_env_tuple2_int("WARMUP_SCROLL_STEP_PX", (220, 900)),
        scroll_steps_range=_env_tuple2_int("WARMUP_SCROLL_STEPS", (1, 4)),

        # mouse movement
        mouse_move_steps_range=_env_tuple2_int("WARMUP_MOUSE_MOVE_STEPS", (3, 18)),

        # timeouts (base, jittered in helpers)
        nav_timeout_ms=_env_int("WARMUP_NAV_TIMEOUT_MS", 45000),
        action_timeout_ms=_env_int("WARMUP_ACTION_TIMEOUT_MS", 8000),

        # stall logic
        hard_cap_mult=_env_float("WARMUP_HARD_CAP_MULT", 1.35),

        # popups
        popup_escape_chance=_env_float("WARMUP_POPUP_ESCAPE_CHANCE", 0.35),

        # debug
        debug_snapshots=_env_bool("WARMUP_DEBUG_SNAPSHOTS", False),
    )

    # context fingerprint (for future use if you start creating contexts yourself)
    ctx_fp = ContextFingerprint(
        locale=os.getenv("WARMUP_LOCALE") or None,
        timezone_id=os.getenv("WARMUP_TZ") or None,
        # geolocation / viewport / ua etc can be added later
    )

    return BehaviorProfile(seed=seed, day=day, human=human, ctx_fp=ctx_fp)


# -------------------------
# registry + transitions
# -------------------------
def _actions_registry() -> Dict[State, Action]:
    # ✅ only one action for now
    return {
        "search": Action(
            name="Search: physical objects (scroll-only)",
            fn=act_search_physical,
            min_sec=90,
            max_sec=240,
            tags=("google", "search"),
        ),
    }


def _transitions() -> Dict[State, List[Tuple[State, float]]]:
    # ✅ loop search while we are testing only it
    return {
        "start": [("search", 1.0)],
        "search": [("search", 1.0)],
    }


# -------------------------
# scenario
# -------------------------
def scenario_1(page: Page, seed: int | None = None) -> None:
    if seed is None:
        seed = time.time_ns() & 0xFFFFFFFF

    profile = _build_profile(seed)
    rng = profile.rng()

    # session budget (keep your original)
    min_sec = _env_int("WARMUP_MIN_SESSION_SEC", 2 * 60)
    max_sec = _env_int("WARMUP_MAX_SESSION_SEC", 3 * 60)
    session_sec = rng.randint(min_sec, max_sec)
    deadline = time.time() + session_sec

    # report dirs
    base_dir = Path("tests") / "report" / "scenario_1_report"
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name = f"scenario_1_seed{seed}_{run_id}"

    report = Report(base_dir=base_dir, run_name=run_name)
    report.start_trace(page)

    print(
        f"[dim]Day session | seed={seed} | budget={session_sec//60}m{session_sec%60:02d}s "
        f"| mode={profile.human.mode} | speed={profile.human.speed}[/dim]"
    )
    print(f"[dim]Trace -> {report.trace_path}[/dim]")
    print(f"[dim]JSONL  -> {report.jsonl_path}[/dim]")

    actions = _actions_registry()
    transitions = _transitions()

    st = ChooseState()
    current: State = "start"
    history: List[State] = []
    fail_streak = 0

    # rough action cost for time budget heuristics (seconds)
    action_costs = {k: actions[k].min_sec for k in actions}

    try:
        while time.time() < deadline:
            time_left = deadline - time.time()
            if time_left < 60:
                break

            cand = transitions.get(current, transitions["start"])
            cand = decay_repeats(cand, history)
            cand = novelty_bonus(cand, history)
            cand = jitter_weights(rng, cand, pct=0.08)
            cand = apply_runtime_rules(cand, st=st, time_left_sec=time_left, action_costs=action_costs)

            next_state = weighted_choice(rng, cand)
            action = actions.get(next_state) or actions["search"]

            page, res = run_action(
                page=page,
                rng=rng,
                profile=profile,
                action=action,
                report=report,
                deadline_ts=deadline,
                retries=_env_int("WARMUP_ACTION_RETRIES", 2),
            )

            if res.outcome == "error":
                fail_streak += 1
            else:
                fail_streak = 0

            # fallback: if we keep failing, just try search again once more
            if fail_streak >= 2:
                report.warn("fallback", "fail streak -> force search", url=getattr(page, "url", None))
                page, _ = run_action(
                    page=page,
                    rng=rng,
                    profile=profile,
                    action=actions["search"],
                    report=report,
                    deadline_ts=deadline,
                    retries=1,
                )
                fail_streak = 0
                current = "search"
                history.append("search")
                history = history[-10:]
                continue

            history.append(next_state)
            history = history[-10:]
            st.history = history
            st.tick()
            current = next_state

        report.info("scenario_1", "finished", url=getattr(page, "url", None), history=history)

    finally:
        report.stop_trace(page)
        print("[green]✓ scenario_1 finished[/green]")
        print(f"[green]✓ Trace saved:[/green] {report.trace_path}")
        print(f"[green]✓ Report saved:[/green] {report.jsonl_path}")
        print(f"[dim]Open trace:[/dim] playwright show-trace {report.trace_path}")
