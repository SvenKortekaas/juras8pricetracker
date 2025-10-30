from __future__ import annotations

import logging
import sys
import threading
import time
from typing import Any

_LOCK = threading.Lock()
_LOG_INITIALIZED = False


def _parse_level(level: str | int | None) -> int:
    if level is None:
        return logging.INFO
    if isinstance(level, int):
        return level
    value = str(level).strip()
    if not value:
        return logging.INFO
    if value.isdigit():
        return int(value)
    return logging._nameToLevel.get(value.upper(), logging.INFO)


class AddonLogger(logging.LoggerAdapter):
    """Thin wrapper around logging.Logger with simple context binding."""

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
        return msg, kwargs


def setup_logging(*, level: str | int | None = None) -> None:
    """Configure the root logger for the add-on."""
    global _LOG_INITIALIZED
    with _LOCK:
        root = logging.getLogger()
        if not _LOG_INITIALIZED:
            handler = logging.StreamHandler(stream=sys.stdout)
            formatter = logging.Formatter(
                fmt="%(asctime)s.%(msecs)03dZ [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
            formatter.converter = time.gmtime  # type: ignore[attr-defined]
            handler.setFormatter(formatter)
            root.handlers.clear()
            root.addHandler(handler)
            logging.captureWarnings(True)
            _LOG_INITIALIZED = True

        root.setLevel(_parse_level(level))


def get_logger(name: str, **context: Any) -> AddonLogger:
    return AddonLogger(logging.getLogger(name), context)
