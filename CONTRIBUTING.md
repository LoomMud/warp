<!--
SPDX-FileCopyrightText: 2026 Oberfield
SPDX-License-Identifier: LicenseRef-Oberfield-Proprietary
-->

# Contributing to Warp

- Every commit must be DCO signed (`git commit -s`).
- Add SPDX headers to all new source files.
- Never commit plaintext secrets or unlicensed third-party assets.
- Commits made by Paperclip agents must end with:
  `Co-Authored-By: Paperclip <noreply@paperclip.ing>`.

## GitHub flow

- Open PRs against `main` at `https://github.com/LoomMud/warp`.
- Keep the interim shared bare repo read-only as a migration mirror.
- For CLI operations, use short-lived env auth and never persist credentials:
  `GH_TOKEN="$GITHUB_TOKEN" gh <command>`
