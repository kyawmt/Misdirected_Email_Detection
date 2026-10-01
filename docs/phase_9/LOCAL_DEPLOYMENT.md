# Phase 9 — Local deployment

Run the scoring API and the review screen on one machine, as two containers or as plain processes. Everything is a local simulation on fictional data: both ports are published on `127.0.0.1` only, and nothing here is meant for a public host, real mail, or enterprise authentication. Decisions are simulated, scores are risk scores, blocking is disabled, and a failure is `unable_to_assess`, never an allow.

## Containers

Needs Docker with Compose v2 and a running daemon, and a Python environment with the project installed (for `med_deploy`; see [REPRODUCIBILITY.md](REPRODUCIBILITY.md)).

```bash
mkdir -p var/demo                   # the feedback folder (gitignored)
docker/build.sh                     # check the bundle, then build med-api:phase9 and med-ui:phase9
docker compose up -d --wait         # starts the API, then the screen once the API's /ready succeeds
open http://127.0.0.1:8501          # the review screen (API: http://127.0.0.1:8000)
python -m med_deploy smoke --api http://127.0.0.1:8000 --ui http://127.0.0.1:8501 --feedback-file var/demo/feedback.jsonl --target container
python -m med_deploy regress --api http://127.0.0.1:8000      # the scenario fixtures against the running API
docker compose down                 # stop and remove the containers; var/demo is kept
```

- **Readiness.** `GET /health` says the process is up. `GET /ready` says the bundle loaded and returns the versions and `T_warn`. Do not route requests on `/health` alone. The API image's Docker health check calls `/ready`, and the screen container starts only after the API reports healthy. The API takes several seconds to start: it verifies every published file before it accepts a request.
- **Bundle checks at build time.** Each image build runs `python -m med_deploy check-bundle --image` on what it copied and fails on a missing, extra, or altered file, including `policy.json` and the stored validation files, which are compared with anchored digests, and on a frozen-outcome file. Image builds never fit, retrain, evaluate, or download data.
- **A bad or missing bundle fails closed.** `/ready` returns 503 with a reason and `/assess` returns `unable_to_assess` with no decision and no score. See [the error behavior](../phase_6/ERROR_BEHAVIOR.md) and [ROLLBACK_REHEARSAL.md](ROLLBACK_REHEARSAL.md).

## Images

| Image | Dockerfile | Id (content-addressed) | Size | Runs as | pyarrow importable | Write to a bundle file from inside |
| --- | --- | --- | --- | --- | --- | --- |
| API | `docker/Dockerfile.api` | `sha256:85d67e46cbf709ac8fedb7d3fa0219929bba940f3f109a4c582714650707d8ee` | 574 MiB | 10001 | no | PermissionError: Permission denied; as root on a read-only filesystem: OSError: Read-only file system |
| Review screen | `docker/Dockerfile.ui` | `sha256:d1983f4f61227a49b9a566b9d5ad4978f6143c318bbf22cbe5560605db9781a1` | 786 MiB | 10001 | yes | PermissionError: Permission denied; as root on a read-only filesystem: OSError: Read-only file system |

Both are built from `python:3.11.14-slim-bookworm@sha256:65a93d69fa75478d554f4ad27c85c1e69fa184956261b4301ebaf6dbb0a3543d`, pinned by tag and by digest of the multi-architecture index. Containers run with a read-only root filesystem, all capabilities dropped, and `no-new-privileges`; limits are in `compose.yaml` (API 2 CPUs and 2 GiB, screen 1 CPU and 1 GiB).

- **Separate images.** The API image has the core install and the model; the screen image has the `ui` extra and **no model, no feature artifact, and no frozen-outcome file**, so it cannot score even by mistake. Every decision the screen shows is the API's, over HTTP.

## What each process reads

Measured, not guessed: each process ran under a Python audit hook that logs every file it opens, was driven with real requests, and the files it opened under `data/` and `artifacts/` are listed. The per-image ignore lists (`docker/Dockerfile.*.dockerignore`) are default-deny lists of exactly these files, and the build fails if an image holds anything else. The commands that regenerate documents from stored results (`python -m med_ui walkthrough`, `python -m med_policy report`, `python -m med_api report`) read the recorded Phase 5 test result, `test_evaluation.json`; no served process does, and no image contains it.

**API: 21 files read** (matches the bundle check: True; files in the image's `/app`: 21; written anywhere under the repository root: nothing).

| File | Bytes |
| --- | --- |
| `artifacts/med-features-v2/artifact_manifest.json` | 1,087 |
| `artifacts/med-features-v2/feature_schema.json` | 4,978 |
| `artifacts/med-features-v2/features_train.csv` | 895,724 |
| `artifacts/med-features-v2/features_validation_diagnostic.csv` | 137,091 |
| `artifacts/med-features-v2/features_validation_product_like.csv` | 1,124,844 |
| `artifacts/med-features-v2/fit_metadata.json` | 4,272 |
| `artifacts/med-features-v2/quality_report.json` | 68,694 |
| `artifacts/med-features-v2/text_transformer.joblib` | 36,678 |
| `artifacts/med-model-v2/model.joblib` | 5,244 |
| `artifacts/med-policy-v2/policy.json` | 3,597 |
| `data/med-synth-v4/contacts.csv` | 39,993 |
| `data/med-synth-v4/dataset_manifest.json` | 4,107 |
| `data/med-synth-v4/draft_recipients.csv` | 392,653 |
| `data/med-synth-v4/drafts.csv` | 6,257,081 |
| `data/med-synth-v4/invalid_fixtures.csv` | 611 |
| `data/med-synth-v4/labels.csv` | 2,313,478 |
| `data/med-synth-v4/message_recipients.csv` | 3,724,475 |
| `data/med-synth-v4/messages.csv` | 52,325,110 |
| `data/med-synth-v4/quality_report.json` | 5,271 |
| `data/med-synth-v4/reviewer_feedback.csv` | 588 |
| `data/med-synth-v4/split_manifest.csv` | 1,658,218 |

**Review screen: 8 files read** (matches the bundle check: True; files in the image's `/app`: 8; written anywhere under the repository root: nothing).

| File | Bytes |
| --- | --- |
| `artifacts/med-policy-v2/policy.json` | 3,597 |
| `artifacts/med-policy-v2/validation_evaluation.json` | 1,582,570 |
| `artifacts/med-policy-v2/validation_scores.csv` | 217,744 |
| `data/med-synth-v4/contacts.csv` | 39,993 |
| `data/med-synth-v4/draft_recipients.csv` | 392,653 |
| `data/med-synth-v4/drafts.csv` | 6,257,081 |
| `data/med-synth-v4/labels.csv` | 2,313,478 |
| `data/med-synth-v4/split_manifest.csv` | 1,658,218 |

Workload while measuring: API: startup, then the smoke check's assessments (allow, warn, edits, invalid_input, unavailable) and one feedback click. Screen: page load, every curated example's catalog build, readiness, assessments, edits, and one feedback click.

Excluded from the images: `.git`, `.venv`, local private notes, `var/` and any local feedback, secrets, tests and docs, the superseded `med-synth-v2` data and the `*-v1` artifacts, `validation_scores.csv` and the evaluation files (for the API), and every file that stores frozen test outcomes.

## Feedback: volume, retention, cleanup

- The API writes reviewed-label clicks to `/feedback/feedback.jsonl` inside the container: one JSON line per click (request id, contact id, label, versions, time), never an address, subject, or body. It is the **only writable path**. Compose mounts the host folder `var/demo` (gitignored) there; set `MED_FEEDBACK_DIR` to use another folder.
- **Nothing reads the file back into scoring.** A click is not a label until a reviewer accepts it, and it never changes the model, the policy, or the cutoff ([API contract](../phase_6/API_CONTRACT.md)).
- **Retention rule for the demo:** keep the file only while a review session needs it. Delete the folder (`rm -rf var/demo`) when the session ends, and in any case within 30 days. It is fictional data, and a new container starts with whatever the folder holds. The frozen bundle is baked into the image and owned by root; removing or replacing it means a new image.
- On Linux the container user (uid 10001) must be able to write the folder: `chmod a+w var/demo` or `chown 10001 var/demo`. Docker Desktop on macOS needs nothing.

## Without containers

```bash
pip install -c constraints.txt -e ".[dev,ui,monitor]"     # see REPRODUCIBILITY.md
python -m med_api serve                                    # API on http://127.0.0.1:8000
python -m med_ui                                           # screen on http://127.0.0.1:8501, loopback only by default
python -m med_deploy smoke --spawn                         # or: start the API yourself and use --api URL
```

`python -m med_ui` previously listened on every network interface by default; it now listens on `127.0.0.1` and takes `--host` to change that. Every bundle path can be overridden with `MED_API_POLICY`, `MED_API_MODEL`, `MED_API_FEATURES`, `MED_API_DATA`, and `MED_API_FEEDBACK` (the screen reads `MED_UI_API_URL`, `MED_UI_ROOT`, `MED_UI_DATA`, and `MED_UI_POLICY_DIR`). To keep the scoring process fast, run the API in an environment without the `ui` extra (pyarrow makes pandas 3 slower, with identical results).

## Troubleshooting

| Symptom | Likely cause | What to do |
| --- | --- | --- |
| `docker compose up --wait` never finishes | The API is not ready: it found a missing or altered bundle file | `docker compose logs api` and `curl http://127.0.0.1:8000/ready`; the reason names the file. Rebuild the image from the published files; do not edit a file in place. |
| `/ready` is 503 and `/assess` returns `unable_to_assess` | The service is up with no loaded bundle (by design it fails closed) | Fix the cause named in `reason`, or restore the known-good image ([ROLLBACK_REHEARSAL.md](ROLLBACK_REHEARSAL.md)). |
| The screen shows "Scoring service is not ready" and Assess is disabled | The API is unreachable, not ready, or serves a different bundle than the screen's policy file | Check `/ready` against `artifacts/med-policy-v2/policy.json` (versions and `T_warn`). |
| A typed address gives `unavailable` | A well-formed address that is not in the snapshot directory (for example a typo) | This is the contract, not an outage: pick a contact from the directory. |
| Feedback click fails or writes nothing | The feedback folder is not writable by uid 10001 (Linux), or the request id is not from this API process | `chmod a+w var/demo`; assess again, then click. |
| Port 8000 or 8501 is in use | Another process holds the port | Set `MED_API_PORT` or `MED_UI_PORT` before `docker compose up`. |
| The API is slow to start | It verifies every published file (checksums and record counts) and builds the history index | Wait for `/ready`; the measured start time is in the latency record. |
| Slow scoring in a plain process | pyarrow is importable (the `ui` extra is installed in the API's environment) | Use a separate environment for the API, or the API image. |

## Limits

- Local only. No registry push, hosted deployment, authentication, TLS, or public exposure was built or tested.
- Images are built and tested for the architecture of the machine that built them; a second architecture check, if any, is in [TEST_REPORT.md](TEST_REPORT.md).
- Monitoring ([the runbook](../phase_8/RUNBOOK.md)) is a simulation; the containers do not ship telemetry. The API's structured-log allow-list is unchanged.
