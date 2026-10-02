<!--
SPDX-FileCopyrightText: 2026 Oberfield
SPDX-License-Identifier: AGPL-3.0-only
-->

# `/std` conventions

These rules keep Warp safe to live-edit. Loom recompiles a program in place
(`update`, `compile_object`), and every live object switches to the new code
while **keeping its variables**. Everything below follows from that.

## D-P1.4: static content in functions, `create()` for mutable state

**`create()` runs once per object, when it is loaded or cloned. It is never
re-run on upgrade.** So anything `create()` stores is frozen into every
existing object. If you edit the literal and run `update`, you see no change
on live objects.

| Kind of data | Where it lives | Example |
|---|---|---|
| Static content: descriptions, names, ids, exits, reset lists, stats that come from the program | An **overridable function** that returns it | `pub override fn short() -> string { return "a notched dagger" }` |
| Per-instance mutable state: hit points, inventory, condition, who you are fighting | A **variable**, initialised by its declaration or in `create()` | `var condition: int = 100` |
| One-off setup that creates *other* objects (NPC loadout, a chest's loot) | `create()` | `/std/npc` `create()` clones `loadout()` |
| Migrating old state to a new shape | **`upgrade(from_version, old)`** | see below |

Don't do this:

```weft
override fn create() {
    set_short("a notched dagger")     // frozen on every existing dagger
    set_exits({"north": "/x/y"})      // editing this and `update` does nothing
}
```

Do this instead:

```weft
pub override fn short() -> string {
    return "a notched dagger"
}
```

`loom check` warns when it sees a `set_*` call with only literal arguments
inside `create()` (`W0900 literal-setter-in-create`). Warp's CI runs
`loom check --deny-warnings`, so the warning fails the build. If you really
mean it, for example `set_heartbeat(true)` in `/secure/combatd`, which is a
registration and not content, put `// loom:allow(literal-setter-in-create)`
on the line before the call.

Per-instance *identity* that is genuinely per instance (a player's name, a
corpse's "of whom") is mutable state, so it is set once through a setter after
cloning, never from literals in `create()`.

Lookup tables that are really code also go in functions: `aliases()` in
`/std/player`, the verb tables in `/secure/cmdd`, `zones()` in
`/secure/master`, the path classes in `/secure/master.classify()`. That way
`update` changes them live.

## Upgrades: `schema_version()` and `upgrade()`

When you change the **variables** of a program (rename, split or retype one),
existing objects need their state migrated:

1. Bump `schema_version()`. Every `/std/item` descendant answers it.
2. Add `upgrade(from_version: int, old: {string: any})`. The driver (V4)
   calls it once per live object, inside an implicit `atomic`, when that
   object is next touched (or by `upgrade_all`). `old` holds the old values
   of removed or changed variables. Assign the new variables from them.
   **Key on the contents of `old`, not on `from_version`:** `from_version` is
   the program's compile count (every `update` bumps it), not your
   `schema_version()`. If `upgrade()` throws, that object is rolled back and
   the failure is reported. Other objects are not affected.
3. Variables whose name and type did not change are carried over
   automatically. New variables get their initialiser. You only migrate what
   changed.

`fixtures/item10k/item_v2.wf` is the worked example (it is also the E1.2 test
input): v1 `/std/item` has `condition: int` (0–100). v2 replaces it with
`durability`/`max_durability`, and `upgrade()` converts one to the other.
`tests/smoke.py item10k` runs that change live on 10,000 clones.

## Other `/std` rules

- **Moving things:** the `move_to()` efun only moves `self`. To move another
  object, call `ob.move(dest)` (in `/std/object`).
- **Taking things out of play:** always call `ob.remove()`, not `destruct()`.
  It moves players inside to the start room, removes everything else
  inside, then destructs. Test a stored reference with `destructed(ob)`
  before you use it (`environment(dead)` is `null`, and calling a
  function on a dead object is an error).
- **Text output:** `ob.message(text)` sends one line (adds `\n`). Rooms have
  `tell(text, exclude)` and `tell_except(text, [objects])`. `send()` is
  verbatim (D-P1.2), so use it directly only for prompts.
- **Randomness:** the `random(n)` efun (`[0, n)`).
- **Time:** the driver ticks every 100 ms. `call_out` delays are in those
  ticks. Heartbeats fire every 20 ticks (2 s). `/secure/combatd` is the
  only object with a heartbeat: each one is a combat pulse, and `now()`
  counts pulses. Hit points regenerate lazily against `now()`, so idle
  livings cost nothing.
- **Late-bound calls return `any`.** Cast at the call site
  (`ob.query_hp() as int`) so the checker can type the rest.
- **Late-bound calls need `pub`.** Every function another object calls must
  be `pub`. Keep functions that act *as* an object private
  (`/std/player` `run_command` is private, so no other object can make a
  player run a command).
- **Weft today:** no `break`, slices, `match`, closures or `struct`/`enum`
  yet. The string efuns are `lower`, `to_int`, `trim`, `split` and `join`,
  and `/std/object` adds `capitalize`, `words` and `join_from`.

## Layout

| Path | What |
|---|---|
| `/secure/master` | boot (clock, zones), `connect()`, `login_complete()`, the security policy (`valid_*`, `program_flags`) |
| `/secure/login` | one clone per connecting user: account login/creation (R2), character creation |
| `/secure/userd` | name → player object (connected or link-dead) |
| `/secure/roles` | staff tiers, domains, grants and quotas (driver roles snapshot) and role changes |
| `/secure/cmdd` | verb → command program tables |
| `/secure/combatd` | combat pulse clock, Diku combat rounds (2 s) |
| `/std/object` → `item` → `container`, `weapon`, `armour`, `corpse` | things |
| `/std/object` → `living` → `player`, `npc` | creatures |
| `/std/object` → `room`, `zone`, `command`, `editor` | places, resets, verbs, `ed` sessions |
| `/cmds/player/*`, `/cmds/builder/*` | one program per verb |
| `/domains/<area>/zone` + rooms, `npc/`, `obj/` | content |
| `/domains/test/warehouse` | the E1.2 10k-clone fixture room |

## Security and staff tiers (spec r5 §5.11, OBI-36)

Tiers live in Postgres (`staff`, `domain_members`, `tier_policy`, `grants`).
The driver holds them as a snapshot. `/secure/roles` is the only way into
it, both for reading and for changing roles; nothing copies tiers into
player variables. Without Postgres, the driver loads `LOOM_ROLES_SEED` (the
smoke test uses `tests/roles-seed.json`).

- **Who you are.** At login, `/secure/master` makes the player body run as
  its account (`seteuid` to the account name). Every privileged efun asks
  the master about every euid on the stack, so a builder object called from
  a player's command gets the player's rights, not its own.
- **Path classes** (`classify()`): `secure`, `protected` (`/std`, `/cmds`,
  `/daemons`, `/include`), `domain_wip(d)` (`/domains/<d>/wip/**`),
  `domain_live(d)` (the rest of `/domains/<d>/`), `workroom(u)`
  (`/builders/<u>/`), `doc`, `data`, `other`.
- **Writes, live:** your own workroom. T2 members also write their domains'
  `wip/`. Leads (T3) write their whole domain and `/doc`. Arches (T4) write
  every domain. `/secure` and protected code are never written live: they
  change through Git review.
- **Compiles** (`update`): T1 only in its own workroom. T2+ also compile
  their domains, T3 also any workroom, T4 also protected code, and T5 also
  `/secure`.
- **Efuns:** T1–T2 get P0–P1, T3 P2, T4 P3 and T5 P4. Any account also gets
  `disconnect`, because the game needs it with a player on the stack
  (`quit`), and `save_object`, because a body saves itself as its account
  (see "Character saves"). `destruct(self())` needs no grant at any tier: it is a driver
  rule (loom OBI-149), not master policy, so `remove()` -> `destruct(self())`
  (kills, corpses, `dest`) always works. `destruct` on a *different* object
  is still P2 (T3+, or a time-boxed grant below that). Grants (`grant`)
  extend a tier for a single efun or path, and they expire.
- **Quotas** (objects, heartbeats, call_outs, ticks, memory, disk) come
  from `tier_policy`. The driver enforces them on each object's owner.
  Player input always gets the world default of 1M ticks.
- **Confinement:** programs under a workroom or `wip/` are `CONFINED`.
  They never enter a live room or a tier 0 player's inventory, and players
  never enter them.
- **Role changes:** `promote`, `demote`, `member`, `grant`, `revoke` and
  `approve`. `/secure/roles` checks rank first. The driver then calls the
  audited SQL functions as the player who typed the command. Tier 4/5
  changes need two roots: one proposes and another approves.

## Character saves (OBI-172)

A character is saved with loom's `save_object` (loom `docs/save-objects.md`)
to `/players/<account>` in the driver's save root (`--save-dir` /
`LOOM_SAVE_DIR`, default `<mudlib>/../saves`), never in the mudlib tree.

- **What is saved:** the `persistent var`s of `/std/object` (`name`),
  `/std/living` (`hp`, `level`, `xp`) and `/std/player` (`class_name`,
  `saved_room`, `saved_items`). Object references do not survive a restart,
  so the room is saved as its program path and each carried item as
  `{path, condition, eq}`; restore clones them again and re-wields/re-wears.
  Items inside carried containers and per-clone state other than
  `condition` are not saved yet.
- **When:** the driver calls `autosave()` every 5 minutes while connected
  and on every disconnect (`quit`, a dropped link, and the shutdown drain
  when the driver stops).
- **Restore:** `/secure/login` restores an account whose character is not
  in memory (`restore_character`) and brings it back to its saved room,
  or the start room if that room no longer loads. No save means a new
  character (class prompt).
- **Who may touch a save:** `/secure/master` `can_save()`. The path must be
  `/players/<account>`; root and mudlib may name any account, an account
  only its own, a domain none. VFS read/write rules and path grants do not
  apply. Adding a `persistent var` is a schema change: old saves restore
  into it by name, and `upgrade()` handles type changes (D-P1.4 rules).
- **Known limit:** staff who can compile code (tier 1+) can write an object
  that inherits `/std/player` and saves it over their *own* save file. It
  cannot reach anyone else's save.

## Not yet (alpha limits)

- **One account, one character, one name.** Passwords are checked by the
  driver against R2 accounts (Argon2, off the world thread).
- **Passwords echo.** The login does not negotiate telnet `WILL ECHO` yet.
- **`ed` edits live files.** On staging they are discarded on the next
  `WARP_REF` bump (D-P1.11).
