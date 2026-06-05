#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

python3 "$ROOT/01_extract_clean_cycles.py" \
 "$ROOT/raw_data/S1" \
 --output-dir "$ROOT/step01_S1"
