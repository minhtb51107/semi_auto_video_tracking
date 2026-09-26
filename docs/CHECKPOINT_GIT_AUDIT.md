# Checkpoint Git audit

This checkpoint includes the previously uncommitted Analyzer v2, external validation/evaluation tools, offline human-review preparation and CVAT adapter, plus Phase5A hardening. The baseline repository had one initial commit. No history rewrite or force push is planned.

## Audit outcome before staging

- Modified tracked files: `.gitignore`, `README.md`; existing README edits retained and current phase links added.
- Source/tests/docs/config and curated small text evidence selected below. No new model/tracker/threshold change in this phase.
- `git status`, `git diff`, `git diff --cached` inspected; index was empty initially.
- Full suite74/74 PASS immediately before checkpoint; see `outputs/robustness/tests.log`.
- Known local CVAT credential scan and suspicious credential-assignment scan found no matches in selected/current text files. All608 existing Git blob objects, including unreachable objects that could remain from staging, were scanned for the known token; no matches. This cannot prove an already-pruned historical object never existed.
- `.env` is ignored, untracked and excluded; `.env.example` uses a placeholder. No secret values appear in this report.
- Branch `main`; remote `origin` = https://github.com/minhtb51107/semi_auto_video_tracking.git. Commit/push outcome is reported after Git execution; this precommit report does not claim success prematurely.

## Intentionally excluded / retained locally

- `.env`, virtual environment, model weights, Python caches, `.runtime/`.
- `data/external_validation/`: acquired dataset images/labels and source copies, not republished in this checkpoint.
- Generated external/regression image visualizations and logs; human review generated HTML/assets/images, QA screenshots, manifests and collected session directory.
- Offline synthetic CVAT dry-run fixtures, manual-import ZIPs, first acquisition/preservation manifests and live snapshot with incidental server account metadata. Curated live event/state/hash evidence is included.
- Machine-local exhaustive inventory `outputs/checkpoint_audit/local_inventory.json` contains separate modified/new/ignored/generated-file selections. It stays ignored to avoid publishing thousands of local environment/cache paths.

No files were deleted for this cleanup. The omitted media and generated packages remain local. A fresh clone can run the full unit suite with the documented Python/Node dependencies and bundled internal fixtures; external media visualizations/pilot rebuilds require acquiring the documented inputs. Existing offline demo paths in historical docs refer to local generated artifacts, not files guaranteed in this Git checkpoint. Human pilot stays PREPARED_NOT_EXECUTED.

## Exact selected paths

```text
.env.example
.gitignore
README.md
configs/review_v2.json
docs/ANALYZER_V2_FUTURE_SIGNALS.md
docs/ANALYZER_V2_IMPLEMENTATION_PLAN.md
docs/ANALYZER_V2_PLAN.md
docs/ANALYZER_V2_RESULTS.md
docs/CHECKPOINT_GIT_AUDIT.md
docs/CVAT_INTEGRATION_GUIDE.md
docs/CVAT_INTEGRATION_PLAN.md
docs/CVAT_INTEGRATION_RESULTS.md
docs/CVAT_LIVE_VERIFICATION.md
docs/EXTERNAL_DATASET.md
docs/EXTERNAL_VALIDATION_02_DATASET.md
docs/EXTERNAL_VALIDATION_02_RESULTS.md
docs/EXTERNAL_VALIDATION_COMPARISON.md
docs/EXTERNAL_VALIDATION_RESULTS.md
docs/HUMAN_PILOT_V2_PLAN.md
docs/HUMAN_REVIEW_PILOT_STATUS.md
docs/HUMAN_REVIEW_PROTOCOL.md
docs/KITTI_EVALUATION_ADAPTER.md
docs/KITTI_EVALUATION_RESULTS.md
docs/ROBUSTNESS_PLAN.md
docs/ROBUSTNESS_RESULTS.md
outputs/analyzer_v2_regression/clip_01/compat_v1/review_flags.csv
outputs/analyzer_v2_regression/clip_01/compat_v1/review_flags.json
outputs/analyzer_v2_regression/clip_01/exact_original_path_compat/review_flags.csv
outputs/analyzer_v2_regression/clip_01/exact_original_path_compat/review_flags.json
outputs/analyzer_v2_regression/clip_01/v1/review_flags.csv
outputs/analyzer_v2_regression/clip_01/v1/review_flags.json
outputs/analyzer_v2_regression/clip_01/v2/review_events.csv
outputs/analyzer_v2_regression/clip_01/v2/review_events.json
outputs/analyzer_v2_regression/clip_01/v2/review_flags_v2.csv
outputs/analyzer_v2_regression/clip_01/v2/review_flags_v2.json
outputs/analyzer_v2_regression/clip_02/compat_v1/review_flags.csv
outputs/analyzer_v2_regression/clip_02/compat_v1/review_flags.json
outputs/analyzer_v2_regression/clip_02/exact_original_path_compat/review_flags.csv
outputs/analyzer_v2_regression/clip_02/exact_original_path_compat/review_flags.json
outputs/analyzer_v2_regression/clip_02/v1/review_flags.csv
outputs/analyzer_v2_regression/clip_02/v1/review_flags.json
outputs/analyzer_v2_regression/clip_02/v2/review_events.csv
outputs/analyzer_v2_regression/clip_02/v2/review_events.json
outputs/analyzer_v2_regression/clip_02/v2/review_flags_v2.csv
outputs/analyzer_v2_regression/clip_02/v2/review_flags_v2.json
outputs/analyzer_v2_regression/frozen_runtime.json
outputs/analyzer_v2_regression/integrity_final.json
outputs/analyzer_v2_regression/issue_capture.csv
outputs/analyzer_v2_regression/kitti_0000/compat_v1/review_flags.csv
outputs/analyzer_v2_regression/kitti_0000/compat_v1/review_flags.json
outputs/analyzer_v2_regression/kitti_0000/exact_original_path_compat/review_flags.csv
outputs/analyzer_v2_regression/kitti_0000/exact_original_path_compat/review_flags.json
outputs/analyzer_v2_regression/kitti_0000/v1/review_flags.csv
outputs/analyzer_v2_regression/kitti_0000/v1/review_flags.json
outputs/analyzer_v2_regression/kitti_0000/v2/review_events.csv
outputs/analyzer_v2_regression/kitti_0000/v2/review_events.json
outputs/analyzer_v2_regression/kitti_0000/v2/review_flags_v2.csv
outputs/analyzer_v2_regression/kitti_0000/v2/review_flags_v2.json
outputs/analyzer_v2_regression/kitti_0001/compat_v1/review_flags.csv
outputs/analyzer_v2_regression/kitti_0001/compat_v1/review_flags.json
outputs/analyzer_v2_regression/kitti_0001/exact_original_path_compat/review_flags.csv
outputs/analyzer_v2_regression/kitti_0001/exact_original_path_compat/review_flags.json
outputs/analyzer_v2_regression/kitti_0001/v1/review_flags.csv
outputs/analyzer_v2_regression/kitti_0001/v1/review_flags.json
outputs/analyzer_v2_regression/kitti_0001/v2/review_events.csv
outputs/analyzer_v2_regression/kitti_0001/v2/review_events.json
outputs/analyzer_v2_regression/kitti_0001/v2/review_flags_v2.csv
outputs/analyzer_v2_regression/kitti_0001/v2/review_flags_v2.json
outputs/analyzer_v2_regression/known_duplicate_geometry.csv
outputs/analyzer_v2_regression/new_candidate_labels.csv
outputs/analyzer_v2_regression/preservation_before.json
outputs/analyzer_v2_regression/summary.json
outputs/checkpoint_audit/secret_scan.json
outputs/cvat_integration/live_task_6_job_4/dry-run.json
outputs/cvat_integration/live_task_6_job_4/first_push_evidence.json
outputs/cvat_integration/live_task_6_job_4/navigation.md
outputs/cvat_integration/live_task_6_job_4/push.json
outputs/cvat_integration/live_task_6_job_4/request_plan.json
outputs/cvat_integration/live_task_6_job_4/resolved_roundtrip.json
outputs/cvat_integration/live_task_6_job_4/state.json
outputs/cvat_integration/live_task_6_job_4/verify.json
outputs/external_validation/kitti_0000/adjudications.json
outputs/external_validation/kitti_0000/artifact_manifest.json
outputs/external_validation/kitti_0000/association_by_frame.csv
outputs/external_validation/kitti_0000/blind_lock.json
outputs/external_validation/kitti_0000/blind_protocol.json
outputs/external_validation/kitti_0000/confirmed_missed_events.csv
outputs/external_validation/kitti_0000/dataset_statistics.json
outputs/external_validation/kitti_0000/evaluation.json
outputs/external_validation/kitti_0000/final_integrity.json
outputs/external_validation/kitti_0000/flag_labels.csv
outputs/external_validation/kitti_0000/integrity_verified.json
outputs/external_validation/kitti_0000/issue_candidates.csv
outputs/external_validation/kitti_0000/kitti_semantics/adjusted_clear_matches.csv
outputs/external_validation/kitti_0000/kitti_semantics/evaluation.json
outputs/external_validation/kitti_0000/kitti_semantics/gt_preprocessing_audit.csv
outputs/external_validation/kitti_0000/kitti_semantics/prediction_preprocessing_audit.csv
outputs/external_validation/kitti_0000/missed_issues.csv
outputs/external_validation/kitti_0000/preblind_dataset_protocol.md
outputs/external_validation/kitti_0000/raw_review_groups.csv
outputs/external_validation/kitti_0000/recheck/evaluation.json
outputs/external_validation/kitti_0000/recheck/kitti_semantics/adjusted_clear_matches.csv
outputs/external_validation/kitti_0000/recheck/kitti_semantics/evaluation.json
outputs/external_validation/kitti_0000/recheck/kitti_semantics/gt_preprocessing_audit.csv
outputs/external_validation/kitti_0000/recheck/kitti_semantics/prediction_preprocessing_audit.csv
outputs/external_validation/kitti_0000/review/review_flags.csv
outputs/external_validation/kitti_0000/review/review_flags.json
outputs/external_validation/kitti_0000/review_events.csv
outputs/external_validation/kitti_0000/rule_summary.csv
outputs/external_validation/kitti_0000/track_coverage.csv
outputs/external_validation/kitti_0000/tracks.txt
outputs/external_validation/kitti_0000/validation_summary.json
outputs/external_validation/kitti_0001/adjudications.json
outputs/external_validation/kitti_0001/blind_lock.json
outputs/external_validation/kitti_0001/blind_protocol.json
outputs/external_validation/kitti_0001/clear_matches.csv
outputs/external_validation/kitti_0001/evaluation.json
outputs/external_validation/kitti_0001/false_positive_track_candidates.csv
outputs/external_validation/kitti_0001/final_integrity.json
outputs/external_validation/kitti_0001/flag_labels.csv
outputs/external_validation/kitti_0001/identity_P54_by_frame.csv
outputs/external_validation/kitti_0001/issue_events.csv
outputs/external_validation/kitti_0001/kitti_semantics/adjusted_clear_matches.csv
outputs/external_validation/kitti_0001/kitti_semantics/evaluation.json
outputs/external_validation/kitti_0001/kitti_semantics/gt_preprocessing_audit.csv
outputs/external_validation/kitti_0001/kitti_semantics/prediction_preprocessing_audit.csv
outputs/external_validation/kitti_0001/missed_issues.csv
outputs/external_validation/kitti_0001/preblind_dataset_protocol.md
outputs/external_validation/kitti_0001/prediction_audit.csv
outputs/external_validation/kitti_0001/reference_issues.csv
outputs/external_validation/kitti_0001/review/review_flags.csv
outputs/external_validation/kitti_0001/review/review_flags.json
outputs/external_validation/kitti_0001/rule_summary.csv
outputs/external_validation/kitti_0001/tracks.txt
outputs/external_validation/kitti_0001/validation_summary.json
outputs/human_review/adjudication_template.csv
outputs/human_review/assisted_template.csv
outputs/human_review/baseline_template.csv
outputs/robustness/live_readonly.json
outputs/robustness/tests.log
tests/pilot_browser_qa.js
tests/test_cvat_integration.py
tests/test_cvat_robustness.py
tests/test_evaluate_kitti_semantics.py
tests/test_external_acquisition.py
tests/test_external_adjudication.py
tests/test_human_review.py
tests/test_kitti_tracking_to_mot.py
tests/test_review_tracks_v2.py
tools/audit_kitti_evaluation.py
tools/build_review_package.py
tools/cvat_integration.py
tools/evaluate_kitti_semantics.py
tools/fetch_kitti_sequence.py
tools/human_review/adjudication.html
tools/human_review/adjudication.js
tools/human_review/metrics.js
tools/human_review/review.html
tools/human_review/review.js
tools/human_review/style.css
tools/kitti_tracking_to_mot.py
tools/regress_analyzer_v2.py
tools/review_tracks_v2.py
tools/run_external_blind.py
tools/validate_external_sequence.py
tools/validate_kitti_sample.py
```
