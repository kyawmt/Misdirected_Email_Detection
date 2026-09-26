"""Feature-specification version and the dataset it is fit on.

Bump FEATURE_SPEC_VERSION when feature definitions, the text preprocessor,
the training-window fit rule, or the dataset the transformer is fit on change.
Every feature CLI and downstream package reads its defaults from here.
"""

from pathlib import Path

from med_data.version import DATA_ROOT

FEATURE_SPEC_VERSION = "med-features-v2"
# The published dataset this feature artifact is fit on. It can lag the
# generator's DATASET_VERSION while a rebuild is pending.
DATASET_VERSION = "med-synth-v4"

DATA_DIR = DATA_ROOT / DATASET_VERSION
ARTIFACT_ROOT = Path("artifacts")
ARTIFACT_DIR = ARTIFACT_ROOT / FEATURE_SPEC_VERSION
DOCS_DIR = Path("docs/phase_3")
