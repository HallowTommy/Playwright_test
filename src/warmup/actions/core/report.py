from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Any, Dict

from playwright.sync_api import Page


@dataclass
class ReportEvent:
    ts: float
    level: str
    action: str
    msg: str
    url: Optional[str] = None
    extra: Optional[dict] = None


def dump_debug(page: Page, out_dir: Path, prefix: str) -> Dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    res: Dict[str, str] = {}
    try:
        if page and not page.is_closed():
            png = out_dir / f"{prefix}_{ts}.png"
            html = out_dir / f"{prefix}_{ts}.html"
            page.screenshot(path=str(png), full_page=True)
            html.write_text(page.content(), encoding="utf-8")
            res["screenshot"] = str(png)
            res["html"] = str(html)
    except Exception:
        pass
    return res


class Report:
    """
    Единая точка:
    - JSONL (шаги/ошибки)
    - Trace start/stop
    - dumps on error
    """
    def __init__(self, base_dir: Path, run_name: str):
        self.base_dir = base_dir
        self.run_name = run_name

        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.traces_dir = self.base_dir / "traces"
        self.dumps_dir = self.base_dir / "dumps"
        self.traces_dir.mkdir(parents=True, exist_ok=True)
        self.dumps_dir.mkdir(parents=True, exist_ok=True)

        self.jsonl_path = self.base_dir / f"{run_name}.jsonl"
        self.trace_path = self.traces_dir / f"{run_name}.zip"

    def log(self, level: str, action: str, msg: str, url: Optional[str] = None, **extra: Any) -> None:
        ev = ReportEvent(ts=time.time(), level=level, action=action, msg=msg, url=url, extra=extra or None)
        with self.jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(ev), ensure_ascii=False) + "\n")

    def info(self, action: str, msg: str, url: Optional[str] = None, **extra: Any) -> None:
        self.log("INFO", action, msg, url, **extra)

    def warn(self, action: str, msg: str, url: Optional[str] = None, **extra: Any) -> None:
        self.log("WARN", action, msg, url, **extra)

    def error(self, action: str, msg: str, url: Optional[str] = None, **extra: Any) -> None:
        self.log("ERROR", action, msg, url, **extra)

    def start_trace(self, page: Page) -> None:
        try:
            page.context.tracing.start(screenshots=True, snapshots=True, sources=True)
        except Exception:
            pass

    def stop_trace(self, page: Page) -> None:
        try:
            page.context.tracing.stop(path=str(self.trace_path))
        except Exception:
            pass

    def on_error(self, page: Page, action: str, exc: Exception) -> Dict[str, str]:
        dbg = dump_debug(page, self.dumps_dir, prefix=action)
        self.error(action, f"exception: {exc}", url=getattr(page, "url", None), **dbg)
        return dbg
