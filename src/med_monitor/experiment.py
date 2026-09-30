"""Sample-size arithmetic for the sender-level A/B test proposal.

This is proposal arithmetic. No online experiment has been run, no real user
has seen a warning, and nothing here is evidence about a live system. The
functions take a baseline and a target and return how many emails or senders a
future test would need under stated assumptions.

The two arms run the same frozen policy on the same kind of draft, so the
policy's scores, warnings, and recall are identical in both by construction.
What the arms can differ on is what senders do with a warning. The primary
outcome is therefore behavioral: the share of policy-warned mistakes that the
sender corrects before sending. Model recall is reported as a descriptive
number and sets how many warned mistakes a test can expect to see.
"""

from __future__ import annotations

import math

from scipy.stats import binom, norm

from med_monitor.version import (
    EXPERIMENT_ACCEPTANCE_RATES,
    EXPERIMENT_ALPHA,
    EXPERIMENT_BASELINE_CORRECTION_RATES,
    EXPERIMENT_EMAILS_PER_SENDER,
    EXPERIMENT_ICC_VALUES,
    EXPERIMENT_POWER,
    EXPERIMENT_PREVALENCE,
    STOP_FOR_HARM_ALPHA,
)


def design_effect(cluster_size: float, icc: float) -> float:
    """Variance inflation from randomizing whole senders: 1 + (m - 1) * icc."""
    return 1.0 + (cluster_size - 1.0) * icc


def two_proportion_n(p1: float, p2: float, alpha: float = EXPERIMENT_ALPHA, power: float = EXPERIMENT_POWER) -> int:
    """Units per arm to detect p1 versus p2 (two-sided, normal approximation)."""
    if p1 == p2:
        raise ValueError("The two proportions are equal")
    z_alpha, z_power = norm.ppf(1 - alpha / 2), norm.ppf(power)
    pooled = (p1 + p2) / 2
    spread = z_alpha * math.sqrt(2 * pooled * (1 - pooled)) + z_power * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    return math.ceil(spread**2 / (p1 - p2) ** 2)


def zero_event_n(rate_per_1000: float, confidence: float = 1 - EXPERIMENT_ALPHA) -> int:
    """Legitimate emails per arm so that zero false interventions bound the rate at or below `rate_per_1000`."""
    return math.ceil(-math.log(1 - confidence) / (rate_per_1000 / 1000.0))


def stop_for_harm_count(legitimate: int, budget_per_1000: float, alpha: float = STOP_FOR_HARM_ALPHA) -> int:
    """Smallest count of confirmed false interventions that would be this unlikely at the budget rate."""
    rate = budget_per_1000 / 1000.0
    count = 0
    while binom.sf(count - 1, legitimate, rate) > alpha:
        count += 1
    return count


def sender_scaling(emails: int, icc: float, cluster_size: float = EXPERIMENT_EMAILS_PER_SENDER) -> dict:
    effect = design_effect(cluster_size, icc)
    inflated = math.ceil(emails * effect)
    return {"icc": icc, "design_effect": effect, "emails": inflated, "senders": math.ceil(inflated / cluster_size)}


def correction_rate_with_warning(baseline: float, acceptance: float) -> float:
    """Correction rate of a warned mistake when the warning is shown.

    Without a warning a sender fixes it at the baseline rate. With one, a
    further `acceptance` share of the rest is fixed.
    """
    return baseline + (1.0 - baseline) * acceptance


def primary_table(warned_recall: float) -> list[dict]:
    """Primary outcome: correction rate among policy-warned mistakes, treatment against control.

    Positives per arm are confirmed warned mistakes. A mistake is warned with
    probability `warned_recall`, so emails per arm = positives / (prevalence * recall).
    """
    rows = []
    for baseline in EXPERIMENT_BASELINE_CORRECTION_RATES:
        for acceptance in EXPERIMENT_ACCEPTANCE_RATES:
            treated = correction_rate_with_warning(baseline, acceptance)
            positives = two_proportion_n(baseline, treated)
            emails = math.ceil(positives / (EXPERIMENT_PREVALENCE * warned_recall))
            rows.append(
                {
                    "baseline_correction": baseline,
                    "acceptance": acceptance,
                    "treated_correction": treated,
                    "confirmed_warned_mistakes_per_arm": positives,
                    "emails_per_arm_if_independent": emails,
                    "with_sender_clustering": [sender_scaling(emails, icc) for icc in EXPERIMENT_ICC_VALUES],
                }
            )
    return rows


def sent_mistake_table(warned_recall: float) -> list[dict]:
    """Secondary outcome: misdirected emails still on their way out at send, per email.

    Only warned mistakes can change, so the difference is small against a rate that is
    already about half a percent; this is why it is not the primary outcome.
    """
    rows = []
    for baseline in EXPERIMENT_BASELINE_CORRECTION_RATES:
        for acceptance in EXPERIMENT_ACCEPTANCE_RATES:
            control = EXPERIMENT_PREVALENCE * (1.0 - baseline)
            treated = control * (1.0 - warned_recall * acceptance)
            emails = two_proportion_n(control, treated)
            rows.append(
                {
                    "baseline_correction": baseline,
                    "acceptance": acceptance,
                    "control_sent_per_1000": 1000 * control,
                    "treated_sent_per_1000": 1000 * treated,
                    "emails_per_arm_if_independent": emails,
                }
            )
    return rows


def warning_rate_table(baseline_rate: float, ratios=(2.0,)) -> list[dict]:
    rows = []
    for ratio in ratios:
        emails = two_proportion_n(baseline_rate, baseline_rate * ratio)
        rows.append(
            {
                "baseline_rate": baseline_rate,
                "target_rate": baseline_rate * ratio,
                "emails_per_arm_if_independent": emails,
                "with_sender_clustering": [sender_scaling(emails, icc) for icc in EXPERIMENT_ICC_VALUES],
            }
        )
    return rows


def false_intervention_guardrail(budget_per_1000: float) -> dict:
    legitimate = zero_event_n(budget_per_1000)
    return {
        "budget_per_1000": budget_per_1000,
        "legitimate_emails_per_arm_for_zero_count_bound": legitimate,
        "with_sender_clustering": [sender_scaling(legitimate, icc) for icc in EXPERIMENT_ICC_VALUES],
        "stop_for_harm_confirmed_false_interventions": stop_for_harm_count(legitimate, budget_per_1000),
        "stop_for_harm_at_legitimate_emails": legitimate,
    }


def design(reference: dict) -> dict:
    """The whole proposal table from the stored reference numbers."""
    validation = reference["policy_reference"]["validation"]
    warned_recall = validation["warned_mistakes"] / validation["misdirected"]
    warning_rate = validation["warnings"] / validation["emails"]
    budget = 1.0
    return {
        "status": "proposal: no online evidence",
        "alpha": EXPERIMENT_ALPHA,
        "power": EXPERIMENT_POWER,
        "assumed_prevalence": EXPERIMENT_PREVALENCE,
        "assumed_emails_per_sender": EXPERIMENT_EMAILS_PER_SENDER,
        "icc_values": list(EXPERIMENT_ICC_VALUES),
        "baseline_correction_rates": list(EXPERIMENT_BASELINE_CORRECTION_RATES),
        "acceptance_rates": list(EXPERIMENT_ACCEPTANCE_RATES),
        "descriptive_recall": {
            "value": warned_recall,
            "warned_mistakes": validation["warned_mistakes"],
            "misdirected": validation["misdirected"],
            "source": "validation product-like, the subset that chose the cutoff; not independent of it",
            "identical_in_both_arms": True,
        },
        "baseline_warning_rate_source": "validation product-like, the subset that chose the cutoff",
        "primary": primary_table(warned_recall),
        "sent_mistakes": sent_mistake_table(warned_recall),
        "warning_rate": warning_rate_table(warning_rate),
        "false_interventions": false_intervention_guardrail(budget),
        "latency": {"p95_limit_ms": 300.0, "requests_per_arm_minimum": 1000},
    }
