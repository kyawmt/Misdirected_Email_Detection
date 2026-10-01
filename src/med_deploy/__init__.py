"""Testing and local deployment checks for the served bundle.

Phase 9 adds no model, feature, policy, dataset, or API change. It verifies the
published bundle, replays fixed validation fixtures through the API, runs the
API and the review screen together, measures warm latency, packages both for
local containers, and rehearses a rollback. It never retrains, refits, or scores
a frozen test draft. Every stored record is fictional and validation-only.
"""
