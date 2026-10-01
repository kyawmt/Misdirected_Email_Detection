"""Generated blocks inside hand-written Markdown.

A document that mixes prose with generated numbers marks each generated region:

    <!-- med-docs:begin NAME -->
    ...generated Markdown...
    <!-- med-docs:end NAME -->

`python -m med_docs report` replaces the text between a pair of markers and
touches nothing else. Every marker pair must appear exactly once, and a marker in
the file with no generated body is an error, so a renamed block cannot be left
stale. Standard library only.
"""

from __future__ import annotations

import re

_MARK = re.compile(r"<!-- med-docs:(begin|end) ([a-z0-9_]+) -->")


class BlockError(ValueError):
    """A document's block markers do not match the blocks the generator produces."""


def begin(name: str) -> str:
    return f"<!-- med-docs:begin {name} -->"


def end(name: str) -> str:
    return f"<!-- med-docs:end {name} -->"


def names(text: str) -> list[str]:
    """Block names in order of appearance, one per begin marker."""
    return [match.group(2) for match in _MARK.finditer(text) if match.group(1) == "begin"]


def apply(text: str, bodies: dict[str, str], source: str = "document") -> str:
    """Replace every block's content with the generated body."""
    found = names(text)
    if sorted(found) != sorted(bodies):
        missing = sorted(set(bodies) - set(found))
        extra = sorted(set(found) - set(bodies))
        raise BlockError(f"{source}: markers and generated blocks differ (no marker for {missing}; no generated body for {extra})")
    if len(found) != len(set(found)):
        raise BlockError(f"{source}: a block name appears more than once")
    for name, body in bodies.items():
        pattern = re.compile(re.escape(begin(name)) + r"\n(?:.*?\n)?" + re.escape(end(name)), re.DOTALL)
        replacement = begin(name) + "\n" + body.strip("\n") + "\n" + end(name)
        text, count = pattern.subn(lambda _match: replacement, text)
        if count != 1:
            raise BlockError(f"{source}: block {name!r} must be a begin marker, content, and an end marker, each on its own line")
    return text


def extract(text: str, name: str) -> str:
    pattern = re.compile(re.escape(begin(name)) + r"\n((?:.*?\n)?)" + re.escape(end(name)), re.DOTALL)
    match = pattern.search(text)
    if not match:
        raise BlockError(f"block {name!r} not found")
    return match.group(1).rstrip("\n")


def outside(text: str) -> str:
    """The hand-written text: everything except the generated blocks."""
    return re.sub(re.escape("<!-- med-docs:begin ") + r"([a-z0-9_]+)" + re.escape(" -->") + r".*?" + re.escape("<!-- med-docs:end ") + r"\1" + re.escape(" -->"), "", text, flags=re.DOTALL)
