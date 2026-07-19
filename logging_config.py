"""
Yapilandirilmis loglama sistemi.
Structured JSON loglama, log seviyeleri, context binding.
"""
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Optional


class StructuredFormatter(logging.Formatter):
    """JSON formatinda yapilandirilmis log formati."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
        }

        # Extra context
        if hasattr(record, "ctx") and record.ctx:
            log_entry["ctx"] = record.ctx

        # Exception info
        if record.exc_info and record.exc_info[0]:
            log_entry["exc"] = self.formatException(record.exc_info)

        # Performance data
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms

        return json.dumps(log_entry, ensure_ascii=False, default=str)


class HumanFormatter(logging.Formatter):
    """Insan okunabilir format (gelistirme ortami icin)."""

    COLORS = {
        "DEBUG": "\033[36m",    # cyan
        "INFO": "\033[32m",     # green
        "WARNING": "\033[33m",  # yellow
        "ERROR": "\033[31m",    # red
        "CRITICAL": "\033[41m", # red bg
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        msg = record.getMessage()

        parts = [f"{color}{ts} [{record.levelname:8}]{self.RESET}", f"{record.name}:", msg]

        if hasattr(record, "ctx") and record.ctx:
            ctx_str = " ".join(f"{k}={v}" for k, v in record.ctx.items())
            parts.append(f"({ctx_str})")

        if record.exc_info and record.exc_info[0]:
            parts.append(f"\n{self.formatException(record.exc_info)}")

        return " ".join(parts)


def setup_logging(
    level: str = "INFO",
    json_format: bool = False,
    log_file: Optional[str] = None,
) -> logging.Logger:
    """Merkezi loglama kurulumu."""
    root = logging.getLogger("smmm")
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Onceki handler'lari temizle
    root.handlers.clear()

    # Console handler
    console = logging.StreamHandler(sys.stderr)
    if json_format:
        console.setFormatter(StructuredFormatter())
    else:
        console.setFormatter(HumanFormatter())
    root.addHandler(console)

    # Dosya handler (opsiyonel)
    if log_file:
        os.makedirs(os.path.dirname(log_file) or ".", exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(StructuredFormatter())
        root.addHandler(file_handler)

    # Third-party loglari sustur
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("streamlit").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)

    return root


class LogContext:
    """Log context manager - islem bazli veri ekler."""

    def __init__(self, logger: logging.Logger, **ctx):
        self.logger = logger
        self.ctx = ctx

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def log(self, level: str, msg: str, **extra):
        record = self.logger.makeRecord(
            self.logger.name, getattr(logging, level.upper()),
            "", 0, msg, (), None
        )
        record.ctx = {**self.ctx, **extra}
        self.logger.handle(record)


def perf_log(func):
    """Fonksiyon calisma suresini logla."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger("smmm.perf")
        start = time.monotonic()
        try:
            result = func(*args, **kwargs)
            duration = (time.monotonic() - start) * 1000
            logger.debug(
                "%s tamamlandi (%.1fms)",
                func.__name__, duration,
                extra={"duration_ms": round(duration, 1)},
            )
            return result
        except Exception as e:
            duration = (time.monotonic() - start) * 1000
            logger.error(
                "%s hatasi (%.1fms): %s",
                func.__name__, duration, str(e),
                extra={"duration_ms": round(duration, 1)},
                exc_info=True,
            )
            raise
    return wrapper


def error_boundary(logger_name: str = "smmm.errors"):
    """Hata siniri - yakalanmayan hatalari logla ve yut."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = logging.getLogger(logger_name)
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.critical(
                    "Yakalanmamis hata: %s.%s - %s",
                    func.__module__, func.__name__, str(e),
                    exc_info=True,
                    extra={"ctx": {"func": func.__name__, "args_count": len(args)}},
                )
                return None
        return wrapper
    return decorator


# Global logger instances
def get_logger(name: str = "smmm") -> logging.Logger:
    return logging.getLogger(name)
