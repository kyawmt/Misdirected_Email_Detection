"""Threshold-policy version and the bundle it applies to.

Bump POLICY_VERSION when the selection rule, the budget definition, the
decision contract, or the upstream model changes. A new policy version gets a
new artifact directory and a new one-shot test evaluation.
"""

from med_models.version import (
    ARTIFACT_ROOT,
    DATA_DIR,
    DATASET_VERSION,
    FEATURE_SPEC_VERSION,
    FEATURES_DIR,
    MODEL_PATH,
    MODEL_VERSION,
)
from med_models.version import ARTIFACT_DIR as MODEL_DIR

POLICY_VERSION = "med-policy-v2"
# SHA-256 of the frozen `policy.json` of this version. `load_bundle` refuses any other file, so an edited
# cutoff cannot be served. It belongs to POLICY_VERSION: a new policy version needs a new value, set after
# `policy.json` is written and before it is evaluated or served. Phase 9 also anchors it for builds and CI.
POLICY_SHA256 = "be39929a3c92cf978dc00c1773f9bf9dd6bdbdfc73984381033979b46152e8e5"
# A risk score lies in [0, 1] and equality warns, so a cutoff of exactly 1.0 is still a valid cutoff.
T_WARN_RANGE = (0.0, 1.0)
SEED = 20260926
N_BOOTSTRAP = 1000
# AC01: false interventions per 1,000 legitimate emails.
BUDGET_PER_1000 = 1.0
SELECTION_SUBSET = "validation_product_like"
DIAGNOSTIC_SUBSET = "validation_diagnostic"
TEST_SUBSETS = ("test_product_like", "test_diagnostic")
PREVALENCES = (0.001, 0.005, 0.01, 0.02)
# B3: the batch path (published feature CSV) and the single-draft path the API
# uses may differ by summation order only. Scores within this bound and
# identical decisions on every selection draft are required before a policy
# is written.
SCORE_PARITY_BOUND = 1e-12

POLICY_DIR = ARTIFACT_ROOT / POLICY_VERSION
POLICY_PATH = POLICY_DIR / "policy.json"
DOCS_DIR = "docs/phase_5"

__all__ = [
    "BUDGET_PER_1000",
    "DATA_DIR",
    "DATASET_VERSION",
    "DIAGNOSTIC_SUBSET",
    "DOCS_DIR",
    "FEATURE_SPEC_VERSION",
    "FEATURES_DIR",
    "MODEL_DIR",
    "MODEL_PATH",
    "MODEL_VERSION",
    "N_BOOTSTRAP",
    "POLICY_DIR",
    "POLICY_PATH",
    "POLICY_SHA256",
    "POLICY_VERSION",
    "PREVALENCES",
    "SEED",
    "SELECTION_SUBSET",
    "TEST_SUBSETS",
    "T_WARN_RANGE",
    "PolicyError",
]


class PolicyError(ValueError):
    """A policy cannot be selected, loaded, or applied under this contract."""
