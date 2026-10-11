"""Pure translation between legacy codes and domain meaning.

Kept as plain functions over plain data, with no Django import, so the rules
can be tested without a database and read without tracing through models. The
only interesting decision in here is what to do with a code nobody documented.
"""

from __future__ import annotations

import re
from typing import Final

#: ST_PEDIDO, as described in a printed manual from 2003.
ORDER_STATUS: Final[dict[str, str]] = {
    "A": "open",
    "P": "awaiting_payment",
    "F": "invoiced",
    "C": "cancelled",
}

#: TP_PESSOA. Brazilian tax law distinguishes a natural person from a company,
#: and the legacy column keeps the Portuguese initial.
PERSON_TYPE: Final[dict[str, str]] = {
    "F": "individual",
    "J": "company",
}

#: What an undocumented code becomes. Surfacing it as "unknown" rather than
#: raising keeps one bad row from taking down a whole listing, and keeps the
#: original letter visible so somebody can go and ask what it meant.
UNKNOWN = "unknown"

_NON_DIGITS = re.compile(r"\D+")


def order_status(code: str | None) -> str:
    """Translate ST_PEDIDO. An unmapped letter becomes ``'unknown'``."""
    if code is None:
        return UNKNOWN
    return ORDER_STATUS.get(code.strip().upper(), UNKNOWN)


def order_status_code(status: str) -> str | None:
    """The inverse, for writes. ``None`` when the status has no legacy code."""
    for code, label in ORDER_STATUS.items():
        if label == status:
            return code
    return None


def person_type(code: str | None) -> str:
    if code is None:
        return UNKNOWN
    return PERSON_TYPE.get(code.strip().upper(), UNKNOWN)


def document_digits(raw: str | None) -> str | None:
    """Strip the punctuation two systems disagree about.

    ``'123.456.789-00'`` and ``'12345678900'`` are the same document; the
    legacy table contains both spellings because two different screens wrote
    to it. The API exposes digits only, so callers can compare them.
    """
    if raw is None:
        return None
    digits = _NON_DIGITS.sub("", raw)
    return digits or None


def document_kind(raw: str | None) -> str:
    """``'cpf'`` for 11 digits, ``'cnpj'`` for 14, else ``'unknown'``.

    Derived from the document rather than read from TP_PESSOA, because the two
    columns disagree in real data and the digits are the harder evidence.
    """
    digits = document_digits(raw)
    if digits is None:
        return UNKNOWN
    return {11: "cpf", 14: "cnpj"}.get(len(digits), UNKNOWN)


def format_document(raw: str | None) -> str | None:
    """Punctuate a document for display, leaving anything unexpected alone."""
    digits = document_digits(raw)
    if digits is None:
        return None
    if len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    if len(digits) == 14:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
    return digits


def phone_digits(raw: str | None) -> str | None:
    """Phone numbers arrive as ``'(91) 99999-0002'`` or as bare digits."""
    return document_digits(raw)


def titleize(raw: str | None) -> str | None:
    """Legacy text is stored SHOUTING, because the terminals were uppercase.

    Rendered as title case for display, with the Portuguese connecting words
    left lowercase so "MARIA DOS SANTOS" does not become "Maria Dos Santos".
    """
    if raw is None:
        return None
    cleaned = " ".join(raw.split())
    if not cleaned:
        return None
    lowercase = {"de", "da", "do", "das", "dos", "e"}
    words = [
        word.lower() if word.lower() in lowercase else word.capitalize()
        for word in cleaned.lower().split(" ")
    ]
    if words:
        words[0] = words[0].capitalize()
    return " ".join(words)
