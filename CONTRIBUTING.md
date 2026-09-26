<!--
SPDX-FileCopyrightText: 2026 Oberfield
SPDX-License-Identifier: AGPL-3.0-only
-->

# Contributing to Warp

## Status and licence

This repository is public and licensed under the **GNU Affero General Public License v3.0 only**
(`AGPL-3.0-only`). The full text is in [`LICENSE`](LICENSE) (REUSE copy: `LICENSES/AGPL-3.0-only.txt`).
Every file carries `SPDX-License-Identifier: AGPL-3.0-only`.

**External pull requests are not accepted for now.** Please do not open pull requests from forks; they
will be closed unmerged. Issues, bug reports and feedback are welcome. We will revisit this (most likely
accepting contributions under AGPL-3.0-only with DCO sign-off) once the contribution governance is settled.

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
