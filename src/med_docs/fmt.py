"""Number and table formatting shared by the renderers. Standard library only."""

from __future__ import annotations


def n(value) -> str:
    """An integer count with thousands separators."""
    return f"{int(value):,}"


def f(value, digits: int = 3) -> str:
    return "n/a" if value is None else f"{value:.{digits}f}"


def score(value) -> str:
    """A risk score the way the generated Phase 7 and Phase 9 documents print it."""
    if value is None:
        return "n/a"
    if value != 0 and abs(value) < 1e-3:
        return f"{value:.3e}"
    return f"{value:.7f}"


def delta(value) -> str:
    return f"{value:+.2e}"


def ci(low, high, digits: int = 3) -> str:
    return f"[{low:.{digits}f}, {high:.{digits}f}]"


def pct(value, digits: int = 1) -> str:
    return "n/a" if value is None else f"{value * 100:.{digits}f}%"


def ms(value, digits: int = 2) -> str:
    return f"{value:.{digits}f} ms"


def per_1000(count, denominator, digits: int = 2) -> str:
    return f"{count / denominator * 1000:.{digits}f}"


def rate_1000(count, denominator) -> float:
    return count / denominator * 1000


def of(count, denominator) -> str:
    return f"{n(count)} / {n(denominator)}"


def mib(size_bytes) -> str:
    return f"{size_bytes / (1 << 20):.0f} MiB"


def table(header: list[str], rows: list[list]) -> str:
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def code(text) -> str:
    return f"`{text}`"


def cut(digest: str, size: int = 16) -> str:
    return f"`{digest[:size]}…`"
