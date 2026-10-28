#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export PATH="$PWD/.conda/ai-brain/bin:$PATH"
export LD_LIBRARY_PATH="$PWD/.conda/ai-brain/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
python -m pytest -q "$@"
cd frontend
node node_modules/typescript/bin/tsc --noEmit
