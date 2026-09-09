"""Deterministic redaction for publisher reports and evidence."""

import re
from typing import Iterable


_PRIVATE_KEY = re.compile(
    r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----.*?-----END (?:[A-Z0-9 ]+ )?PRIVATE KEY-----",
    re.DOTALL,
)
_BEARER = re.compile(r"(\bBearer\s+)[^\s,;]+", re.IGNORECASE)
_TOKEN_ASSIGNMENT = re.compile(
    r"((?:token|api[_-]?key|secret|password|passwd|access[_-]?token)\s*[:=]\s*)"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;&]+)",
    re.IGNORECASE,
)
_KNOWN_TOKEN = re.compile(
    r"\b(?:gh[pousr]_[A-Za-z0-9_\-]{10,}|github_pat_[A-Za-z0-9_\-]{10,}|"
    r"sk_(?:live|test)_[A-Za-z0-9]{8,}|xox[baprs]-[A-Za-z0-9-]{10,}|"
    r"AKIA[0-9A-Z]{16})\b"
)
_DATABASE_PASSWORD = re.compile(
    r"(\b(?:postgres(?:ql)?|mysql|mariadb|redis)://[^\s/@:]+:)[^\s/@]+(@)",
    re.IGNORECASE,
)
_COOKIE = re.compile(
    r"(\b(?:cookie|set-cookie)\s*:\s*)([^\r\n]+)", re.IGNORECASE
)
_COOKIE_VALUE = re.compile(
    r"([\w.-]+\s*=\s*)[^;\s]+", re.IGNORECASE
)
_QR = re.compile(
    r"(\b(?:qr(?:[_ -]?code)?|qr[_ -]?payload)\s*[:=]\s*)"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;&]+)",
    re.IGNORECASE,
)
_UNIX_HOME = re.compile(r"(?<![\w])/(?:Users|home)/[^/\s\\]+", re.IGNORECASE)
_WINDOWS_HOME = re.compile(
    r"(?<![\w])[A-Za-z]:[\\/]Users[\\/][^\\/\s]+", re.IGNORECASE
)


def redact_text(text: str, private_values: Iterable[str] = ()) -> str:
    """Replace sensitive values with stable markers, preserving safe context."""

    if not isinstance(text, str):
        raise TypeError("text must be a string")
    clean = text

    # Caller-supplied values are handled first and longest-first to avoid a
    # shorter value partially consuming a longer credential.
    values = sorted({value for value in private_values if value}, key=len, reverse=True)
    for value in values:
        clean = clean.replace(value, "[REDACTED_PRIVATE]")

    clean = _PRIVATE_KEY.sub("[REDACTED_PRIVATE_KEY]", clean)
    clean = _BEARER.sub(r"\1[REDACTED_TOKEN]", clean)
    clean = _DATABASE_PASSWORD.sub(r"\1[REDACTED_PASSWORD]\2", clean)
    clean = _COOKIE.sub(lambda m: m.group(1) + _COOKIE_VALUE.sub("[REDACTED_COOKIE]", m.group(2)), clean)
    clean = _QR.sub(r"\1[REDACTED_QR]", clean)
    clean = _TOKEN_ASSIGNMENT.sub(r"\1[REDACTED_SECRET]", clean)
    clean = _KNOWN_TOKEN.sub("[REDACTED_TOKEN]", clean)
    clean = _WINDOWS_HOME.sub("[REDACTED_HOME]", clean)
    clean = _UNIX_HOME.sub("[REDACTED_HOME]", clean)
    return clean
