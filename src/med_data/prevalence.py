"""Illustrative precision under alternative prevalence assumptions.

These figures are algebra on a hypothetical operating point. They are not
measurements of a trained detector.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class IllustrativePoint:
    prevalence: float
    precision: float


def precision_from_rates(recall: float, false_positive_rate: float, prevalence: float) -> float:
    """Email precision if recall and the legitimate false-intervention rate stay fixed.

    precision = (recall * p) / (recall * p + fpr * (1 - p))
    """
    if not 0.0 < prevalence < 1.0:
        raise ValueError("prevalence must be between 0 and 1")
    if not 0.0 <= recall <= 1.0 or not 0.0 <= false_positive_rate <= 1.0:
        raise ValueError("rates must be between 0 and 1")
    true_positive = recall * prevalence
    false_positive = false_positive_rate * (1.0 - prevalence)
    denominator = true_positive + false_positive
    if denominator == 0.0:
        raise ValueError("precision is undefined when there are no interventions")
    return true_positive / denominator


def illustrative_table(
    recall: float = 0.5,
    false_positive_rate: float = 0.001,
    prevalences: tuple[float, ...] = (0.001, 0.005, 0.01, 0.02),
) -> list[IllustrativePoint]:
    """Show how precision would move if prevalence changed and error rates did not.

    The default false-positive rate matches the provisional budget of one false
    intervention per 1,000 legitimate emails. The recall value is hypothetical.
    """
    return [
        IllustrativePoint(
            prevalence=prevalence,
            precision=precision_from_rates(recall, false_positive_rate, prevalence),
        )
        for prevalence in prevalences
    ]
