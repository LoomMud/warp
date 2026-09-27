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
inside `create()` (lint `W0300 literal-setter-in-create`,
OBI-86, S4b). If you really mean it, put
`// loom:allow(literal-setter-in-create)` on the line before the call.

Per-instance *identity* that is genuinely per instance (a player's name, a
corpse's "of whom") is mutable state, so it is set once through a setter after
cloning, never from literals in `create()`.

Lookup tables that are really code also go in functions: `aliases()` in
`/std/player`, the verb tables in `/secure/cmdd`, `zones()` in
`/secure/master`, the staff list in `/secure/staff`. That way `update` changes
them live.

## Upgrades: `schema_version()` and `upgrade()`

When you change the **variables** of a program (rename, split or retype one),
existing objects need their state migrated:

1. Bump `schema_version()`. Every `/std/item` descendant answers it.
2. Add `upgrade(from_version: int, old: {string: any})`. The driver (V4,
   OBI-34) calls it once per live object,
   inside an implicit `atomic`, with the old values of removed or changed
   variables in `old`. Assign the new variables from them. If `upgrade()`
   throws, that object is rolled back and the failure is reported. Other
   objects are not affected.
3. Variables whose name and type did not change are carried over
   automatically. New variables get their initialiser. You only migrate what
   changed.

`fixtures/item10k/item_v2.wf` is the worked example (it is also the E1.2 test
input): v1 `/std/item` has `condition: int` (0–100). v2 replaces it with
`durability`/`max_durability`, and `upgrade()` converts one to the other.

Until V4 lands, `update` keeps Phase 0 semantics: matching variables are kept,
new ones get their initialiser, and `upgrade()` is not called yet.

## Other `/std` rules

- **Moving things:** the `move_to()` efun only moves `self`. To move another
  object, call `ob.move(dest)` (in `/std/object`).
- **Taking things out of play:** always call `ob.remove()`, never anything
  lower-level. Today it parks the object in `/secure/void`. Once the
  `destruct` efun lands (OBI-85, S4a) it
  becomes `destruct(self())`. Everything already goes through this one
  function, so that is a one-line change.
- **Text output:** `ob.message(text)` sends one line (adds `\n`). Rooms have
  `tell(text, exclude)` and `tell_except(text, [objects])`. `send()` is
  verbatim (D-P1.2), so use it directly only for prompts.
- **Randomness:** `load_object("/secure/rng").roll(n)` gives `[0, n)`. It
  becomes the `random()` efun with S4a. Call sites don't change.
- **The clock:** `/secure/combatd` `now()` counts world ticks (100 ms).
  Hit points regenerate lazily against it, so idle livings cost nothing.
  `combatd` is the only object with a heartbeat. Everything else uses
  `call_out`.
- **Late-bound calls return `any`.** Cast at the call site
  (`ob.query_hp() as int`) so the checker can type the rest.
- **Late-bound calls need `pub`.** Every function another object calls must
  be `pub`. Keep functions that act *as* an object private
  (`/std/player` `run_command` is private, so no other object can make a
  player run a command).
- **Weft today:** no `break`, slices, `match`, closures, `struct`/`enum` or
  `const` at runtime yet. `/std/object` has the string helpers
  (`lower_case`, `capitalize`, `words`, `join_from`, `parse_int`).

## Layout

| Path | What |
|---|---|
| `/secure/master` | boot (clock, zones), `connect()`, `login_complete()` |
| `/secure/login` | one clone per connecting user: name, character creation |
| `/secure/userd` | name → player object (connected or link-dead) |
| `/secure/staff` | alpha staff tiers (interim, until S2 `/secure/roles`) |
| `/secure/cmdd` | verb → command program tables |
| `/secure/combatd` | world clock, Diku combat rounds (2 s) |
| `/secure/rng` | randomness |
| `/secure/void` | where removed objects are parked (until `destruct`) |
| `/std/object` → `item` → `container`, `weapon`, `armour`, `corpse` | things |
| `/std/object` → `living` → `player`, `npc` | creatures |
| `/std/object` → `room`, `zone`, `command` | places, resets, verbs |
| `/cmds/player/*`, `/cmds/builder/*` | one program per verb |
| `/domains/<area>/zone` + rooms, `npc/`, `obj/` | content |
| `/domains/test/warehouse` | the E1.2 10k-clone fixture room |

## Not yet (alpha limits)

- **No passwords** until the account efuns land (S4a,
  OBI-85). Logging in by name reconnects a
  link-dead character, and a connected character cannot be taken over.
  Staging does not open to anyone before this is closed.
- **No saving.** Characters exist from creation until driver restart.
- **Tiers are advisory** until S1/S2 (OBI-35,
  OBI-36) enforce them in the driver.
  Builder commands check `query_tier() >= 2` (looked up by name in
  `/secure/staff`, never stored on the player).
- **`ed`-lite** needs `read_file`/`write_file` (S4a) and ships with part 2.
