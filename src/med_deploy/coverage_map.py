"""Where each Phase 9 test topic is covered.

Existing tests are cited, not copied. Each entry names a test and the layer that
runs it: `ci` (the fast selection, `-m "not slow"`) or `release` (marked slow,
run by the full `pytest`). A test checks that every name exists and that its
layer matches its `slow` marker, so this map cannot point at a test that was
renamed or moved between layers.
"""

from __future__ import annotations

# topic -> ((test node, layer), ...)
COVERAGE = {
    "Timestamp-correct history (sent_at strictly earlier; same family and copied non-empty body excluded)": (
        ("tests/test_phase3.py::test_counts_recency_window_and_exclusions", "ci"),
        ("tests/test_phase3.py::test_earlier_draft_ignores_later_mail", "ci"),
        ("tests/test_phase3.py::test_history_index_matches_visible_history_ids", "ci"),
        ("tests/test_phase3.py::test_similarity_excludes_self_and_future_contacts", "ci"),
        ("tests/test_phase2.py::test_walkthrough_history_respects_relationships", "ci"),
        ("tests/test_phase3.py::test_real_history_and_scoring_view_agree", "release"),
        ("tests/test_phase2.py::test_published_contract_passes_validation", "release"),
    ),
    "Split and frozen-subset protections": (
        ("tests/test_phase3.py::test_export_and_quality_report_refuse_frozen_subsets", "ci"),
        ("tests/test_phase4.py::test_frozen_subset_is_refused", "ci"),
        ("tests/test_phase5.py::test_no_writer_for_frozen_feature_files", "ci"),
        ("tests/test_phase6.py::test_no_frozen_test_writer_or_fixture", "ci"),
        ("tests/test_phase7.py::test_frozen_subset_drafts_are_refused", "ci"),
        ("tests/test_phase7.py::test_catalog_never_materializes_frozen_records", "ci"),
        ("tests/test_phase8.py::test_frozen_and_non_validation_drafts_are_refused", "ci"),
        ("tests/test_phase8.py::test_no_monitor_command_opens_a_file_that_stores_test_results", "ci"),
        ("tests/test_phase9.py::test_frozen_draft_ids_are_refused_by_the_phase_9_paths", "ci"),
        ("tests/test_phase9.py::test_no_phase_9_path_opens_a_file_with_frozen_outcomes", "ci"),
    ),
    "Train/serve feature parity": (
        ("tests/test_phase3.py::test_batch_single_reload_and_scoring_view_match", "ci"),
        ("tests/test_phase5.py::test_batch_and_single_draft_scores_agree_at_the_cutoff", "ci"),
        ("tests/test_phase5.py::test_published_policy_matches_its_validation_table", "ci"),
        ("tests/test_phase9.py::test_fixtures_are_validation_only_and_chosen_by_rule", "ci"),
        ("tests/test_phase4.py::test_score_query_matches_batch_and_scoring_view", "release"),
    ),
    "Threshold equality": (
        ("tests/test_phase5.py::test_threshold_equality_warns_and_below_allows", "ci"),
        ("tests/test_phase6.py::test_score_equal_to_t_warn_warns_through_the_api", "ci"),
        ("tests/test_phase9.py::test_threshold_equality_through_the_api_and_the_decision_function", "ci"),
    ),
    "Cold start and limited text": (
        ("tests/test_phase6.py::test_empty_subject_and_body_still_assess_with_limited_text", "ci"),
        ("tests/test_phase9.py::test_scenario_fixtures_replay_against_the_frozen_bundle", "ci"),
    ),
    "Malformed requests": (
        ("tests/test_phase6.py::test_invalid_input_has_no_score_and_no_allow", "ci"),
        ("tests/test_phase6.py::test_malformed_json_is_invalid_input", "ci"),
        ("tests/test_phase9.py::test_scenario_fixtures_replay_against_the_frozen_bundle", "ci"),
    ),
    "Duplicate addresses, several recipients, and maximum aggregation": (
        ("tests/test_phase6.py::test_repeated_address_merges_roles_before_transform", "ci"),
        ("tests/test_phase5.py::test_max_aggregation_flags_every_recipient_and_counts_one_intervention", "ci"),
        ("tests/test_phase4.py::test_email_risk_is_the_max_and_two_mistakes_count_once", "ci"),
        ("tests/test_phase9.py::test_scenario_fixtures_replay_against_the_frozen_bundle", "ci"),
    ),
    "Provenance and the score contract": (
        ("tests/test_phase6.py::test_no_block_and_the_model_note_matches_the_model", "ci"),
        ("tests/test_phase9.py::test_the_comparator_detects_a_changed_decision_score_provenance_or_limitation", "ci"),
    ),
    "Failure clarity (unable_to_assess is never an allow)": (
        ("tests/test_phase6.py::test_missing_policy_is_unavailable_and_ready_fails", "ci"),
        ("tests/test_phase6.py::test_checksum_mismatch_is_unavailable", "ci"),
        ("tests/test_phase6.py::test_health_works_when_bundle_path_is_missing", "ci"),
        ("tests/test_phase8.py::test_a_mismatched_bundle_is_refused_and_never_allowed", "ci"),
        ("tests/test_phase9.py::test_an_unable_to_assess_that_carries_a_decision_is_detected", "ci"),
        ("tests/test_phase9.py::test_a_broken_bundle_fails_every_assessed_fixture", "ci"),
        ("tests/test_phase9.py::test_a_failing_candidate_process_fails_closed", "ci"),
        ("tests/test_phase9.py::test_the_rehearsal_fails_when_the_ui_container_is_not_healthy", "ci"),
    ),
    "End to end: the review screen and the API together": (
        ("tests/test_phase9.py::test_smoke_passes_end_to_end_over_http", "ci"),
        ("tests/test_phase9.py::test_smoke_reports_a_service_that_is_not_ready", "ci"),
    ),
    "Packaging: pins, images, compose, CI": (
        ("tests/test_phase9.py::test_constraints_are_exact_portable_and_cover_every_dependency", "ci"),
        ("tests/test_phase9.py::test_dockerfiles_pin_the_base_and_ship_what_the_process_reads", "ci"),
        ("tests/test_phase9.py::test_the_shipped_modules_run_without_the_others", "ci"),
        ("tests/test_phase9.py::test_compose_publishes_on_loopback_and_hardens_the_containers", "ci"),
        ("tests/test_phase9.py::test_ci_workflow_runs_the_compact_checks_and_never_retrains", "ci"),
        ("tests/test_phase9.py::test_published_bundle_passes_the_check_and_a_damaged_copy_fails", "ci"),
        ("tests/test_phase9.py::test_a_file_changed_without_changing_its_shape_fails_the_digest_check", "ci"),
    ),
}
