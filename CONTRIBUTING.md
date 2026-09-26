<!--
SPDX-FileCopyrightText: 2026 Oberfield
SPDX-License-Identifier: LicenseRef-Oberfield-Proprietary
-->

# Contributing to Warp

## Status and licence

This repository is **public but not open source (yet)**. The project licence is still being decided, so
every file is `LicenseRef-Oberfield-Proprietary` (all rights reserved). **External contributions are not
accepted** until a licence is chosen; please do not open pull requests from forks. Issues and feedback
are welcome.

## Rules

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
