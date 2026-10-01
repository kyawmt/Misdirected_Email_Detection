"""Deployment-check version, record paths, and the workloads the checks use.

Bundle versions, the snapshot id, and default paths come from the version
modules of the packages that own them (`med_policy.version`,
`med_api.version`). No bundle version string is written here. Change
DEPLOY_VERSION when a check, a workload, or an image layout changes, so a stored
record is never replaced by a different definition of the same measurement.
"""

from __future__ import annotations

from pathlib import Path

from med_api.version import API_CONTRACT_VERSION, DEFAULT_PATHS, LATENCY_PATH, MAX_BODY_CHARS, MAX_RECIPIENTS, MODE, SNAPSHOT_ID
from med_policy.version import (
    ARTIFACT_ROOT,
    DATA_DIR,
    DATASET_VERSION,
    DIAGNOSTIC_SUBSET,
    FEATURE_SPEC_VERSION,
    FEATURES_DIR,
    MODEL_PATH,
    MODEL_VERSION,
    POLICY_DIR,
    POLICY_PATH,
    POLICY_VERSION,
    SEED,
    SELECTION_SUBSET,
    TEST_SUBSETS,
)

DEPLOY_VERSION = "med-deploy-v1"

ARTIFACT_DIR = ARTIFACT_ROOT / DEPLOY_VERSION
DOCS_DIR = Path("docs/phase_9")
SCENARIO_RECORD = ARTIFACT_DIR / "scenario_regression.json"
# SHA-256 of the published files nothing else checksums (policy.json and the two stored validation files).
DIGESTS_RECORD = ARTIFACT_DIR / "bundle_digests.json"
BUNDLE_RECORDS = {"api": ARTIFACT_DIR / "bundle_check_api.json", "ui": ARTIFACT_DIR / "bundle_check_ui.json"}
READS_RECORD = ARTIFACT_DIR / "reads.json"
IMAGES_RECORD = ARTIFACT_DIR / "images.json"
RUNS_RECORD = ARTIFACT_DIR / "test_runs.json"
REBUILD_RECORD = ARTIFACT_DIR / "rebuild_comparison.json"
CLEAN_CHECKOUT_RECORD = ARTIFACT_DIR / "clean_checkout.json"
SMOKE_RECORDS = {"process": ARTIFACT_DIR / "smoke_process.json", "container": ARTIFACT_DIR / "smoke_container.json"}
LATENCY_RECORD = ARTIFACT_DIR / "latency_api_image.json"
REHEARSAL_RECORDS = {"container": ARTIFACT_DIR / "rollback_rehearsal_container.json", "process": ARTIFACT_DIR / "rollback_rehearsal_process.json"}
BROWSER_RECORD = ARTIFACT_DIR / "browser_check_ui_container.json"
MUTATION_RECORD = ARTIFACT_DIR / "mutation_checks.json"
PLATFORM_RECORD = ARTIFACT_DIR / "other_platform_check.json"

CONSTRAINTS_FILE = Path("constraints.txt")
# The Python the tests and the images were checked with.
TESTED_PYTHON = "3.11.14"

# ------------------------------------------------------------ data boundary

# Every load, replay, and regression fixture comes from these subsets. The
# frozen test subsets are refused before a draft is read.
VALIDATION_SUBSETS = (SELECTION_SUBSET, DIAGNOSTIC_SUBSET)
FROZEN_SUBSETS = TEST_SUBSETS
# Files that hold per-draft frozen outcomes or frozen feature matrices. No
# Phase 9 command opens them, and no image contains them.
FORBIDDEN_FILES = ("test_evaluation.json",)
FORBIDDEN_PREFIXES = ("features_test_",)

# ---------------------------------------------------------------- serving

API_PORT = 8000
UI_PORT = 8501
LOCAL_HOST = "127.0.0.1"
# Where a container writes reviewed-label clicks. Nothing reads this file back
# into scoring.
FEEDBACK_MOUNT = "/feedback"
FEEDBACK_FILE_NAME = "feedback.jsonl"
# Compose project and default host directory for the demo's feedback file.
COMPOSE_FILE = Path("compose.yaml")
DEMO_FEEDBACK_DIR = Path("var/demo")
API_IMAGE_NAME = "med-api"
UI_IMAGE_NAME = "med-ui"
API_DOCKERFILE = Path("docker/Dockerfile.api")
UI_DOCKERFILE = Path("docker/Dockerfile.ui")
# Seconds to wait for a process or container to answer /health.
START_TIMEOUT_SECONDS = 180

# ---------------------------------------------------------- latency workload

# AC05 (docs/phase_1/ACCEPTANCE_CRITERIA.md, A10): one request in flight, at
# least 1,000 measured requests after 20 unmeasured warm-up requests.
WARMUP_CALLS = 20
MEASURED_CALLS = 1000
TARGET_P95_MS = 300.0
WORKLOAD_SEED = SEED
WORKLOAD_SUBSET = SELECTION_SUBSET
# A small concurrent load, reported apart from the AC05 run.
CONCURRENT_CLIENTS = 4
CONCURRENT_CALLS = 400
# Requests built from a validation draft and stretched to the supported limits
# (A10 asks for maximum-supported inputs to be reported separately).
MAX_INPUT_PROBES = 30
MAX_INPUT_RECIPIENTS = MAX_RECIPIENTS
MAX_INPUT_BODY_CHARS = MAX_BODY_CHARS

# ----------------------------------------------------------- rehearsal

REHEARSAL_PROJECT = "med-rehearsal"

__all__ = [name for name in dir() if name.isupper()]
