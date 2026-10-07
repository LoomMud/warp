<!--
SPDX-FileCopyrightText: 2026 Oberfield
SPDX-License-Identifier: AGPL-3.0-only
-->

# Contributing to Warp

## Status and licence

This repository is public and licensed under the **GNU Affero General Public License v3.0 only**
(`AGPL-3.0-only`). The full text is in [`LICENSE`](LICENSE) (REUSE copy: `LICENSES/AGPL-3.0-only.txt`).
Every file carries an SPDX header naming `AGPL-3.0-only` as its licence identifier.

**External pull requests are not accepted for now.** Please do not open pull requests from forks; they
will be closed unmerged. Issues, bug reports and feedback are welcome. We will revisit this (most likely
accepting contributions under AGPL-3.0-only with DCO sign-off) once the contribution governance is settled.

## Rules

- Every commit must be DCO signed (`git commit -s`).
- Add SPDX headers to all new source files.
- Never commit plaintext secrets or unlicensed third-party assets.
- **No synthetic CPU/load or stress testing on the shared host without board consent**
  (OBI-306/OBI-307). Do not start busy-loop spinners (`while :; do :; done`), parallel builds whose
  only purpose is to add load, or stress loops unless the issue has a board-accepted confirmation
  for that test. Ordinary builds and tests are fine. So are sequential repeat runs with no added load.
  To prove a flake fix, use a deterministic reproduction plus a regression test, or N *sequential*
  runs with no added load. If you really need contention, say so in the plan and get board consent
  before you run it.
- Commits made by Paperclip agents must end with:
  `Co-Authored-By: Paperclip <noreply@paperclip.ing>`.

## GitHub flow

- Open PRs against `main` at `https://github.com/LoomMud/warp`.
- Keep the interim shared bare repo read-only as a migration mirror.
- For CLI operations, use short-lived env auth and never persist credentials:
  `GH_TOKEN="$GITHUB_TOKEN" gh <command>`
