#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Oberfield
# SPDX-License-Identifier: AGPL-3.0-only
#
# Local gates before pushing: `loom check` (parse + link every .wf) and DCO.
# LOOM_CLI: path to a loom-cli binary built from loom `main` (default: `loom-cli` on PATH).
set -euo pipefail
cd "$(dirname "$0")/.."
"${LOOM_CLI:-loom-cli}" check --deny-warnings .
# End-to-end session test against a real `loom serve` (needs python3).
LOOM_CLI="${LOOM_CLI:-loom-cli}" tests/smoke.py
scripts/check-dco.sh "${DCO_RANGE:-origin/main..HEAD}"
echo "ci-local: all gates green"
