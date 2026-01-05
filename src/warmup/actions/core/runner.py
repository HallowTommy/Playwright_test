from __future__ import annotations

import time
import random
import inspect
from typing import Tuple

from playwright.sync_api import Page, TimeoutError, Error as PWError

from .types import Action, BehaviorProfile, NeedLogin, ActionStalled, StepResult
from .helpers import ensure_page, maybe_think, maybe_micro_noise, maybe_backtrack, maybe_switch_tabs
from .helpers import jitter_ms
from .report import Report


def _call_action_fn(action: Action, page: Page, rng: random.Random, profile: BehaviorProfile, report: Report) -> Page:
    """
    Backward compatible:
    - old actions: fn(page, rng, profile) -> Page
    - new actions: fn(page, rng, profile, report) -> Page
    """
    fn = action.fn

    # Fast path: try signature-based dispatch
    try:
        params = inspect.signature(fn).parameters
        # allow (page, rng, profile, report) and also (page, rng, profile, report=...)
        if len(params) >= 4:
            return fn(page, rng, profile, report)
        return fn(page, rng, profile)
    except Exception:
        # Fallback: try 4-args first, then 3-args
        try:
            return fn(page, rng, profile, report)
        except TypeError:
            return fn(page, rng, profile)


def run_action(
    page: Page,
    rng: random.Random,
    profile: BehaviorProfile,
    action: Action,
    report: Report,
    deadline_ts: float,
    retries: int = 2,
) -> Tuple[Page, StepResult]:
    """
    Единый раннер для всех actions:
    - before/after human hooks (think/noise/backtrack)
    - retries
    - dumps on error
    - ✅ passes report into action if supported
    """
    if time.time() > deadline_ts:
        return ensure_page(page), StepResult(outcome="ok", elapsed=0.0)

    hard_cap_sec = max(8.0, action.max_sec * profile.human.hard_cap_mult)

    for attempt in range(retries + 1):
        page = ensure_page(page)
        t0 = time.time()

        try:
            report.info(action.name, f"start (try {attempt+1}/{retries+1})", url=getattr(page, "url", None))

            # "human" before
            maybe_think(rng, profile)
            page = maybe_switch_tabs(page, rng, profile)  # optional
            page = ensure_page(page)

            # actual action (with report if it supports it)
            page = _call_action_fn(action, page, rng, profile, report)

            # "human" after
            page = maybe_micro_noise(page, rng, profile)
            page = maybe_backtrack(page, rng, profile)
            maybe_think(rng, profile)

            elapsed = time.time() - t0
            if elapsed > hard_cap_sec:
                raise ActionStalled(f"hard cap exceeded: {elapsed:.1f}s > {hard_cap_sec:.1f}s")

            report.info(action.name, "done", url=getattr(page, "url", None), elapsed=round(elapsed, 3))
            return ensure_page(page), StepResult(outcome="ok", elapsed=elapsed)

        except NeedLogin as e:
            elapsed = time.time() - t0
            report.warn(action.name, f"skip_login: {e}", url=getattr(page, "url", None), elapsed=round(elapsed, 3))
            return ensure_page(page), StepResult(outcome="skip_login", elapsed=elapsed, meta={"reason": str(e)})

        except (TimeoutError, ActionStalled) as e:
            elapsed = time.time() - t0
            report.warn(action.name, f"stalled/timeout: {e}", url=getattr(page, "url", None), elapsed=round(elapsed, 3))
            report.on_error(page, action=f"stall_{action.name}", exc=e)
            # small recovery
            try:
                page = ensure_page(page)
                page.goto("https://www.google.com", wait_until="domcontentloaded", timeout=jitter_ms(rng, profile, 25000))
            except Exception:
                page = ensure_page(page)

        except PWError as e:
            elapsed = time.time() - t0
            report.warn(action.name, f"playwright_error: {e}", url=getattr(page, "url", None), elapsed=round(elapsed, 3))
            report.on_error(page, action=f"pwerr_{action.name}", exc=e)

        except Exception as e:
            elapsed = time.time() - t0
            report.error(action.name, f"error: {e}", url=getattr(page, "url", None), elapsed=round(elapsed, 3))
            report.on_error(page, action=f"err_{action.name}", exc=e)

    return ensure_page(page), StepResult(outcome="error", elapsed=0.0)
