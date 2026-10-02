# Usage guide

How to run the demo, use the review screen, and re-run the checks. Everything is a local simulation on fictional data: nothing is sent, stopped, or hosted, both ports are bound to the loopback interface, and a failure is `unable_to_assess`, never an allow. Read [results](RESULTS.md) and [limitations and future work](LIMITATIONS_AND_FUTURE_WORK.md) to know what the numbers do and do not show.

This page links to the detailed documents and does not repeat them. Commands that write a record or a document use a scratch directory made in the same block with `SCRATCH="$(mktemp -d)"`, because the published records under `artifacts/` are write-once. Every command block on this page runs as printed from the repository root; nothing in it needs to be substituted.

## What you need

- Python 3.11 or newer. Python 3.11.14 is the tested interpreter (`.python-version`).
- Optional: Docker with Compose v2 and a running daemon, for the container route only.

## Install from the pins

`constraints.txt` pins every third-party package the project uses, as tested. It pins nothing of this project itself, and it installs nothing on its own.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -c constraints.txt -e ".[dev,ui,monitor]"
pip check
python -m med_deploy environment --constraints constraints.txt --check
python -m med_deploy check-bundle --scope api
python -m med_deploy check-bundle --scope ui
```

`environment --check` exits non-zero on any difference from the pins. `check-bundle` verifies the versions and checksums of the published bundle without scoring or fitting anything. The details, including why the scoring service is kept apart from the `ui` extra, are in [reproducibility](phase_9/REPRODUCIBILITY.md).

## Start the demo

### As two local processes

Start the scoring API, then, in a second terminal, the review screen:

```bash
python -m med_api serve
python -m med_ui
```

The API listens on `http://127.0.0.1:8000` and the screen on `http://127.0.0.1:8501`, both on loopback only. The API verifies every published file before it accepts a request, so it takes a few seconds to become ready. `GET /health` says the process is up; `GET /ready` says the bundle loaded. Do not treat `/health` alone as ready.

### As two containers

```bash
mkdir -p var/demo
docker/build.sh
docker compose up -d --wait
python -m med_deploy smoke --api http://127.0.0.1:8000 --ui http://127.0.0.1:8501 --feedback-file var/demo/feedback.jsonl --target container
docker compose down
```

`docker/build.sh` checks the bundle and builds the API image and the review-screen image; `compose up --wait` starts the screen only after the API reports ready. `var/demo` is the one writable folder, for feedback clicks, and it is kept when the containers stop. See [local deployment](phase_9/LOCAL_DEPLOYMENT.md) for what each image holds, what each process reads, and the retention rule for feedback.

### A quick end-to-end check without containers

```bash
python -m med_deploy smoke --spawn
```

It starts the API as a process with a disposable feedback file, drives the real review screen against it over HTTP, and compares what the screen shows with what the API returns.

## Use the review screen

The [UI guide](phase_7/UI_GUIDE.md) describes every part of the screen. In short:

- Choose a curated example in the sidebar, or compose a draft from the directory. Each example is a fictional validation draft chosen by a stated rule; "About this example" shows its story, which the model never sees.
- Press **Assess draft**. The panel beside the message says "Pause and review before sending." with each flagged recipient, its field, and the API's reason codes, or "No warning from this policy." The scores, recipient cards, and provenance are under **Assessment details**.
- Edit anything and the earlier result is hidden until you assess the edited draft again; removing a flagged recipient may still warn.
- Mark a recipient intended or unintended to store a feedback line. It is not a label, and it changes nothing.
- The collapsed threshold exploration moves a what-if cutoff over stored validation scores. It is a simulation and never changes the decision above it.
- The lookalike, familiar-contact, and autocompleted-contact examples are allowed on purpose: they are known misses, shown as such.
- Typing an address that is not in the directory snapshot gives `unable_to_assess`, not a warning.

`?example=added_recipient&assess=1` in the screen's address loads an example and assesses it; the keys are listed in the UI guide.

## Run the walkthrough

The generated [walkthrough](phase_7/WALKTHROUGH.md) lists each step with the desired outcome beside the measured one. To regenerate it from a running API without replacing the published copy:

```bash
SCRATCH="$(mktemp -d)"
python -m med_ui walkthrough --api http://127.0.0.1:8000 --output "$SCRATCH/WALKTHROUGH.md"
```

The [demo script](DEMO_WALKTHROUGH.md) follows the same steps as a short spoken demonstration.

## Run monitoring and the drift replay

The stored results are in [monitoring](phase_8/MONITORING.md), the [drift replay](phase_8/DRIFT_REPLAY.md), the [feedback review](phase_8/FEEDBACK_REVIEW.md), the [A/B test proposal](phase_8/EXPERIMENT_PROPOSAL.md), and the [runbook](phase_8/RUNBOOK.md). To regenerate those documents from the stored records, or to run the replay again, write to scratch:

```bash
SCRATCH="$(mktemp -d)"
python -m med_monitor report --docs "$SCRATCH/phase_8"
python -m med_monitor replay --plan-output "$SCRATCH/replay_plan.json" --output "$SCRATCH/replay.json"
python -m med_monitor bundle-checks --output "$SCRATCH/bundle_checks.json"
```

The replay drives the real API in process through the test client and takes a couple of minutes; `--api http://127.0.0.1:8000` uses a running service instead. It reads validation mail and the train-only reference, never a frozen test row, and it never changes a model, a policy, or the cutoff. The monitor is a simulation: there is no production traffic and no real reviewer.

## Run the regression and smoke checks

With the API running (either route above):

```bash
python -m med_deploy regress --api http://127.0.0.1:8000
```

It replays the recorded scenario fixtures and prints each difference in a decision, score, code, limitation, or provenance. The known misses stay in the suite on purpose, so an improvement fails it as surely as a regression.

The fast test selection is what continuous integration runs. The full test run and the dataset validation are the release gate and take several minutes:

```bash
python -m pytest -m "not slow"
python -m pytest
python -m med_data validate --data data/med-synth-v4
python -m med_docs check
```

`med_docs check` fails if a generated document no longer matches the stored records. Check that the regression catches changes, using the recorded one-line mutations applied to a scratch copy of the source:

```bash
SCRATCH="$(mktemp -d)"
python -m med_deploy mutation-check --record "$SCRATCH/mutation_checks.json"
```

The results of all of these are in the [test report](phase_9/TEST_REPORT.md).

## Rehearse a rollback

A rollback here means restoring a known-good image after a failing candidate. The rehearsal swaps two candidates with one injected fault each, checks that each fails closed, and restores and re-verifies the known-good image.

```bash
docker/build.sh
SCRATCH="$(mktemp -d)"
python -m med_deploy rehearse --mode container --record "$SCRATCH/rehearsal_container.json"
python -m med_deploy rehearse --mode process --record "$SCRATCH/rehearsal_process.json"
```

To roll back the running demo by hand, point compose at the known-good image id (read from the images record) and recreate only the API, then check `GET /ready` and run the regression:

```bash
KNOWN_GOOD="$(python -c 'import json; print(json.load(open("artifacts/med-deploy-v1/images.json"))["images"]["api"]["identity"]["id"])')"
MED_API_IMAGE="$KNOWN_GOOD" docker compose up -d --no-build --force-recreate --no-deps api
python -m med_deploy regress --api http://127.0.0.1:8000
```

Do not edit a bundle inside a running container; a new bundle is a new image. There is no live switch between two bundles, no shadow mode, and no canary. See the [rollback rehearsal](phase_9/ROLLBACK_REHEARSAL.md).

## Reproduce a rebuild without touching the published files

Rebuilding the features and the model takes several minutes and must write to scratch, because the feature and model commands overwrite their default output directories:

```bash
SCRATCH="$(mktemp -d)"
python -m med_deploy rebuild-demo --record "$SCRATCH/rebuild_comparison.json"
```

It builds into a scratch directory, compares the result with the published files, and reports what is byte-identical.

## Never run these with their default paths

- `python -m med_features build` and `python -m med_models run` overwrite the published feature and model artifacts, and `med_models run` also rewrites `docs/phase_4`. Use `rebuild-demo` above, or give both commands scratch outputs.
- `python -m med_policy select` and `python -m med_policy evaluate-test` are one-shot. The frozen test subsets of this dataset version were scored once, and a new policy needs a new version and a new frozen dataset version.
- `python -m med_api latency` is the one-shot Phase 6 measurement. Phase 9 measures latency with `med_deploy latency`, which writes a record you name.
- `python -m med_data build` refuses to write into a directory that already holds a dataset. Build into a new directory to compare the manifest.

## Troubleshooting

| Symptom | Likely cause | What to do |
| --- | --- | --- |
| The screen shows "Scoring service is not ready" and **Assess draft** is disabled (the readiness check) | The API is not running, is not ready, or serves a different bundle or cutoff than the screen's local policy file | Open `/ready` on the API. It must report the contract and snapshot the screen speaks and the model, feature, and policy versions and `T_warn` of `artifacts/med-policy-v2/policy.json`. Start or restart the API; use the same bundle for both. |
| `/ready` returns `503` and `/assess` returns `unable_to_assess` (a missing or damaged bundle) | The service is up but its bundle failed to verify: a missing file, a checksum mismatch, a cutoff outside the risk-score range, a `policy.json` that is not the frozen file, or a policy that names another version | `reason` in the `/ready` body names the file. Run `python -m med_deploy check-bundle --scope api` for the failing check. Restore the published file from the repository or rebuild the image; do not edit a file in place. |
| A typed address gives `unavailable` (an unknown address) | The address is well formed but is not in the directory snapshot, for example a typo | This is the contract, not an outage: pick a contact from the directory. A malformed address gives `invalid_input` instead. |
| `docker compose` or `docker/build.sh` reports it cannot connect to the Docker daemon (Docker not running) | The Docker daemon is not started | Start Docker Desktop (on macOS, `open -a Docker`) and wait until `docker info` succeeds. Docker is needed only for the container route; the process route needs none. |
| `docker compose up --wait` never finishes | The API never became healthy, so the screen was not started | `docker compose logs api` and `curl http://127.0.0.1:8000/ready`; the reason names the file. |
| Port `8000` or `8501` is in use | Another process holds it | Set `MED_API_PORT` or `MED_UI_PORT` before `docker compose up`, or pass `--port` to the process commands. |
| A feedback click fails or writes nothing | The feedback folder is not writable by the container user on Linux, or the request id is not from this API process | `chmod a+w var/demo`, assess again, then click. |
| A monitor or deploy command says a record exists | Records are write-once | Give the command a scratch `--output` or `--record` path. |
| Data and feature commands are slow | pyarrow is importable because the `ui` extra is installed in the same environment | Use a separate virtual environment for the API and the data commands. Results are identical. |
| `python -m med_docs check` reports a file out of date | A record or a hand-written marker changed | Run `python -m med_docs report`. Do not edit a generated block or `docs/RESULTS.md` by hand. |

## Documents behind this guide

[Reproducibility](phase_9/REPRODUCIBILITY.md) · [local deployment](phase_9/LOCAL_DEPLOYMENT.md) · [test report](phase_9/TEST_REPORT.md) · [rollback rehearsal](phase_9/ROLLBACK_REHEARSAL.md) · [UI guide](phase_7/UI_GUIDE.md) · [API contract](phase_6/API_CONTRACT.md) · [error behavior](phase_6/ERROR_BEHAVIOR.md) · [runbook](phase_8/RUNBOOK.md) · [documentation index](README.md)
