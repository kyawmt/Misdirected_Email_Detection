"""Monitoring, reviewed feedback, and rollout evidence for the served bundle.

The monitor is a client of the scoring API and a reader of the published
validation data and feature artifacts. It fits nothing, recalibrates nothing,
and never changes a model, a policy, or the cutoff. It never reads a frozen
test row. Stored records are aggregates: no address, name, subject, body, or
per-draft score is written.
"""
