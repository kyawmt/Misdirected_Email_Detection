"""Threshold-policy version.

Bump POLICY_VERSION when the selection rule, the budget definition, or the
decision contract changes. A new policy version gets a new artifact directory
and a new one-shot test evaluation.
"""

POLICY_VERSION = "med-policy-v1"
SEED = 20260926
N_BOOTSTRAP = 1000
# AC01: false interventions per 1,000 legitimate emails.
BUDGET_PER_1000 = 1.0
SELECTION_SUBSET = "validation_product_like"
DIAGNOSTIC_SUBSET = "validation_diagnostic"
TEST_SUBSETS = ("test_product_like", "test_diagnostic")
PREVALENCES = (0.001, 0.005, 0.01, 0.02)


class PolicyError(ValueError):
    """A policy cannot be selected, loaded, or applied under this contract."""
