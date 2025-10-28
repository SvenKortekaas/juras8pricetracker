from __future__ import annotations

import logging
import os
import sys
import threading
import time
from typing import Any, Mapping

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover - resolved by requirements.txt
    httpx = None  # type: ignore

_LOCK = threading.Lock()
_LOG_INITIALIZED = False
_LOGBOOK_HANDLER: "LogbookHandler | None" = None


def _parse_level(level: str | int | None) -> int:
    if level is None:
        return logging.INFO
    if isinstance(level, int):
        return level
    lvl = str(level).strip()
    if not lvl:
        return logging.INFO
    if lvl.isdigit():
        return int(lvl)
    return logging._nameToLevel.get(lvl.upper(), logging.INFO)


class AddonLogger(logging.LoggerAdapter):
    """Thin wrapper around logging.Logger with context support."""

    def bind(self, **extra: Any) -> "AddonLogger":
        merged = dict(self.extra)
        merged.update(extra)
        return AddonLogger(self.logger, merged)

    def process(self, msg: Any, kwargs: dict[str, Any]):
        extra_kw = dict(kwargs.pop("extra", {}) or {})
        context = dict(self.extra)
        context.update(extra_kw)
        if context:
            serialized = " ".join(
                f"{key}={context[key]}" for key in sorted(context) if context[key] is not None
            )
            msg = f"{msg} | {serialized}"
        kwargs["extra"] = {"addon_context": context}
        return msg, kwargs


class LogbookHandler(logging.Handler):
    """Logging handler that forwards records to Home Assistant's logbook service."""

    def __init__(
        self,
        *,
        name: str,
        token: str,
        api_url: str,
        level: int,
        entity_id: str | None,
        include_level: bool,
    ):
        super().__init__(level=level)
        self._name = name
        self._token = token
        self._api_url = api_url.rstrip("/")
        self._entity_id = entity_id
        self._include_level = include_level
        self._lock = threading.Lock()
        self._client = httpx.Client(timeout=5.0) if httpx else None

    def emit(self, record: logging.LogRecord) -> None:
        if self._client is None:  # pragma: no cover - handled by setup guard
            return
        message = record.getMessage()
        if self._include_level:
            message = f"[{record.levelname}] {message}"

        payload: dict[str, Any] = {"name": self._name, "message": message}
        context = getattr(record, "addon_context", {}) or {}
        entity_id = context.get("entity_id") or self._entity_id
        if entity_id:
            payload["entity_id"] = entity_id
        domain = context.get("domain")
        if domain:
            payload["domain"] = domain

        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        url = f"{self._api_url}/services/logbook/log"

        try:
            with self._lock:
                self._client.post(url, json=payload, headers=headers)
        except Exception:
            # Avoid recursion by writing directly to stderr.
            err = f"Logbook handler failed to emit record: {record.getMessage()}"
            sys.stderr.write(err + os.linesep)

    def close(self) -> None:
        if self._client:
            self._client.close()
        super().close()


def setup_logging(
    *,
    level: str | int | None = None,
    logbook: Mapping[str, Any] | None = None,
) -> None:
    """Configure root logging and optional Home Assistant logbook forwarding."""
    global _LOG_INITIALIZED, _LOGBOOK_HANDLER
    root = logging.getLogger()
    with _LOCK:
        if not _LOG_INITIALIZED:
            handler = logging.StreamHandler(stream=sys.stdout)
            formatter = logging.Formatter(
                fmt="%(asctime)s.%(msecs)03dZ [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
            formatter.converter = time.gmtime  # type: ignore[name-defined]
            handler.setFormatter(formatter)
            root.handlers.clear()
            root.addHandler(handler)
            logging.captureWarnings(True)
            _LOG_INITIALIZED = True

        root.setLevel(_parse_level(level))

        if logbook is None:
            return

        enabled = bool(logbook.get("enabled"))
        if not enabled:
            if _LOGBOOK_HANDLER:
                root.removeHandler(_LOGBOOK_HANDLER)
                _LOGBOOK_HANDLER.close()
                _LOGBOOK_HANDLER = None
            return

        if httpx is None:
            root.warning("Logbook logging requested but httpx is unavailable.")
            return

        token = os.getenv("SUPERVISOR_TOKEN")
        if not token:
            root.warning("Logbook logging requested but SUPERVISOR_TOKEN is not set.")
            return

        api_url = os.getenv("HOME_ASSISTANT_API", "http://supervisor/core/api")
        display_name = logbook.get("name") or "Jura S8 Price Tracker"
        entity_id = logbook.get("entity_id")
        include_level = bool(logbook.get("include_level", True))
        level_override = _parse_level(logbook.get("level"))

        if _LOGBOOK_HANDLER:
            root.removeHandler(_LOGBOOK_HANDLER)
            _LOGBOOK_HANDLER.close()
            _LOGBOOK_HANDLER = None

        handler = LogbookHandler(
            name=display_name,
            token=token,
            api_url=api_url,
            level=level_override,
            entity_id=entity_id,
            include_level=include_level,
        )
        root.addHandler(handler)
        _LOGBOOK_HANDLER = handler


def get_logger(name: str, **context: Any) -> AddonLogger:
    return AddonLogger(logging.getLogger(name), context)


# Local import to avoid circular reference.
