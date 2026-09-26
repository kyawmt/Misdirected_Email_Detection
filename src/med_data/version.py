"""Dataset and generator versions, and the published data location.

Bump DATASET_VERSION when the seed, quotas, or generation rules change.
The frozen test subsets belong to one dataset version.
"""

from pathlib import Path

DATASET_VERSION = "med-synth-v4"
GENERATOR_VERSION = "1.3.0"
SEED = 20260926

# Published tables live under data/<version>. Paths are relative to the
# repository root, which is where the CLIs run.
DATA_ROOT = Path("data")
DATA_DIR = DATA_ROOT / DATASET_VERSION

# Product-like mail uses this misdirection rate. It is a simulation assumption,
# not a measured real-world prevalence. Train is enriched so later models see
# enough positive examples; that rate is not the product operating point.
PRODUCT_LIKE_TEST_DRAFTS = 6000
PRODUCT_LIKE_TEST_MISDIRECTED = 30
PRODUCT_LIKE_VALIDATION_DRAFTS = 4000
PRODUCT_LIKE_VALIDATION_MISDIRECTED = 20
TRAIN_DRAFTS = 3000
TRAIN_MISDIRECTED = 300
