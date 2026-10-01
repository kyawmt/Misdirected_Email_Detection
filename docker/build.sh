#!/usr/bin/env bash
# Check the published bundle, then build both local images.
#
#   docker/build.sh
#
# Needs a Python environment with the project installed (for `med_deploy`) and a
# running Docker daemon. Builds never fit, retrain, or evaluate anything: they
# copy the published, checksummed bundle. Each image build runs the same bundle
# check on what it copied and fails if a file is missing, extra, or altered.
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python}"

"$PYTHON" -m med_deploy check-bundle --scope api
"$PYTHON" -m med_deploy check-bundle --scope ui

docker build -f docker/Dockerfile.api -t med-api:phase9 .
docker build -f docker/Dockerfile.ui -t med-ui:phase9 .

docker image inspect --format '{{index .RepoTags 0}}  {{.Id}}' med-api:phase9 med-ui:phase9
echo "Identities are content-addressed image ids. To record them (the published record is write-once): python -m med_deploy images --record <scratch>/images.json"
