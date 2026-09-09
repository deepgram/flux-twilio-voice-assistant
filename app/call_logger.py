# app/call_logger.py
"""Per-call log files.

Container/stdout logging is untouched. This adds a second sink: while a call is
being handled, everything logged inside that call's async context is *also*
appended to a file of its own under LOGS_DIR.

Scoping works by tagging each Twilio websocket connection with a mutable holder
kept in a contextvar. asyncio tasks copy the current context when they are
created, so the per-call background tasks (agent reader, media meter, hangup
finalizer) all see the same holder and write to the same file. Because the
holder is mutable, the call_sid and caller phone can be filled in later, when
Twilio's `start` frame finally tells us what they are.
"""
from __future__ import annotations

import logging
import os
import re
import threading
import time
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Repo root (or /app in the container) + /logs, unless overridden.
_DEFAULT_DIR = Path(__file__).resolve().parent.parent / "logs"
LOGS_DIR = Path(os.getenv("CALL_LOG_DIR") or os.getenv("BOBA_LOG_DIR") or _DEFAULT_DIR)

CALL_LOG_TO_FILE = os.getenv("CALL_LOG_TO_FILE", "1").lower() not in ("0", "false", "no")
# getLevelName returns a str like "Level BOGUS" for junk input; fall back to INFO
_level = logging.getLevelName((os.getenv("CALL_LOG_LEVEL") or "INFO").upper())
CALL_LOG_LEVEL = _level if isinstance(_level, int) else logging.INFO

_FMT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"
_RULE = "=" * 80

log = logging.getLogger("call_logger")

# Per-connection holder; see module docstring.
_ctx: ContextVar[Optional[dict]] = ContextVar("call_log_ctx", default=None)

_dir_lock = threading.Lock()
_dir_ready: Optional[bool] = None


def _ensure_dir() -> bool:
    """Create LOGS_DIR once; remember failures so we don't warn on every call."""
    global _dir_ready
    with _dir_lock:
        if _dir_ready is None:
            try:
                LOGS_DIR.mkdir(parents=True, exist_ok=True)
                _dir_ready = True
            except Exception as e:
                log.warning(f"per-call logs disabled: cannot create {LOGS_DIR} ({e})")
                _dir_ready = False
        return _dir_ready


def _digits(phone: Optional[str]) -> str:
    return re.sub(r"\D", "", phone or "")


def log_file_for(phone_digits: str, suffix: str = "") -> Path:
    """Path for a call log file with an already-sanitized phone prefix."""
    return LOGS_DIR / f"{phone_digits}{suffix}.log"


def _filename(call_sid: Optional[str], phone: Optional[str]) -> str:
    # Phone-first so /staff can find a caller's latest log by globbing
    # "<digits>_*.log"; timestamp + call_sid tail keep repeat calls distinct.
    who = _digits(phone) or "unknown"
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    tail = re.sub(r"[^A-Za-z0-9]", "", call_sid or "")[-8:] or "nosid"
    return f"{who}_{ts}_{tail}.log"


class _HolderFilter(logging.Filter):
    """Accept only records emitted inside this call's context."""

    def __init__(self, holder: dict) -> None:
        super().__init__()
        self._holder = holder

    def filter(self, record: logging.LogRecord) -> bool:
        return _ctx.get() is self._holder


class _CallFileHandler(logging.FileHandler):
    def __init__(self, path: Path, holder: dict) -> None:
        super().__init__(path, mode="a", encoding="utf-8")
        self.setLevel(CALL_LOG_LEVEL)
        self.setFormatter(logging.Formatter(_FMT, _DATEFMT))
        self.addFilter(_HolderFilter(holder))

    def raw(self, text: str) -> None:
        """Write text straight to the file, bypassing formatting/filtering."""
        try:
            self.acquire()
            try:
                if self.stream is None:
                    self.stream = self._open()
                self.stream.write(text if text.endswith("\n") else text + "\n")
                self.flush()
            finally:
                self.release()
        except Exception:
            pass


# ---------------------------------------------------------------- public API

def begin_context() -> dict:
    """Tag the current async context as belonging to one (not-yet-known) call."""
    holder: dict[str, Any] = {"call_sid": None, "phone": None, "path": None,
                              "handler": None, "started": time.time()}
    _ctx.set(holder)
    return holder


def start_call_log(holder: Optional[dict], call_sid: str, phone: Optional[str] = None,
                   stream_sid: Optional[str] = None) -> Optional[Path]:
    """Open this call's log file and start mirroring the call's log records into it."""
    if holder is None:
        return None
    if holder.get("handler"):  # already started (duplicate `start` frame)
        return holder.get("path")
    if not CALL_LOG_TO_FILE or not _ensure_dir():
        return None

    path = LOGS_DIR / _filename(call_sid, phone)
    try:
        handler = _CallFileHandler(path, holder)
    except Exception as e:
        log.warning(f"cannot open per-call log {path}: {e}")
        return None

    holder.update(call_sid=call_sid, phone=phone, path=path,
                  handler=handler, started=time.time())
    logging.getLogger().addHandler(handler)

    handler.raw(
        f"{_RULE}\n"
        f"CALL START   {datetime.now().isoformat(timespec='seconds')}\n"
        f"call_sid     {call_sid}\n"
        f"stream_sid   {stream_sid or '-'}\n"
        f"caller       {phone or 'unknown'}\n"
        f"{_RULE}"
    )
    return path


def end_call_log(holder: Optional[dict], summary: Optional[dict] = None) -> None:
    """Write the footer, detach the handler and close the file."""
    if not holder:
        return
    handler: Optional[_CallFileHandler] = holder.get("handler")
    if not handler:
        return

    lines = [
        _RULE,
        f"CALL END     {datetime.now().isoformat(timespec='seconds')}",
        f"duration     {time.time() - float(holder.get('started') or time.time()):.1f}s",
    ]
    for key, value in (summary or {}).items():
        lines.append(f"{key:<12} {value}")
    lines.append(_RULE)
    handler.raw("\n".join(lines) + "\n")

    holder["handler"] = None
    try:
        logging.getLogger().removeHandler(handler)
    finally:
        try:
            handler.close()
        except Exception:
            pass


def current_log_path() -> Optional[Path]:
    """Path of the log file for the call being handled in this context, if any."""
    holder = _ctx.get()
    return holder.get("path") if holder else None


def append_for_phone(phone: str, lines: list[str]) -> Optional[Path]:
    """Append a block to the most recent log file for `phone`.

    Used by out-of-call events (e.g. staff marking an order ready), which happen
    long after the websocket — and its handler — are gone.
    """
    if not CALL_LOG_TO_FILE:
        return None
    digits = _digits(phone)
    if not digits or not LOGS_DIR.is_dir():
        return None
    matches = list(LOGS_DIR.glob(f"{digits}_*.log"))
    if not matches:
        return None
    latest = max(matches, key=lambda p: p.stat().st_mtime)
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    try:
        with open(latest, "a", encoding="utf-8") as f:
            f.write(f"\n{_RULE}\n")
            for line in lines:
                f.write(f"[{ts}] {line}\n")
            f.write(f"{_RULE}\n\n")
    except Exception as e:
        log.warning(f"could not append to {latest.name}: {e}")
        return None
    return latest
