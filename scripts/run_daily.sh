#!/usr/bin/env bash
# Local equivalent of the GitHub "collect" workflow: collect, forecast, build.
set -euo pipefail
cd "$(dirname "$0")/.."
status=0
python -m collect.pipeline "$@" || status=$?
python -m predict.forecast
python -m site_builder.builder
exit "$status"
