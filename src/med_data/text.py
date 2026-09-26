"""Text helpers shared by generation and leakage checks."""

import hashlib


def normalize_body(text: str) -> str:
    return " ".join(text.split()).casefold()


def body_hash(text: str) -> str:
    """Stable hash of a non-empty body. Empty bodies share an empty hash."""
    normalized = normalize_body(text)
    if not normalized:
        return ""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
