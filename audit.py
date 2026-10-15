# audit.py — guvenlik olaylarini security.log'a yazar (engellenen prompt
# injection denemeleri, yetkisiz kritik arac denemeleri, rate-limit asimlari).
# PII loglara ham yazilmaz; log edilecek metin once pii.redact'tan gecirilir.
import logging
from pathlib import Path

from pii import redact

_LOG_PATH = Path(__file__).parent.resolve() / "security.log"

_logger = logging.getLogger("security")
_logger.setLevel(logging.INFO)
if not _logger.handlers:
    handler = logging.FileHandler(_LOG_PATH, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
    _logger.addHandler(handler)


def log_blocked_attempt(identifier: str, reason: str, snippet: str) -> None:
    _logger.info(f"BLOCKED identifier={identifier} reason={reason!r} text={redact(snippet)[:200]!r}")


def log_unauthorized_tool(identifier: str, tool_name: str, girdi) -> None:
    _logger.info(f"UNAUTHORIZED_TOOL identifier={identifier} tool={tool_name} girdi={redact(str(girdi))[:200]!r}")


def log_rate_limited(identifier: str) -> None:
    _logger.info(f"RATE_LIMITED identifier={identifier}")
