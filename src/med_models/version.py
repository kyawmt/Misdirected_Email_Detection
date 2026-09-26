"""Model-comparison version and the feature artifact it trains on.

Bump MODEL_VERSION when the recorded experiments, selection rule, scoring
contract, or upstream feature artifact change. The dataset and feature
specification versions come from `med_features.version`.
"""

from med_features.version import ARTIFACT_DIR as FEATURES_DIR
from med_features.version import ARTIFACT_ROOT, DATA_DIR, DATASET_VERSION, FEATURE_SPEC_VERSION

MODEL_VERSION = "med-model-v2"
SEED = 20260926
N_FOLDS = 4
N_BOOTSTRAP = 1000

ARTIFACT_DIR = ARTIFACT_ROOT / MODEL_VERSION
MODEL_PATH = ARTIFACT_DIR / "model.joblib"
DOCS_DIR = "docs/phase_4"

__all__ = [
    "ARTIFACT_DIR",
    "DATA_DIR",
    "DATASET_VERSION",
    "DOCS_DIR",
    "FEATURES_DIR",
    "FEATURE_SPEC_VERSION",
    "MODEL_PATH",
    "MODEL_VERSION",
    "N_BOOTSTRAP",
    "N_FOLDS",
    "SEED",
    "ModelError",
]


class ModelError(ValueError):
    """A model bundle cannot be trained or scored under this contract."""
