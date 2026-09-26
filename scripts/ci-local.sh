#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Oberfield
# SPDX-License-Identifier: LicenseRef-Oberfield-Proprietary
#
# Local gates before pushing: `loom check` (parse + link every .wf) and DCO.
# LOOM_CLI: path to a loom-cli binary built from loom `main` (default: `loom-cli` on PATH).
set -euo pipefail
cd "$(dirname "$0")/.."
"${LOOM_CLI:-loom-cli}" check .
scripts/check-dco.sh
echo "ci-local: all gates green"
