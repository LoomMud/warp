<!--
SPDX-FileCopyrightText: 2026 Oberfield
SPDX-License-Identifier: AGPL-3.0-only
-->

# E1.2 fixture: 10,000 live `/std/item` clones

This is the mudlib side of the Phase 1 exit test E1.2 ("recompile `/std/item`
with 10k live clones, all upgraded, zero disconnects"). The loom-side test
(V4, OBI-34) drives it through the `World` API or a builder session.

## Steps

1. Boot a world on a copy of this repo.
2. `load_object("/domains/test/warehouse")` and call `fill(1000)` ten times
   (one call stays well inside the 1M-tick budget; one call per tick
   mirrors realistic load). `item_count()` is then 10000. Clone *k* has v1
   `condition == 100 - (k % 100)`, so every instance is distinguishable.
3. Record `version_sum()` (10000 for v1) and, if you like, a sample of
   `query_condition()`.
4. Copy `fixtures/item10k/item_v2.wf` over `std/item.wf` and recompile
   `/std/item` (`compile_object` / `update /std/item`). The wave also re-links
   `/std/container`, `/std/weapon`, `/std/armour`, `/std/corpse` and every
   domain item.
5. After `upgrade_all` finishes: `version_sum() == 20000`, every sampled
   `query_condition()` equals its v1 value (the `upgrade()` migration
   `durability = condition * 10`), `query_durability() == condition * 10`, and
   the test clients are still connected.

`item_v2.wf` is a valid program in its own right (`loom check` covers it), but
nothing inherits it in place.

## Checked here

`tests/smoke.py` runs `update /std/item` with live objects on every run.
Steps 2–5 at 10k scale belong to OBI-34's exit test.
