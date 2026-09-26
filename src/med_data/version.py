"""Dataset and generator versions.

Bump DATASET_VERSION when the seed, quotas, or generation rules change.
The frozen test subsets belong to one dataset version.
"""

DATASET_VERSION = "med-synth-v2"
GENERATOR_VERSION = "1.1.0"
SEED = 20260926

# Product-like mail uses this misdirection rate. It is a simulation assumption,
# not a measured real-world prevalence. Train is enriched so later models see
# enough positive examples; that rate is not the product operating point.
PRODUCT_LIKE_MISDIRECTED = 10
PRODUCT_LIKE_TEST_DRAFTS = 2000
PRODUCT_LIKE_VALIDATION_DRAFTS = 1000
TRAIN_MISDIRECTED = 100
TRAIN_DRAFTS = 1000
