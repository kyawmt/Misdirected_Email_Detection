"""Model-comparison version.

Bump MODEL_VERSION when the recorded experiments, selection rule, or scoring
contract change. The dataset and feature specification stay on their own versions.
"""

MODEL_VERSION = "med-model-v1"
SEED = 20260926
N_FOLDS = 4
N_BOOTSTRAP = 1000


class ModelError(ValueError):
    """A model bundle cannot be trained or scored under this contract."""
