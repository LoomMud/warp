# Warp

[![License: AGPL-3.0-only](https://img.shields.io/badge/license-AGPL--3.0--only-blue.svg)](LICENSE)

Warp is Oberfield's base mudlib, written from scratch in **Weft** for the **Loom** driver (spec v2, Paperclip OBI-4).
It owns all game policy: master object, login, rooms, items, commands, combat.

Layout (spec §3.2): `/secure` (master, roles, login), `/std` (base classes), `/cmds`, `/domains/<area>`,
`/builders/<uid>` (staff workrooms).

Rules: DCO sign-off on every commit (`git commit -s`), SPDX header in every `.wf` file
(`// SPDX-License-Identifier: AGPL-3.0-only`), no secrets or unlicensed assets.

## Remotes

- Canonical remote: `https://github.com/LoomMud/warp` (public).
- Interim mirror (read-only until Phase 1 completes):
  `/paperclip/instances/default/shared/oberfield/warp.git`.

## Licence

Copyright 2026 Oberfield. Licensed under the [GNU Affero General Public License v3.0 only](LICENSE)
(`AGPL-3.0-only`). See [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution policy.
