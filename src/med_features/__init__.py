"""Behavioral and text features for misdirected-email drafts.

Phase 3 turns a scoring view into one row per addressed recipient. It does not
train a model, choose a threshold, or score frozen test subsets for reporting.
"""

from med_features.version import FEATURE_SPEC_VERSION

__all__ = ["FEATURE_SPEC_VERSION"]
