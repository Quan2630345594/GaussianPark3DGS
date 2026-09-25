#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
python -m parking_gs.server --port 8080
