"""Frozen TF-IDF transformer.

Vocabulary and IDF are fit on sent messages strictly before the validation
window. Warmup mail is part of that corpus. Validation and test text are not.
The fitted object is reused at transform time and is not refit per draft.
"""

from __future__ import annotations

from datetime import datetime

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from med_data.calendar import split_bounds
from med_features.preprocess import analyze, document_text, text_config
from med_features.schema import FEATURE_SPEC_VERSION, MIN_DF, FeatureError

FIT_END_EXCLUSIVE = split_bounds("validation")[0]


class FittedText:
    """A fitted vectorizer plus the settings that produced it."""

    def __init__(self, vectorizer: TfidfVectorizer, config: dict, fit_scope: dict):
        self.vectorizer = vectorizer
        self.config = config
        self.fit_scope = fit_scope
        self.feature_spec_version = FEATURE_SPEC_VERSION

    def save(self, path) -> None:
        joblib.dump(
            {
                "feature_spec_version": self.feature_spec_version,
                "config": self.config,
                "fit_scope": self.fit_scope,
                "vectorizer": self.vectorizer,
            },
            path,
        )

    @classmethod
    def load(cls, path) -> "FittedText":
        payload = joblib.load(path)
        version = payload.get("feature_spec_version")
        if version != FEATURE_SPEC_VERSION:
            raise FeatureError(f"Transformer version {version} does not match {FEATURE_SPEC_VERSION}")
        if payload.get("config") != text_config():
            raise FeatureError("Fitted transformer config does not match the current preprocessor")
        fitted = cls(payload["vectorizer"], payload["config"], payload["fit_scope"])
        if not hasattr(fitted.vectorizer, "vocabulary_"):
            raise FeatureError("Loaded transformer has no vocabulary")
        return fitted


def training_documents(dataset) -> list[str]:
    """Sent subject/body documents eligible for the vocabulary fit.

    Documents are ordered by send time and message id. Empty analyses are
    omitted. The end bound is the validation window start, exclusive.
    """
    messages = dataset.messages
    eligible = messages.loc[messages["sent_at"] < FIT_END_EXCLUSIVE]
    eligible = eligible.sort_values(["sent_at", "message_id"], kind="mergesort")
    documents = []
    for subject, body in zip(eligible["subject"].tolist(), eligible["body"].tolist(), strict=True):
        text = document_text(subject, body)
        if analyze(text):
            documents.append(text)
    return documents


def fit_text_transformer(documents: list[str], *, fit_scope: dict | None = None) -> FittedText:
    """Fit IDF on an explicit document list. The caller chooses the corpus."""
    config = text_config()
    usable = [document for document in documents if analyze(document)]
    if len(usable) < 2:
        raise FeatureError("Need at least two non-empty documents to fit TF-IDF")
    vectorizer = TfidfVectorizer(
        analyzer=analyze,
        min_df=MIN_DF,
        norm="l2",
        smooth_idf=True,
        sublinear_tf=False,
        dtype=np.float64,
    )
    vectorizer.fit(usable)
    scope = {
        "document_count": len(usable),
        "vocabulary_size": len(vectorizer.vocabulary_),
        "fit_sent_at_end_exclusive": FIT_END_EXCLUSIVE.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "corpus": "caller_supplied_documents",
    }
    if fit_scope:
        scope.update(fit_scope)
    return FittedText(vectorizer, config, scope)


def fit_on_dataset(dataset) -> FittedText:
    """Fit on warmup and train sent mail only."""
    messages = dataset.messages
    end = FIT_END_EXCLUSIVE
    eligible = messages.loc[messages["sent_at"] < end]
    skipped = 0
    for subject, body in zip(eligible["subject"].tolist(), eligible["body"].tolist(), strict=True):
        if not analyze(document_text(subject, body)):
            skipped += 1
    documents = training_documents(dataset)
    if eligible["sent_at"].empty:
        raise FeatureError("Training window has no sent messages")
    first = _as_stamp(eligible["sent_at"].min())
    last = _as_stamp(eligible["sent_at"].max())
    scope = {
        "corpus": "sent_messages_before_validation_window",
        "warmup_included": True,
        "validation_and_test_excluded": True,
        "messages_in_window": int(len(eligible)),
        "empty_documents_skipped": skipped,
        "first_sent_at": first,
        "last_sent_at": last,
        "dataset_version": str(messages["dataset_version"].iloc[0]) if "dataset_version" in messages else "",
    }
    return fit_text_transformer(documents, fit_scope=scope)


def _as_stamp(value) -> str:
    if isinstance(value, datetime):
        current = value
    else:
        current = value.to_pydatetime()
    return current.astimezone(FIT_END_EXCLUSIVE.tzinfo).strftime("%Y-%m-%dT%H:%M:%SZ")
