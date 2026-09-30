"""Monitor version, reference paths, alert thresholds, and minimum sample sizes.

Bundle versions, the snapshot id, and default paths come from the version
modules of the packages that own them. No bundle version string is written
here. Change MONITOR_VERSION when a threshold, a minimum sample size, the
replay plan, or the review simulation changes, so a new stored record never
overwrites an older one.

Everything the monitor needs to decide "is this enough data to say anything"
or "is this large enough to alert" is a named constant in this file.
"""

from __future__ import annotations

from pathlib import Path

from med_api.version import API_CONTRACT_VERSION, DEFAULT_PATHS, LATENCY_PATH, MODE, SNAPSHOT_ID
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

MONITOR_VERSION = "med-monitor-v1"

ARTIFACT_DIR = ARTIFACT_ROOT / MONITOR_VERSION
REFERENCE_PATH = ARTIFACT_DIR / "reference.json"
PLAN_PATH = ARTIFACT_DIR / "replay_plan.json"
REPLAY_PATH = ARTIFACT_DIR / "replay.json"
FEEDBACK_REVIEW_PATH = ARTIFACT_DIR / "feedback_review.json"
BUNDLE_CHECKS_PATH = ARTIFACT_DIR / "bundle_checks.json"
DOCS_DIR = Path("docs/phase_8")
# Local, gitignored click feedback written by POST /feedback.
API_FEEDBACK_PATH = Path("var/feedback.jsonl")

# ------------------------------------------------------------ data boundary

# Monitored traffic and review labels come from these subsets only. The frozen
# test subsets are never read; see med_monitor.data.
TRAFFIC_SUBSET = SELECTION_SUBSET
VALIDATION_SUBSETS = (SELECTION_SUBSET, DIAGNOSTIC_SUBSET)
FROZEN_SUBSETS = TEST_SUBSETS
# Drift references are fit on this subset of the feature artifact and no other.
REFERENCE_SUBSET = "train"

# --------------------------------------------------------------- replay plan

# Eight consecutive windows of 500 emails, in send-time order. Windows 1-4 are
# the reference operating period. Window 5 is a control with no injected shift.
WINDOW_EMAILS = 500
N_WINDOWS = 8
REFERENCE_WINDOWS = (1, 2, 3, 4)
CURRENT_WINDOWS = (5, 6, 7, 8)
# Share of a window's emails replaced by legitimate first-contact drafts (a new
# partner or collaborator wave). Windows not listed are not shifted.
SHIFT_SCHEDULE = {6: 0.04, 7: 0.08, 8: 0.16}
# Replaced emails are ordinary routine drafts; the injected drafts are these
# validation variants (legitimate first contacts, S03 and S06).
FIRST_CONTACT_VARIANTS = ("legitimate_first_contact", "legitimate_new_domain")
REPLACEABLE_SCENARIO = "routine"
WARMUP_CALLS = 20
PLAN_SEED = SEED

# ----------------------------------------------------- operational thresholds

# Client-side scoring latency. The absolute limit is the AC05 target; the
# relative limit is a multiple of the reference-period p95.
LATENCY_TARGET_MS = 300.0
LATENCY_RELATIVE_FACTOR = 2.0
MIN_REQUESTS_OPERATIONAL = 200
# Exact one-sided tests against the reference period (Fisher exact).
RATE_ALPHA = 0.01
# Email risk scores in [T_warn - NEAR_BAND, T_warn) count as near the cutoff.
# The highest legitimate validation score sits 2.3e-3 below T_warn; the band is
# about twice that margin.
NEAR_BAND = 0.005
MIN_EMAILS_SCORE_BAND = 500
# Fixed lower edges for the score histogram; the last two bins are cut from T_warn.
SCORE_EDGES = (0.0, 0.001, 0.1, 0.5, 0.9, 0.99)

# ------------------------------------------------------------- input drift

# Population stability index against the train-only reference. The two cut
# points are a common convention, not a validated limit for this system.
PSI_WATCH = 0.10
PSI_ALERT = 0.25
# Fewer recipient rows or fewer emails than this in a window: no input-drift
# statement at all. Recipient-level features are counted over recipient rows;
# draft-level features are counted over emails.
MIN_ROWS_INPUT_DRIFT = 500
MIN_EMAILS_INPUT_DRIFT = 500
# A 0/1 indicator also alerts when its share moves this far from the train
# share, because PSI is slow to rise when a rare state (about 2% of train rows)
# grows to about 13%. Watch starts at half of it.
SHARE_SHIFT_ALERT = 0.10
SHARE_SHIFT_WATCH = 0.05
# An alert also needs at least this many rows in excess of the reference
# expectation, so two odd rows in a rare state cannot alert on their own.
MIN_EXCESS_ROWS = 5
# Smoothing added to every bin count on both sides (half a row).
PSI_PSEUDO_COUNT = 0.5
# A feature with at most this many distinct train values gets one bin per value.
MAX_DISCRETE_VALUES = 12
QUANTILE_BINS = 10
# These features describe the sender or the draft, not one recipient, so every
# recipient row of a draft repeats the same value. They are counted once per
# email, in the reference and in every window; otherwise one six-recipient email
# would count six times and dominate a window.
DRAFT_LEVEL_FEATURES = (
    "sender_outbound_count",
    "sender_history_available",
    "sender_history_span_days",
    "addressed_recipient_count",
    "co_support_applicable",
    "draft_raw_token_count",
    "draft_text_empty",
    "draft_text_short",
    "draft_text_oov",
    "draft_subject_blank",
    "draft_body_blank",
)
# Lifetime counts and spans grow with calendar time, so any window after the
# training period sits above the train range by construction. They are reported
# as structural (share above the train maximum) and never alert.
CUMULATIVE_FEATURES = (
    "sender_outbound_count",
    "sender_history_span_days",
    "pair_outbound_count",
    "pair_inbound_count",
    "domain_outbound_count",
    "co_joint_message_count",
    "pair_text_message_count",
)

# ----------------------------------------------------------- decision rates

# A decision-rate statement needs this many emails in the reference and in the
# compared block. At the reference warning rate that is only a few warnings, so
# per-window statements are not made; blocks of four windows are compared.
MIN_EMAILS_DECISION_RATE = 2000

# -------------------------------------------------------- reviewed feedback

# Simulated reviewer: every queued item is answered with the dataset's
# stipulated label after a seeded delay. These are assumptions about reviewer
# behavior, not measurements.
REVIEW_DELAY_SHAPE = 2.0
REVIEW_DELAY_SCALE_DAYS = 3.0
REVIEW_HORIZONS_DAYS = (1, 3, 7, 14, 30)
# Reference and current blocks are compared on labels returned within this many
# days of the assessment.
PERFORMANCE_HORIZON_DAYS = 14
REVIEW_CONFIDENCE = 0.95
# Review strata for allowed emails: (name, lower score bound inclusive, upper
# bound exclusive, inclusion probability). Every warned email is queued.
ALLOWED_STRATA = (
    ("allowed_score_at_least_0.9", 0.9, 1.0 + 1e-9, 1.0),
    ("allowed_score_0.5_to_0.9", 0.5, 0.9, 0.10),
    ("allowed_score_below_0.5", 0.0, 0.5, 0.01),
)
WARNED_STRATUM = "warned"
# A performance statement needs at least this many reviewed misdirected emails
# in the reference and in the current block.
MIN_REVIEWED_POSITIVES = 30
MIN_REVIEWED_LEGITIMATE = 1000

# --------------------------------------------------------------- experiment

# Proposal arithmetic only. Nothing here has been run online.
EXPERIMENT_ALPHA = 0.05
EXPERIMENT_POWER = 0.80
EXPERIMENT_PREVALENCE = 0.005
EXPERIMENT_ICC_VALUES = (0.0, 0.01, 0.05)
EXPERIMENT_EMAILS_PER_SENDER = 200
# The primary outcome is behavioral. No correction data exists, so both inputs
# are assumptions shown as a grid, not estimates: the share of warned mistakes
# a sender fixes with no warning shown, and the share of shown warnings on a
# mistake that a sender acts on.
EXPERIMENT_BASELINE_CORRECTION_RATES = (0.05, 0.10, 0.20)
EXPERIMENT_ACCEPTANCE_RATES = (0.2, 0.5)
# A treatment arm stops for harm when confirmed false interventions reach a
# count this unlikely at the budget rate.
STOP_FOR_HARM_ALPHA = 0.01

__all__ = [name for name in dir() if name.isupper()] + [
    "API_CONTRACT_VERSION",
    "DEFAULT_PATHS",
    "LATENCY_PATH",
    "MODE",
    "SNAPSHOT_ID",
]
