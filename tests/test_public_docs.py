"""Public documents stay free of private planning context and broken links."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_ROOTS = (ROOT / "README.md", ROOT / "docs")
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
PRIVATE_TERMS = (
    re.compile(r"interviewer", re.IGNORECASE),
    re.compile(r"job description", re.IGNORECASE),
    re.compile(r"project_context"),
    re.compile(r"abnormal", re.IGNORECASE),
)


def test_public_docs_avoid_private_terms_and_broken_links():
    problems = []
    for path in _markdown_files():
        text = path.read_text(encoding="utf-8")
        for pattern in PRIVATE_TERMS:
            if pattern.search(text):
                problems.append(f"{path.relative_to(ROOT)} contains {pattern.pattern!r}")
        for match in LINK.finditer(text):
            target = match.group(1).strip()
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                if target.startswith("#") and not _has_anchor(text, target[1:]):
                    problems.append(f"{path.relative_to(ROOT)} missing anchor {target}")
                continue
            path_part, anchor = _split_target(target)
            if not path_part:
                if anchor and not _has_anchor(text, anchor):
                    problems.append(f"{path.relative_to(ROOT)} missing anchor #{anchor}")
                continue
            resolved = (path.parent / path_part).resolve()
            if not resolved.is_file():
                problems.append(f"{path.relative_to(ROOT)} links to missing {path_part}")
                continue
            if anchor and not _has_anchor(resolved.read_text(encoding="utf-8"), anchor):
                problems.append(f"{path.relative_to(ROOT)} links to missing anchor {path_part}#{anchor}")
    assert problems == []


def _markdown_files():
    found = []
    for root in PUBLIC_ROOTS:
        if root.is_file():
            found.append(root)
        else:
            found.extend(sorted(root.rglob("*.md")))
    return found


def _split_target(target: str) -> tuple[str, str]:
    body = target.split()[0]
    if "#" in body:
        path_part, anchor = body.split("#", 1)
        return path_part, anchor
    return body, ""


def _has_anchor(text: str, anchor: str) -> bool:
    wanted = anchor.strip().lower()
    for line in text.splitlines():
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
            if _slug(heading) == wanted:
                return True
    return False


def _slug(heading: str) -> str:
    text = heading.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "-", text.strip())
    return text
