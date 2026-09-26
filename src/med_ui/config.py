"""All UI configuration in one place.

Versions and bundle paths come from `med_api.version` and `med_policy.version`,
so the UI follows whatever bundle the API serves. No version string is written
here. The curated example rules below select drafts from the validation
subsets by rule; no draft id appears in this package.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from med_api.version import API_CONTRACT_VERSION, DEFAULT_PATHS, MAX_RECIPIENTS, ORGANIZATION_DOMAIN, SNAPSHOT_ID
from med_policy.version import DIAGNOSTIC_SUBSET, POLICY_DIR, POLICY_VERSION, SELECTION_SUBSET

# --------------------------------------------------------------------- API

DEFAULT_API_URL = "http://127.0.0.1:8000"
# The API has its own 2 s scoring timeout. The read timeout here only covers
# the HTTP round trip on top of it.
CONNECT_TIMEOUT_SECONDS = 2.0
READ_TIMEOUT_SECONDS = 10.0
DEFAULT_UI_PORT = 8501

# The Phase 1 request fields. The UI sends these and nothing else: no draft
# reference, and never a label, scenario, split, family, or score.
REQUEST_FIELDS = ("draft_timestamp", "sender", "to", "cc", "bcc", "subject", "body", "context_snapshot_id")
ROLES = ("to", "cc", "bcc")
FEEDBACK_LABELS = ("intended", "unintended")

EXPECTED_CONTRACT_VERSION = API_CONTRACT_VERSION
EXPECTED_SNAPSHOT_ID = SNAPSHOT_ID
EXPECTED_POLICY_VERSION = POLICY_VERSION
MAX_UNIQUE_RECIPIENTS = MAX_RECIPIENTS
SENDER_DOMAIN = ORGANIZATION_DOMAIN

# ------------------------------------------------------ data and exploration

# Curated examples come from these subsets only. The frozen test subsets are
# refused before any draft text is read.
EXAMPLE_SUBSETS = (SELECTION_SUBSET, DIAGNOSTIC_SUBSET)
# Stored decisions used to pick examples exist for the policy's selection subset.
STORED_SCORES_SUBSET = SELECTION_SUBSET
# The exploration view reads these two stored validation artifacts and nothing else.
EXPLORATION_SCORES_FILE = "validation_scores.csv"
EXPLORATION_POLICY_FILE = "policy.json"
# Recorded per-scenario outcomes shown in "About this example" (validation only).
VALIDATION_EVALUATION_FILE = "validation_evaluation.json"
# Candidate what-if cutoffs: every stored validation score whose cutoff would
# produce at most this many false warnings, plus the policy cutoff and a few
# round values for scale.
EXPLORATION_MAX_FALSE_WARNINGS = 25
EXPLORATION_ROUND_CUTOFFS = (0.5, 0.9, 0.95, 0.99)
# Rows of the tradeoff table below the policy cutoff.
TRADEOFF_MAX_FALSE_WARNINGS = 10


@dataclass(frozen=True)
class UiSettings:
    api_url: str
    root: Path
    data_dir: Path
    policy_dir: Path

    @classmethod
    def from_env(cls) -> "UiSettings":
        root = Path(os.environ.get("MED_UI_ROOT") or os.environ.get("MED_API_ROOT") or ".")
        return cls(
            api_url=os.environ.get("MED_UI_API_URL", DEFAULT_API_URL),
            root=root,
            data_dir=Path(os.environ.get("MED_UI_DATA") or root / DEFAULT_PATHS["data"]),
            policy_dir=Path(os.environ.get("MED_UI_POLICY_DIR") or root / POLICY_DIR),
        )


# ------------------------------------------------------- curated examples

# Scenario names and one-line stories, paraphrased from docs/phase_1/SCENARIOS.md.
# They appear only in the "About this example" panel, never in a request.
SCENARIO_STORIES = {
    "S01": ("Lookalike replacement", "The sender picked a contact whose name resembles the person they meant to write to."),
    "S02": ("Added external recipient", "An outside supplier was added by accident to mail meant for the internal group."),
    "S03": ("New legitimate collaborator", "A planned first message to a newly assigned colleague with no earlier exchanges."),
    "S04": ("Familiar recipient, unusual topic", "Compensation content went to a frequent contact who handles different work."),
    "S05": ("Routine legitimate mail", "Ordinary mail to recipients the sender writes to regularly."),
    "S06": ("Uncommon external domain, valid purpose", "A planned first contact at a new external domain."),
    "S07": ("Legitimate topic change", "A familiar contact is invited to work unrelated to earlier messages."),
    "S08": ("Multiple recipients and roles", "A group message where a contact in Cc or Bcc may not belong."),
    "S09": ("Cold start or little text", "A sender with no earlier mail, or a draft with empty or tiny text."),
    "S11": ("Mistaken first contact", "Autocomplete selected a directory contact the sender has never emailed."),
}

# Desired outcomes, quoted in substance from docs/phase_1/SCENARIOS.md.
DESIRED_OUTCOMES = {
    "S01": "Warn on the lookalike recipient when combined context supports it; name resemblance alone is insufficient.",
    "S02": "Warn on the added recipient using several signals; keep the other recipients visible.",
    "S03": "Aim to allow; show limited relationship history as context, not a mistake label. A warning is a false positive.",
    "S04": "Warn if content mismatch and other evidence justify it; familiarity alone is insufficient.",
    "S05": "Allow. This is the ordinary no-intervention path.",
    "S06": "Aim to allow; novelty does not supply the label.",
    "S07": "Aim to allow; unusual content alone is not definitive.",
    "S08": "Assess every unique addressee across roles; flag the unintended one.",
    "S09": "Assess with a visible limitation; never manufacture confidence or equate missing history with low risk.",
    "S10": "Return a non-assessed outcome with no risk score and no allow; separate invalid input from unavailable context.",
    "S11": "Aim to warn when combined context supports it; novelty alone is not proof.",
}


@dataclass(frozen=True)
class ExampleRule:
    """How one curated example is chosen. Applied to stored validation results, never to test data.

    `stored_decision` is the policy's recorded decision for the draft in
    `validation_scores.csv`. `pick` orders the matching drafts:
    - "median": the draft at position len // 2 by (email risk, draft id)
    - "highest": the highest email risk score, ties by draft id
    - "fewest_recipients_highest": fewest recipients, then highest email risk, then draft id
    """

    key: str
    title: str
    subset: str
    scenario_ids: tuple[str, ...]
    variants: tuple[str, ...]
    misdirected: bool
    stored_decision: str
    pick: str
    rule: str


EXAMPLE_RULES = (
    ExampleRule(
        key="routine",
        title="Routine project update",
        subset=STORED_SCORES_SUBSET,
        scenario_ids=("S05",),
        variants=("internal_project",),
        misdirected=False,
        stored_decision="allow",
        pick="median",
        rule="The S05 internal project draft at the median email risk score among those the policy allowed on validation_product_like.",
    ),
    ExampleRule(
        key="added_recipient",
        title="Forecast with an added vendor",
        subset=STORED_SCORES_SUBSET,
        scenario_ids=("S02",),
        variants=("added_external",),
        misdirected=True,
        stored_decision="warn",
        pick="fewest_recipients_highest",
        rule="Among S02 added-recipient mistakes the policy warned on validation_product_like: the fewest recipients, then the highest email risk score.",
    ),
    ExampleRule(
        key="first_contact",
        title="Introduction to a new collaborator",
        subset=STORED_SCORES_SUBSET,
        scenario_ids=("S03", "S06"),
        variants=("legitimate_first_contact", "legitimate_new_domain"),
        misdirected=False,
        stored_decision="allow",
        pick="highest",
        rule="The legitimate first contact (S03 or S06) with the highest email risk score among those the policy allowed on validation_product_like, the one closest to the cutoff.",
    ),
    ExampleRule(
        key="lookalike_miss",
        title="Staffing note to a similar name",
        subset=STORED_SCORES_SUBSET,
        scenario_ids=("S01",),
        variants=("lookalike_replacement",),
        misdirected=True,
        stored_decision="allow",
        pick="highest",
        rule="The S01 lookalike mistake the policy allowed on validation_product_like with the highest email risk score, the one closest to the cutoff.",
    ),
    ExampleRule(
        key="topic_miss",
        title="Compensation note to a familiar contact",
        subset=STORED_SCORES_SUBSET,
        scenario_ids=("S04",),
        variants=("familiar_topic_mismatch",),
        misdirected=True,
        stored_decision="allow",
        pick="highest",
        rule="The S04 familiar-recipient topic mistake the policy allowed on validation_product_like with the highest email risk score.",
    ),
    ExampleRule(
        key="first_contact_miss",
        title="Status update to an autocompleted contact",
        subset=STORED_SCORES_SUBSET,
        scenario_ids=("S11",),
        variants=("mistaken_first_contact",),
        misdirected=True,
        stored_decision="allow",
        pick="highest",
        rule="The S11 mistaken first contact the policy allowed on validation_product_like with the highest email risk score.",
    ),
    ExampleRule(
        key="topic_change",
        title="Kickoff invitation to a familiar contact",
        subset=STORED_SCORES_SUBSET,
        scenario_ids=("S07",),
        variants=("legitimate_topic_change",),
        misdirected=False,
        stored_decision="allow",
        pick="highest",
        rule="The S07 legitimate topic change with the highest email risk score among those the policy allowed on validation_product_like.",
    ),
    ExampleRule(
        key="cold_start",
        title="First mail from a new sender",
        subset=STORED_SCORES_SUBSET,
        scenario_ids=("S09",),
        variants=("cold_start_legitimate",),
        misdirected=False,
        stored_decision="allow",
        pick="median",
        rule="The S09 cold-start draft (a sender with no earlier mail) at the median email risk score among those the policy allowed on validation_product_like.",
    ),
)

# Failure demonstrations derived from the routine example by rule.
# - unknown address: the first To address with the last letter of its local
#   part removed, which must not be in the directory
# - invalid input: the first To address with "@" replaced by "."
FAILURE_BASE_EXAMPLE = "routine"

# Kinds the API contract gives each code (docs/phase_6/API_CONTRACT.md). The UI
# shows the API's own code and text; this only labels the column.
CODE_KINDS = {
    "CONTENT_RELATIONSHIP_MISMATCH": "reason",
    "EXTERNAL_RECIPIENT": "context",
    "LOOKALIKE_CONTACT_CONTEXT": "context",
    "UNUSUAL_RECIPIENT_COMBINATION": "context",
    "LIMITED_RELATIONSHIP_HISTORY": "evidence limitation",
    "LIMITED_TEXT": "evidence limitation",
}

# ------------------------------------------------------------- walkthrough

DOCS_DIR = "docs/phase_7"
WALKTHROUGH_FILE = "WALKTHROUGH.md"
# The walkthrough document quotes the recorded single test pass for the known
# misses. It is read only for that sentence, never for examples or exploration.
TEST_EVALUATION_FILE = "test_evaluation.json"
KNOWN_MISS_SCENARIOS = ("S01", "S04", "S11")
# Desired outcomes for walkthrough steps that are not a single scenario, from
# the narrative walkthrough and safeguards in docs/phase_1/SCENARIOS.md.
WALKTHROUGH_DESIRED = {
    "reassess": "Reassess the edited draft as a new request. Removing one suspicious recipient does not guarantee allow if another remains risky.",
    "exploration": "Threshold exploration is a simulation, visibly distinct from the default policy.",
    "feedback": "User corrections require review before becoming labels; feedback never silently changes the deployed model.",
}
