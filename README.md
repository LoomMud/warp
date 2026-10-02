# Warp

[![License: AGPL-3.0-only](https://img.shields.io/badge/license-AGPL--3.0--only-blue.svg)](LICENSE)

Warp is Oberfield's base mudlib, written from scratch in **Weft** for the **Loom** driver (spec v2, Paperclip OBI-4).
It owns all game policy: master object, login, rooms, items, commands, combat.

Layout (spec §3.2): `/secure` (master, login, daemons), `/std` (base classes), `/cmds`, `/domains/<area>`,
`/builders/<uid>` (staff workrooms). Conventions for writing `/std` and domain code, including the
upgrade rules (D-P1.4), are in [`docs/std-conventions.md`](docs/std-conventions.md).

## Playing the alpha

```sh
loom-cli serve --mudlib .            # telnet to $LOOM_TELNET_ADDR (default 127.0.0.1:4000)
LOOM_CLI=loom-cli tests/smoke.py     # scripted end-to-end check (seeds tiers itself; ignores DATABASE_URL)
```

Characters are saved (OBI-172) under the driver's save root (`LOOM_SAVE_DIR`); see "Character saves" in
[`docs/std-conventions.md`](docs/std-conventions.md). The `persist` smoke scenario restarts the driver and needs
accounts that survive it, so it runs only with `LOOM_SMOKE_DATABASE_URL` set.

Pick a name and password (an R2 account), choose a class (warrior or rogue), and type `help`. The Goblin Wood lies east of the hall.
Staff (tiers 1-5 in the roles tables, see `/secure/roles`) also get `update`, `ed`, `clone`, `dest`, `goto`, `reset`
and the role commands. What each tier may touch is `/secure/master`'s policy ([`docs/std-conventions.md`](docs/std-conventions.md)).
Without Postgres, `LOOM_ROLES_SEED=tests/roles-seed.json` gives the dev staff list. It is keyed on account names
anyone can register, so use it only on a private dev server, never on a shared one.

- `fixtures/item10k/`: the E1.2 10k-clone `/std/item` upgrade fixture (V4).
- `loadbot/`: the command mix and login contract for the R4 load bot.

Rules: DCO sign-off on every commit (`git commit -s`), SPDX header in every `.wf` file
(`SPDX-License-Identifier` tag, value `AGPL-3.0-only`), no secrets or unlicensed assets.

## Remotes

- Canonical remote: `https://github.com/LoomMud/warp` (public).
- Interim mirror (read-only until Phase 1 completes):
  `/paperclip/instances/default/shared/oberfield/warp.git`.

## Licence

Copyright 2026 Oberfield. Licensed under the [GNU Affero General Public License v3.0 only](LICENSE)
(`AGPL-3.0-only`). See [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution policy.
