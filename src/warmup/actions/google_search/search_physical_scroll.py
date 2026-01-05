from __future__ import annotations

import random
from typing import Tuple, Optional, Dict, Any

from playwright.sync_api import Page, TimeoutError, Error as PWError

from ..core.helpers import (
    goto,
    ensure_page,
    human_sleep,
    human_scroll,
    human_mouse_wander,
    maybe_handle_popups,
    maybe_handle_consent,
    jitter_ms,
    # new helpers we added to core/helpers.py
    human_clear,
    human_type_with_typos,
    human_click,
    maybe_read_pause,
    back,
)
from ..core.types import BehaviorProfile
from ..core.report import Report


PHYSICAL_QUERIES: Tuple[str, ...] = (
    "gym", "fitness club", "yoga studio", "pilates studio", "crossfit gym", "swimming pool",
    "pharmacy", "drugstore", "24 hour pharmacy",
    "supermarket", "grocery store", "convenience store", "hypermarket", "wholesale store", "organic food store",
    "bakery", "butcher shop", "fish market",
    "coffee shop", "cafe", "pizza place", "sushi restaurant", "fast food near me",
    "atm", "bank branch", "post office",
    "gas station", "car wash", "tire shop", "auto repair", "phone repair",
    "electronics store", "computer store", "hardware store", "home improvement store", "furniture store",
    "clothing store", "shoe store", "sports store",
    "pet store", "vet clinic", "dentist", "clinic", "urgent care", "optical store",
    "barber shop", "hair salon", "nail salon",
    "dry cleaning", "laundry", "florist", "bookstore", "cinema", "shopping mall",
    "IKEA", "Decathlon", "Lidl", "Aldi", "Carrefour", "Walmart", "Costco", "Tesco", "Auchan",
)

MODIFIERS: Tuple[str, ...] = (
    "near me", "open now", "hours", "price", "address", "best",
)


def _search_box_locator(page: Page):
    return page.locator('textarea[name="q"], input[name="q"]')


def _focus_search_box(page: Page, rng: random.Random, profile: BehaviorProfile) -> bool:
    box = _search_box_locator(page)
    if box.count() > 0:
        try:
            if rng.random() < 0.60:
                try:
                    box.first.hover(timeout=jitter_ms(rng, profile, 1500))
                    human_sleep(rng, profile, 0.05, 0.18)
                except Exception:
                    pass
            box.first.click(timeout=jitter_ms(rng, profile, 2500))
            human_sleep(rng, profile, 0.04, 0.16)
            return True
        except Exception:
            return False
    return False


def _hover_results(page: Page, rng: random.Random, profile: BehaviorProfile) -> int:
    titles = page.locator("h3")
    total = titles.count()
    n = min(total, rng.randint(3, 7))
    if n <= 0:
        human_mouse_wander(page, rng, profile, moves=rng.randint(2, 5))
        return 0

    did = 0
    for i in range(n):
        try:
            el = titles.nth(i)
            el.scroll_into_view_if_needed(timeout=jitter_ms(rng, profile, 1500))
            box = el.bounding_box()
            if box:
                x = box["x"] + min(20, max(1, box["width"] - 1))
                y = box["y"] + min(10, max(1, box["height"] - 1))
                page.mouse.move(x, y, steps=rng.randint(8, 20))
                human_sleep(rng, profile, 0.10, 0.45)
                did += 1
        except Exception:
            continue
    return did


def _click_next_page(page: Page, rng: random.Random, profile: BehaviorProfile) -> bool:
    candidates = [
        "a#pnnext",
        'a[aria-label="Next"]',
        'a[aria-label="Next page"]',
        'a:has-text("Next")',
        'a:has-text("Следующая")',
        'a:has-text("Weiter")',
    ]
    for sel in candidates:
        loc = page.locator(sel)
        try:
            if loc.count() > 0:
                loc.first.scroll_into_view_if_needed(timeout=jitter_ms(rng, profile, 1500))
                ok = human_click(loc, rng, profile, timeout_ms=jitter_ms(rng, profile, 4500))
                human_sleep(rng, profile, 0.25, 0.90)
                return ok
        except Exception:
            continue
    return False


def _result_link_locators(page: Page):
    """
    Try to target clickable search results robustly.
    Usually: <a ...><h3>Title</h3></a>
    """
    a1 = page.locator('a:has(h3)')
    if a1.count() > 0:
        return a1
    return page.locator("h3").locator("xpath=ancestor::a[1]")


def _slow_read_to_bottom(page: Page, rng: random.Random, profile: BehaviorProfile) -> None:
    """
    Slow incremental scroll to bottom, as if reading.
    """
    try:
        maybe_read_pause(rng, profile, a=0.25, b=1.15, chance=0.75)

        height = page.evaluate("() => Math.max(document.body.scrollHeight, document.documentElement.scrollHeight)")
        if not isinstance(height, (int, float)) or height <= 0:
            height = 8000

        segments = rng.randint(6, 14)
        for _ in range(segments):
            step = rng.randint(260, 720)
            try:
                page.mouse.wheel(0, step)
            except PWError:
                break

            if rng.random() < 0.18:
                try:
                    page.mouse.wheel(0, -rng.randint(80, 260))
                except Exception:
                    pass

            human_sleep(rng, profile, 0.45, 1.85)

        if rng.random() < 0.55:
            try:
                page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
                human_sleep(rng, profile, 0.35, 1.10)
            except Exception:
                pass

    except Exception:
        return


def _open_result_in_new_tab(page: Page, rng: random.Random, profile: BehaviorProfile, report: Optional[Report] = None) -> bool:
    """
    Middle-click one random SERP result -> new tab, read a bit, close.
    """
    links = _result_link_locators(page)
    n = links.count()
    if n <= 0:
        return False

    idx = rng.randint(0, min(n - 1, 6))
    link = links.nth(idx)

    try:
        link.scroll_into_view_if_needed(timeout=jitter_ms(rng, profile, 1500))
        human_sleep(rng, profile, 0.05, 0.22)

        with page.context.expect_page(timeout=jitter_ms(rng, profile, 8000)) as pinfo:
            try:
                link.hover(timeout=jitter_ms(rng, profile, 1500))
                human_sleep(rng, profile, 0.04, 0.18)
            except Exception:
                pass
            link.click(button="middle", timeout=jitter_ms(rng, profile, 4000))

        newp = pinfo.value
        try:
            newp.wait_for_load_state("domcontentloaded", timeout=jitter_ms(rng, profile, 20000))
        except Exception:
            pass
        human_sleep(rng, profile, 0.2, 0.8)

        try:
            maybe_handle_consent(newp, rng, profile)
            maybe_handle_popups(newp, rng, profile)
        except Exception:
            pass

        if rng.random() < 0.70:
            _slow_read_to_bottom(newp, rng, profile)
        else:
            for _ in range(rng.randint(2, 5)):
                try:
                    newp.mouse.wheel(0, rng.randint(350, 900))
                except Exception:
                    break
                human_sleep(rng, profile, 0.25, 0.90)

        try:
            newp.close()
        except Exception:
            pass

        return True

    except Exception as e:
        if report:
            report.warn("google_search", f"new_tab_open_failed: {e}", url=getattr(page, "url", None))
        return False


def _maybe_click_internal_link(page: Page, rng: random.Random, profile: BehaviorProfile) -> bool:
    """
    Sometimes click an internal link (same host) in the same tab,
    skim a bit, then go back (to the result page).
    """
    try:
        if rng.random() > 0.35:
            return False

        cur_url = (page.url or "").lower()
        if not cur_url.startswith("http"):
            return False
        if "accounts.google.com" in cur_url:
            return False

        try:
            host = page.evaluate("() => location.host")
        except Exception:
            host = ""
        host = (host or "").lower().strip()
        if not host:
            return False

        candidates = page.locator(
            'a[href]:not([href^="#"]):not([href^="javascript:"]):not([href^="mailto:"]):not([href^="tel:"])'
        )
        total = candidates.count()
        if total <= 0:
            return False

        sample_n = min(total, 30)
        tries = rng.randint(4, 8)
        picked = None

        banned_words = ("login", "sign in", "register", "subscribe", "buy", "cart", "checkout", "cookie", "accept")
        banned_words_ru = ("войти", "регистрац", "подпис", "купить", "корзин", "оформ", "куки", "принять")
        banned_words_de = ("anmelden", "registr", "abo", "kaufen", "warenkorb", "checkout", "cookies")

        for _ in range(tries):
            i = rng.randint(0, sample_n - 1)
            a = candidates.nth(i)
            try:
                a.scroll_into_view_if_needed(timeout=jitter_ms(rng, profile, 1500))
            except Exception:
                continue

            try:
                href = a.get_attribute("href") or ""
                txt = (a.inner_text(timeout=800) or "").strip().lower()
            except Exception:
                continue

            href_l = href.strip().lower()
            if not href_l or href_l.startswith("#"):
                continue
            if any(w in txt for w in banned_words) or any(w in txt for w in banned_words_ru) or any(w in txt for w in banned_words_de):
                continue

            try:
                same_host = page.evaluate(
                    """(href) => {
                        try { const u = new URL(href, location.href); return u.host === location.host; }
                        catch(e) { return false; }
                    }""",
                    href,
                )
            except Exception:
                same_host = False

            if not same_host:
                continue

            picked = a
            break

        if picked is None:
            return False

        human_sleep(rng, profile, 0.05, 0.25)
        try:
            picked.hover(timeout=jitter_ms(rng, profile, 1500))
            human_sleep(rng, profile, 0.03, 0.15)
        except Exception:
            pass

        picked.click(timeout=jitter_ms(rng, profile, 6000))
        try:
            page.wait_for_load_state("domcontentloaded", timeout=jitter_ms(rng, profile, 20000))
        except Exception:
            pass

        try:
            maybe_handle_consent(page, rng, profile)
            maybe_handle_popups(page, rng, profile)
        except Exception:
            pass

        maybe_read_pause(rng, profile, a=0.25, b=1.4, chance=0.85)
        for _ in range(rng.randint(2, 5)):
            try:
                page.mouse.wheel(0, rng.randint(280, 820))
            except Exception:
                break
            human_sleep(rng, profile, 0.25, 1.05)

        page = back(page, rng, profile)
        try:
            page.wait_for_load_state("domcontentloaded", timeout=jitter_ms(rng, profile, 15000))
        except Exception:
            pass

        return True

    except Exception:
        return False


def _maybe_open_internal_link_new_tab(
    page: Page,
    rng: random.Random,
    profile: BehaviorProfile,
    report: Optional[Report] = None,
) -> bool:
    """
    Sometimes open an internal link (same host) in a NEW TAB via middle-click,
    skim a bit, close tab, stay on the current page.
    """
    try:
        if rng.random() > 0.28:
            return False

        cur_url = (page.url or "").lower()
        if not cur_url.startswith("http"):
            return False
        if "accounts.google.com" in cur_url:
            return False

        try:
            host = page.evaluate("() => location.host")
        except Exception:
            host = ""
        host = (host or "").lower().strip()
        if not host:
            return False

        candidates = page.locator(
            'a[href]:not([href^="#"]):not([href^="javascript:"]):not([href^="mailto:"]):not([href^="tel:"])'
        )
        total = candidates.count()
        if total <= 0:
            return False

        sample_n = min(total, 35)
        tries = rng.randint(5, 9)
        picked = None

        banned_words = ("login", "sign in", "register", "subscribe", "buy", "cart", "checkout", "cookie", "accept")
        banned_words_ru = ("войти", "регистрац", "подпис", "купить", "корзин", "оформ", "куки", "принять")
        banned_words_de = ("anmelden", "registr", "abo", "kaufen", "warenkorb", "checkout", "cookies")

        for _ in range(tries):
            i = rng.randint(0, sample_n - 1)
            a = candidates.nth(i)
            try:
                a.scroll_into_view_if_needed(timeout=jitter_ms(rng, profile, 1500))
            except Exception:
                continue

            try:
                href = a.get_attribute("href") or ""
                txt = (a.inner_text(timeout=800) or "").strip().lower()
            except Exception:
                continue

            href_l = href.strip().lower()
            if not href_l or href_l.startswith("#"):
                continue
            if any(w in txt for w in banned_words) or any(w in txt for w in banned_words_ru) or any(w in txt for w in banned_words_de):
                continue

            try:
                same_host = page.evaluate(
                    """(href) => {
                        try { const u = new URL(href, location.href); return u.host === location.host; }
                        catch(e) { return false; }
                    }""",
                    href,
                )
            except Exception:
                same_host = False

            if not same_host:
                continue

            picked = a
            break

        if picked is None:
            return False

        picked.scroll_into_view_if_needed(timeout=jitter_ms(rng, profile, 1500))
        human_sleep(rng, profile, 0.05, 0.25)

        try:
            picked.hover(timeout=jitter_ms(rng, profile, 1500))
            human_sleep(rng, profile, 0.03, 0.18)
        except Exception:
            pass

        with page.context.expect_page(timeout=jitter_ms(rng, profile, 8000)) as pinfo:
            picked.click(button="middle", timeout=jitter_ms(rng, profile, 4500))

        newp = pinfo.value
        try:
            newp.wait_for_load_state("domcontentloaded", timeout=jitter_ms(rng, profile, 20000))
        except Exception:
            pass

        try:
            maybe_handle_consent(newp, rng, profile)
            maybe_handle_popups(newp, rng, profile)
        except Exception:
            pass

        maybe_read_pause(rng, profile, a=0.25, b=1.3, chance=0.85)
        for _ in range(rng.randint(2, 6)):
            try:
                newp.mouse.wheel(0, rng.randint(260, 860))
            except Exception:
                break
            human_sleep(rng, profile, 0.25, 1.1)

        if rng.random() < 0.35:
            try:
                newp.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
                human_sleep(rng, profile, 0.25, 0.9)
            except Exception:
                pass

        try:
            newp.close()
        except Exception:
            pass

        if report:
            report.info("google_search", "opened_internal_link_new_tab", url=getattr(page, "url", None))

        return True

    except Exception as e:
        if report:
            report.warn("google_search", f"internal_new_tab_failed: {e}", url=getattr(page, "url", None))
        return False


def _open_result_in_current_tab_and_return(
    page: Page,
    rng: random.Random,
    profile: BehaviorProfile,
    report: Optional[Report] = None,
) -> Page:
    """
    Open one result in current tab, read slowly to bottom, then:
    - maybe open an internal link in a new tab and close it
    - else maybe click an internal link in same tab and go back
    Then go back to SERP.
    """
    links = _result_link_locators(page)
    n = links.count()
    if n <= 0:
        return page

    idx = rng.randint(0, min(n - 1, 7))
    link = links.nth(idx)

    try:
        link.scroll_into_view_if_needed(timeout=jitter_ms(rng, profile, 1500))
        human_sleep(rng, profile, 0.05, 0.22)

        ok = human_click(link, rng, profile, timeout_ms=jitter_ms(rng, profile, 6000))
        if not ok:
            return page

        try:
            page.wait_for_load_state("domcontentloaded", timeout=jitter_ms(rng, profile, 25000))
        except Exception:
            pass

        page = ensure_page(page)
        try:
            page = maybe_handle_consent(page, rng, profile)
            page = maybe_handle_popups(page, rng, profile)
        except Exception:
            pass

        maybe_read_pause(rng, profile, a=0.35, b=2.5, chance=0.85)

        _slow_read_to_bottom(page, rng, profile)

        # ✅ internal interaction: prefer new-tab internal link, else same-tab internal click
        did_internal_tab = _maybe_open_internal_link_new_tab(page, rng, profile, report=report)

        did_internal = False
        if not did_internal_tab:
            did_internal = _maybe_click_internal_link(page, rng, profile)
            if report and did_internal:
                report.info("google_search", "opened_internal_link", url=getattr(page, "url", None))

        if rng.random() < 0.35:
            try:
                page.mouse.wheel(0, -rng.randint(200, 700))
                human_sleep(rng, profile, 0.25, 0.85)
            except Exception:
                pass

        page = back(page, rng, profile)
        try:
            page.wait_for_selector("#search, h3", timeout=jitter_ms(rng, profile, 14000))
        except Exception:
            pass

        return ensure_page(page)

    except Exception as e:
        if report:
            report.warn("google_search", f"open_current_failed: {e}", url=getattr(page, "url", None))
        return ensure_page(page)


def run(
    page: Page,
    rng: random.Random,
    profile: BehaviorProfile,
    report: Optional[Report] = None,
) -> Page:
    """
    - open google.com once
    - do exactly 3 queries
    - for each query:
        - submit (with human clear + occasional typos)
        - scroll/hover
        - maybe open SERP result in new tab
        - maybe open SERP result in current tab:
            - read slowly to bottom
            - maybe open an internal link in new tab and close
            - else maybe click internal link in same tab and back
            - back to SERP
        - go to next page once and read again
    """

    def log(level: str, msg: str, **extra: Any) -> None:
        if not report:
            return
        ev_url = getattr(page, "url", None)
        if "url" in extra:
            ev_url = extra.pop("url")
        fn = getattr(report, level, None)
        if fn:
            fn("google_search", msg, url=ev_url, **extra)

    page = ensure_page(page)

    log("info", "goto_google:start")
    page = goto(page, "https://www.google.com", rng, profile)
    page = maybe_handle_consent(page, rng, profile)
    page = maybe_handle_popups(page, rng, profile)
    log("info", "goto_google:done", url=page.url)

    QUERIES_PER_RUN = 3
    PAGES_PER_QUERY = 2

    used = set()

    for qi in range(1, QUERIES_PER_RUN + 1):
        page = ensure_page(page)

        base = rng.choice(PHYSICAL_QUERIES)
        tries = 0
        while base in used and tries < 10:
            base = rng.choice(PHYSICAL_QUERIES)
            tries += 1
        used.add(base)

        q = base
        if rng.random() < 0.65:
            q = f"{q} {rng.choice(MODIFIERS)}"

        log("info", "query:selected", q_index=qi, total=QUERIES_PER_RUN, query=q, base=base)

        if not _focus_search_box(page, rng, profile):
            log("warn", "searchbox:not_found -> retry_goto_google")
            page = goto(page, "https://www.google.com", rng, profile)
            page = maybe_handle_consent(page, rng, profile)
            page = maybe_handle_popups(page, rng, profile)

        ok_focus = _focus_search_box(page, rng, profile)
        log("info", "searchbox:focus", ok=ok_focus)
        if not ok_focus:
            log("error", "searchbox:still_not_found -> abort_query", q_index=qi)
            continue

        try:
            box = _search_box_locator(page).first

            human_clear(box, rng, profile)

            human_type_with_typos(
                box,
                q,
                rng,
                profile,
                typo_chance=0.028,
                fix_chance=0.92,
                sensitive=False,
            )

            maybe_read_pause(rng, profile, a=0.08, b=0.55, chance=0.55)

            box.press("Enter")
            log("info", "query:submitted", q_index=qi, query=q)
        except Exception as e:
            log("error", "query:submit_failed", q_index=qi, err=str(e))
            continue

        try:
            page.wait_for_selector("#search, h3", timeout=jitter_ms(rng, profile, 12000))
            log("info", "serp:loaded", q_index=qi, url=page.url)
        except TimeoutError:
            log("warn", "serp:load_timeout", q_index=qi, url=page.url)

        page = maybe_handle_consent(page, rng, profile)
        page = maybe_handle_popups(page, rng, profile)

        did_open_new_tab = False
        did_open_current = False

        for pi in range(1, PAGES_PER_QUERY + 1):
            log("info", "serp:read_page:start", q_index=qi, page_index=pi)

            totals: Dict[str, int] = {"hovered": 0, "scroll_calls": 0}

            rounds = rng.randint(2, 4)
            for _ in range(rounds):
                totals["hovered"] += _hover_results(page, rng, profile)
                page = human_scroll(page, rng, profile, steps=rng.randint(1, 2))
                totals["scroll_calls"] += 1
                human_sleep(rng, profile, 0.20, 0.70)

            if rng.random() < 0.70:
                try:
                    amt = rng.randint(500, 1400)
                    page.mouse.wheel(0, -amt)
                    human_sleep(rng, profile, 0.12, 0.40)
                    log("info", "serp:scroll_up", q_index=qi, page_index=pi, amount=amt)
                except Exception as e:
                    log("warn", "serp:scroll_up_failed", q_index=qi, page_index=pi, err=str(e))

            if not did_open_new_tab and rng.random() < 0.28:
                ok = _open_result_in_new_tab(page, rng, profile, report=report)
                did_open_new_tab = did_open_new_tab or ok
                log("info", "serp:open_new_tab", q_index=qi, page_index=pi, ok=ok)

            if not did_open_current and rng.random() < 0.34:
                before_url = getattr(page, "url", None)
                page = _open_result_in_current_tab_and_return(page, rng, profile, report=report)
                did_open_current = True
                log("info", "serp:open_current_and_back", q_index=qi, page_index=pi, before=before_url, after=getattr(page, "url", None))

            log("info", "serp:read_page:done", q_index=qi, page_index=pi, **totals)

            if pi < PAGES_PER_QUERY:
                moved = _click_next_page(page, rng, profile)
                log("info", "serp:next_page", q_index=qi, ok=moved)
                if not moved:
                    break

                try:
                    page.wait_for_selector("#search, h3", timeout=jitter_ms(rng, profile, 12000))
                except TimeoutError:
                    pass

                page = maybe_handle_consent(page, rng, profile)
                page = maybe_handle_popups(page, rng, profile)

        human_sleep(rng, profile, 0.35, 1.20)

    log("info", "action:done", unique_queries=len(used), used=list(used))
    return ensure_page(page)
