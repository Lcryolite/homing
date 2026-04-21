from __future__ import annotations

import logging
import logging.handlers
import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Sensitive-data redaction filter
# ---------------------------------------------------------------------------

# Patterns compiled once; order matters (longer tokens first).
_SENSITIVE_PATTERNS: list[re.Pattern[str]] = [
    # Authorization header values (Bearer xxx, Basic xxx)
    re.compile(
        r"""(Authorization\s*[:=]\s*["']?(?:Bearer |Basic )?)([A-Za-z0-9+/._~\-]{20,})(["']?)""",
        re.IGNORECASE,
    ),
    # OAuth / refresh tokens in key=value or JSON context
    re.compile(
        r"""(refresh_token|access_token|id_token|token_secret)\s*[:=]\s*["']?([A-Za-z0-9+/._~\-]{20,})""",
        re.IGNORECASE,
    ),
    # Generic "password" / "passwd" / "pass" fields
    re.compile(
        r"""(password|passwd|pass|secret)\s*[:=]\s*["']?([^\s"'}{{,]{4,})""",
        re.IGNORECASE,
    ),
    # Cookie header
    re.compile(
        r"""(Cookie\s*[:=]\s*["']?)(.{10,})(["']?)""",
        re.IGNORECASE,
    ),
]


class SensitiveDataFilter(logging.Filter):
    """Replace sensitive values in log records with ***REDACTED***."""

    _REDACT = "***REDACTED***"

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        if isinstance(record.msg, str):
            record.msg = self._redact(record.msg)
        if record.args:
            record.args = tuple(
                self._redact(a) if isinstance(a, str) else a for a in record.args
            )
        return True

    @staticmethod
    def _redact(text: str) -> str:
        for pat in _SENSITIVE_PATTERNS:
            text = pat.sub(lambda m: f"{m.group(1)}***REDACTED***", text)
        return text


# ---------------------------------------------------------------------------
# Unified logging setup
# ---------------------------------------------------------------------------

_LOG_DIR: Path | None = None


def get_log_dir() -> Path:
    """Return ~/.openemail/, creating it if needed."""
    global _LOG_DIR
    if _LOG_DIR is None:
        _LOG_DIR = Path.home() / ".openemail"
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
    return _LOG_DIR


def setup_logging(
    *,
    debug: bool = False,
    console: bool = True,
    file_log: bool = True,
) -> None:
    """Initialise the root ``openemail`` logger once.

    Call this at process entry (before any other ``openemail`` import that
    may log).  Idempotent — subsequent calls are no-ops.
    """
    root = logging.getLogger("openemail")
    if root.handlers:
        return  # already initialised

    level = logging.DEBUG if debug else logging.INFO
    root.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    redact_filter = SensitiveDataFilter()

    # --- console handler ---------------------------------------------------
    if console:
        ch = logging.StreamHandler()
        ch.setLevel(level)
        ch.setFormatter(formatter)
        ch.addFilter(redact_filter)
        root.addHandler(ch)

    # --- rotating file handler ---------------------------------------------
    if file_log:
        log_path = get_log_dir() / "openemail.log"
        fh = logging.handlers.RotatingFileHandler(
            log_path,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8",
        )
        fh.setLevel(level)
        fh.setFormatter(formatter)
        fh.addFilter(redact_filter)
        root.addHandler(fh)
