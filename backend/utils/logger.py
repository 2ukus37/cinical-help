"""
Structured logging utility for CDSS audit trail.
"""
import logging
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


class JSONFormatter(logging.Formatter):
    """Emit log records as JSON for structured audit trail."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if hasattr(record, "extra"):
            log_obj.update(record.extra)
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(JSONFormatter())

    # File handler – rotating daily
    fh = logging.FileHandler(LOG_DIR / "cdss_audit.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(JSONFormatter())

    # Invalid input handler
    invalid_fh = logging.FileHandler(LOG_DIR / "invalid_inputs.log", encoding="utf-8")
    invalid_fh.setLevel(logging.WARNING)
    invalid_fh.setFormatter(JSONFormatter())
    invalid_fh.addFilter(lambda r: "INVALID_INPUT" in r.getMessage())

    logger.addHandler(ch)
    logger.addHandler(fh)
    logger.addHandler(invalid_fh)
    logger.propagate = False
    return logger


audit_logger = get_logger("cdss.audit")
model_logger = get_logger("cdss.model")
