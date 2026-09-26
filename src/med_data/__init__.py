"""Fictional dataset construction for misdirected-email detection.

Phase 2 covers contacts, sent mail, assessment drafts, stipulated labels,
chronological splits, and leakage checks. It does not compute features or
train models.
"""

from med_data.generate import generate_dataset
from med_data.version import DATASET_VERSION, GENERATOR_VERSION, SEED

__all__ = [
    "DATASET_VERSION",
    "GENERATOR_VERSION",
    "SEED",
    "generate_dataset",
]
