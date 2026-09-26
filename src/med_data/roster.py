"""Fictional directory, weekly lanes, and per-split draft quotas.

Quotas are the dataset contract. The generator and the validator both read them.
"""

from dataclasses import dataclass, field
from datetime import datetime

from med_data.calendar import parse_ts

DIRECTORY_OPEN = parse_ts("2024-01-01T00:00:00Z")

FIRST_NAMES = (
    "Blair", "Casey", "Drew", "Emery", "Finley", "Gray", "Hayden", "Indigo",
    "Jules", "Kendall", "Logan", "Marlow", "Nico", "Oakley", "Parker", "Reese",
    "Shay", "Tatum", "Umber", "Val", "Winter", "Yael", "Arden", "Briar",
)
LAST_NAMES = (
    "Santos", "Ibarra", "Okada", "Silva", "Cohen", "Diaz", "Farouk", "Gupta",
    "Hassan", "Ivers", "Johal", "Kaur", "Laurent", "Moreau", "Nasser", "Okafor",
    "Pereira", "Quint", "Sato", "Tremblay", "Ueda", "Vasquez", "Walker", "Yoon",
)
PARTNER_BRANDS = (
    "northwind", "harborlight", "brightlane", "cedarline", "dovetail",
    "eastfield", "fairhaven", "goldacre", "highmeadow", "ionbridge",
    "juniperlane", "keelson", "larkspur", "maplecourt", "nimbusgate",
    "oakbarrel",
)


@dataclass(frozen=True)
class Contact:
    contact_id: str
    display_name: str
    email_address: str
    domain: str
    is_internal: bool
    department: str
    directory_visible_from: datetime


@dataclass(frozen=True)
class Lane:
    sender: str
    to: tuple[str, ...]
    cc: tuple[str, ...]
    bcc: tuple[str, ...]
    topic: str
    days: tuple[int, ...]
    repeats: int = 1


@dataclass(frozen=True)
class SplitPlan:
    product_total: int
    product_subset: str
    diagnostic_subset: str | None
    # Misdirected assessment drafts in the product-like subset.
    misdirected: dict[str, int]
    # Legitimate hard negatives included in the product-like total.
    hard_negative: dict[str, int]
    # Diagnostic challenge counts, before clean twins are added.
    diagnostic_misdirected: dict[str, int] = field(default_factory=dict)
    diagnostic_legitimate: dict[str, int] = field(default_factory=dict)
    # Authored walkthrough drafts. Counts are included only on the test plan.
    walkthrough: dict[str, int] = field(default_factory=dict)

    @property
    def product_misdirected_count(self) -> int:
        return sum(self.misdirected.values())

    @property
    def product_hard_count(self) -> int:
        return sum(self.hard_negative.values())

    @property
    def routine_count(self) -> int:
        remaining = self.product_total - self.product_misdirected_count - self.product_hard_count
        if remaining < 0:
            raise ValueError(f"{self.product_subset} quotas exceed product_total")
        return remaining


def _contact(contact_id: str, display_name: str, email: str, department: str, visible: datetime) -> Contact:
    domain = email.split("@", 1)[1]
    return Contact(
        contact_id=contact_id,
        display_name=display_name,
        email_address=email,
        domain=domain,
        is_internal=domain == "demo.example",
        department=department,
        directory_visible_from=visible,
    )


def core_contacts() -> list[Contact]:
    rows = [
        ("c_maya", "Maya Okonkwo", "maya@demo.example", "Operations"),
        ("c_alex_chan", "Alex Chan", "alex.chan@demo.example", "Staffing"),
        ("c_alex_chen", "Alex Chen", "alex.chen@demo.example", "Workplace"),
        ("c_sam", "Sam Rivera", "sam@demo.example", "Facilities"),
        ("c_priya", "Priya Shah", "priya@demo.example", "People"),
        ("c_noah", "Noah Kim", "noah@demo.example", "Program Delivery"),
        ("c_elena", "Elena Rossi", "elena@demo.example", "Program Delivery"),
        ("c_taylor", "Taylor Brooks", "taylor@demo.example", "Program Delivery"),
        ("c_lena", "Lena Owens", "lena@demo.example", "Program Delivery"),
        ("c_chris", "Chris Patel", "chris@demo.example", "Finance"),
        ("c_marcus", "Marcus Bell", "marcus@demo.example", "Finance"),
        ("c_avery", "Avery Nguyen", "avery@demo.example", "Staffing"),
        ("c_devon", "Devon Clark", "devon@demo.example", "Staffing"),
        ("c_quinn", "Quinn Adler", "quinn@demo.example", "People"),
        ("c_hana", "Hana Ito", "hana@demo.example", "Facilities"),
        ("c_jamie_lee", "Jamie Lee", "jamie.lee@demo.example", "Staffing"),
        ("c_jamie_li", "Jamie Li", "jamie.li@demo.example", "Workplace"),
        ("c_morgan_shaw", "Morgan Shaw", "morgan.shaw@demo.example", "Staffing"),
        ("c_morgan_zhao", "Morgan Zhao", "morgan.zhao@demo.example", "Workplace"),
        ("c_lee", "Lee Park", "lee@vendor.example", "Vendor Scheduling"),
        ("c_pat", "Pat Okada", "pat@parts.example", "Vendor Scheduling"),
        ("c_ren", "Ren Cho", "ren@logistics.example", "Vendor Scheduling"),
    ]
    return [_contact(cid, name, email, dept, DIRECTORY_OPEN) for cid, name, email, dept in rows]


# (intended contact, lookalike contact). Index 0 is the canonical walkthrough pair.
LOOKALIKE_PAIRS = (
    ("c_alex_chan", "c_alex_chen"),
    ("c_jamie_lee", "c_jamie_li"),
    ("c_morgan_shaw", "c_morgan_zhao"),
)
VENDORS = ("c_lee", "c_pat", "c_ren")
MAYA = "c_maya"
PROJECT_TO = ("c_noah", "c_elena", "c_taylor")
PROJECT_CC = ("c_chris",)
PROJECT_BCC = ("c_lena",)
SAM = "c_sam"
PRYA = "c_priya"
QUINN = "c_quinn"
NOAH = "c_noah"
LEE = "c_lee"

# Canonical walkthrough identities required by the scenario list.
JORDAN = _contact("c_jordan", "Jordan Hale", "jordan@demo.example", "Program Delivery", DIRECTORY_OPEN)
RINA = _contact("c_rina", "Rina Costa", "rina@newpartner.example", "External Partner", DIRECTORY_OPEN)
ELLIOT = _contact("c_elliot", "Elliot Berg", "elliot.berg@demo.example", "Operations", DIRECTORY_OPEN)

DIAGNOSTIC_MIS = {
    "s01": 4,
    "s02": 4,
    "s04": 4,
    "s08_cc": 4,
    "s08_bcc": 4,
    "s08_two": 4,
    "s09_little_bad": 4,
}
DIAGNOSTIC_LEG = {
    "s08_all": 1,
    "s03": 1,
    "s06": 1,
    "s07": 1,
    "s05_internal": 1,
    "s05_external": 1,
    "s09_cold": 1,
    "s09_little_ok": 1,
}

PLANS: dict[str, SplitPlan] = {
    "train": SplitPlan(
        product_total=1000,
        product_subset="train",
        diagnostic_subset=None,
        misdirected={
            "s01": 24,
            "s02": 24,
            "s04": 20,
            "s08_cc": 10,
            "s08_bcc": 8,
            "s08_two": 8,
            "s09_little_bad": 6,
        },
        hard_negative={
            "s03": 4,
            "s06": 4,
            "s07": 4,
            "s09_cold": 4,
            "s09_little_ok": 4,
        },
    ),
    "validation": SplitPlan(
        product_total=1000,
        product_subset="validation_product_like",
        diagnostic_subset="validation_diagnostic",
        misdirected={"s01": 1, "s02": 1, "s04": 1, "s08_cc": 1, "s08_two": 1},
        hard_negative={"s03": 3, "s06": 3, "s07": 3, "s09_cold": 2, "s09_little_ok": 2},
        diagnostic_misdirected=dict(DIAGNOSTIC_MIS),
        diagnostic_legitimate=dict(DIAGNOSTIC_LEG),
    ),
    "test": SplitPlan(
        product_total=2000,
        product_subset="test_product_like",
        diagnostic_subset="test_diagnostic",
        misdirected={"s01": 3, "s02": 3, "s04": 2, "s08_cc": 1, "s08_two": 1},
        hard_negative={"s03": 4, "s06": 4, "s07": 4, "s09_cold": 3, "s09_little_ok": 3},
        diagnostic_misdirected=dict(DIAGNOSTIC_MIS),
        diagnostic_legitimate=dict(DIAGNOSTIC_LEG),
        walkthrough={
            "s05_internal": 1,
            "s05_external": 1,
            "s01": 1,
            "s02": 1,
            "s03": 1,
            "s04": 1,
            "s06": 1,
            "s07": 1,
            "s08_all": 1,
            "s08_cc": 1,
            "s08_bcc": 1,
            "s08_two": 1,
            "s09_cold": 1,
            "s09_little_ok": 1,
            "s09_little_bad": 1,
        },
    ),
}

KIND_META = {
    "s01": ("S01", "lookalike_replacement"),
    "s02": ("S02", "added_external"),
    "s03": ("S03", "legitimate_first_contact"),
    "s04": ("S04", "familiar_topic_mismatch"),
    "s05_internal": ("S05", "internal_project"),
    "s05_external": ("S05", "external_purchase"),
    "s06": ("S06", "legitimate_new_domain"),
    "s07": ("S07", "legitimate_topic_change"),
    "s08_all": ("S08", "all_intended"),
    "s08_cc": ("S08", "unintended_cc"),
    "s08_bcc": ("S08", "unintended_bcc"),
    "s08_two": ("S08", "two_unintended"),
    "s09_cold": ("S09", "cold_start_legitimate"),
    "s09_little_ok": ("S09", "little_text_legitimate"),
    "s09_little_bad": ("S09", "little_text_unintended"),
}

# Sent-mail topic allow-list for contacts whose history must stay clean.
# Absence from this map means the contact is unrestricted.
RESTRICTED_TOPICS = {
    "c_alex_chan": frozenset({"staffing"}),
    "c_alex_chen": frozenset({"office_equipment"}),
    "c_jamie_lee": frozenset({"staffing"}),
    "c_jamie_li": frozenset({"office_equipment"}),
    "c_morgan_shaw": frozenset({"staffing"}),
    "c_morgan_zhao": frozenset({"office_equipment"}),
    "c_lee": frozenset({"purchase_scheduling"}),
    "c_pat": frozenset({"purchase_scheduling"}),
    "c_ren": frozenset({"purchase_scheduling"}),
    "c_hana": frozenset({"facilities"}),
    "c_sam": frozenset({"facilities", "kickoff"}),
}


def s07_count(split: str) -> int:
    plan = PLANS[split]
    return plan.hard_negative.get("s07", 0) + plan.diagnostic_legitimate.get("s07", 0)


def s04_pool_size() -> int:
    return 4


def new_person_count(split: str, kind: str) -> int:
    """Unique people for one-shot legitimate or cold-start cases, including walkthrough."""
    plan = PLANS[split]
    return (
        plan.hard_negative.get(kind, 0)
        + plan.diagnostic_legitimate.get(kind, 0)
        + plan.walkthrough.get(kind, 0)
    )
