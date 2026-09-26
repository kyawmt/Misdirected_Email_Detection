"""Text preprocessing for content features.

Generator slots are removed before tokenization so a unique reference, ticket,
or calendar date cannot dominate TF-IDF. The same function is used for the
fit corpus and for every draft and history message.
"""

from __future__ import annotations

import re

from med_features.schema import MIN_DF

# Exact tokens dropped after generator-slot substitution. "acknowledge" is kept.
# "re" removes the reply-subject marker.
STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "to",
        "for",
        "of",
        "in",
        "on",
        "at",
        "by",
        "with",
        "from",
        "this",
        "that",
        "is",
        "are",
        "be",
        "was",
        "were",
        "it",
        "as",
        "if",
        "when",
        "before",
        "after",
        "please",
        "thanks",
        "thank",
        "hi",
        "you",
        "your",
        "we",
        "i",
        "our",
        "me",
        "my",
        "any",
        "only",
        "can",
        "will",
        "have",
        "has",
        "had",
        "do",
        "does",
        "not",
        "so",
        "but",
        "they",
        "their",
        "them",
        "there",
        "here",
        "also",
        "than",
        "then",
        "into",
        "over",
        "under",
        "about",
        "up",
        "out",
        "just",
        "its",
        "am",
        "been",
        "being",
        "did",
        "doing",
        "re",
        "ref",
        "ack",
    }
)

_MESSAGE_ID = re.compile(r"\b[md]\d{6}\b", re.IGNORECASE)
_TICKET = re.compile(r"\bt-\d+\b", re.IGNORECASE)
_ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_TOKEN = re.compile(r"[a-z0-9]+")


def document_text(subject: str, body: str) -> str:
    """One document string for a message or a draft."""
    return f"{subject}\n{body}"


def is_blank(text: str) -> bool:
    return not text.strip()


def unigrams(text: str) -> list[str]:
    """Content tokens after slot removal, in order."""
    cleaned = text.casefold()
    cleaned = _MESSAGE_ID.sub(" ", cleaned)
    cleaned = _TICKET.sub(" ", cleaned)
    cleaned = _ISO_DATE.sub(" ", cleaned)
    tokens = []
    for token in _TOKEN.findall(cleaned):
        if len(token) < 2 or token.isdigit():
            continue
        if token in STOP_WORDS:
            continue
        tokens.append(token)
    return tokens


def analyze(text: str) -> list[str]:
    """Unigrams plus adjacent bigrams. This is the TF-IDF analyzer."""
    grams = unigrams(text)
    bigrams = [f"{grams[index]} {grams[index + 1]}" for index in range(len(grams) - 1)]
    return grams + bigrams


def text_config() -> dict:
    """Serializable preprocessor settings stored with the fitted transformer."""
    return {
        "analyzer": "unigrams_and_adjacent_bigrams",
        "min_df": MIN_DF,
        "norm": "l2",
        "smooth_idf": True,
        "sublinear_tf": False,
        "stop_words": sorted(STOP_WORDS),
        "stripped_patterns": [
            "message_or_draft_id_[md]dddddd",
            "ticket_t-digits",
            "iso_date",
            "tokens_ref_and_ack",
        ],
    }
