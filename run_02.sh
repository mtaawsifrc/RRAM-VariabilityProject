#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

python3 "$ROOT/02_select_device_representative_curve.py" \
  --step01-dir "$ROOT/step01_S1" \
  --output-dir "$ROOT/step02_S1" \
  --representative-mode medoid-cycle \
  --min-overlap-cycles 5
