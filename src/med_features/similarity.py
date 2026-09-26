"""Normalized Levenshtein similarity for display names and address local-parts."""

from __future__ import annotations


def normalize_name(name: str) -> str:
    return " ".join(name.casefold().split())


def local_part(email: str) -> str:
    return email.casefold().split("@", 1)[0]


def levenshtein(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    previous = list(range(len(right) + 1))
    for index, char in enumerate(left, start=1):
        current = [index]
        for other_index, other in enumerate(right, start=1):
            insert = current[other_index - 1] + 1
            delete = previous[other_index] + 1
            replace = previous[other_index - 1] + (char != other)
            current.append(min(insert, delete, replace))
        previous = current
    return previous[-1]


def normalized_similarity(left: str, right: str) -> float:
    """1 minus edit distance over the longer string. Equal strings score 1."""
    if left == right:
        return 1.0
    denom = max(len(left), len(right))
    if denom == 0:
        return 1.0
    return 1.0 - levenshtein(left, right) / denom
