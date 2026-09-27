<!--
SPDX-FileCopyrightText: 2026 Oberfield
SPDX-License-Identifier: AGPL-3.0-only
-->

# Load-bot contract (R4, OBI-40)

This is what the Rust load bot in `loom` needs to know to drive Warp. If you
change any of it, change it here in the same PR.

## Login (new character per bot)

| Wait for (regex) | Send |
|---|---|
| `By what name` | the bot's name: 3–16 letters `a`–`z` (no digits). Suggested: `bot` + base-26 of the index, e.g. `botaaa`, `botaab`, … |
| `Create a new character` | `yes` |
| `Choose a class` | `warrior` (or `rogue`) |
| `<\d+/\d+hp> ` | *(logged in)* |

A bot that reconnects with a name already in use gets `already playing`
while the old connection is up. Once that connection has dropped, it gets
`You take over your body again` and then a prompt, so the bot can reconnect
after a disconnect without creating a new character. Characters are not
saved across driver restarts.

**Part 2 (after the account efuns, OBI-85):** a password step is added
after the name (`Password:`; a new account also gets a confirmation). This
file will say exactly what to send. Bots should key their login logic on the
prompts above, not on a fixed number of lines.

## The prompt is the end-of-output marker

After every command the player sends a prompt with **no trailing newline**:
`<HP/MAXHPhp> ` (regex `<\d+/\d+hp> $`). Measure command → output latency
as "line sent" → "prompt received". Asynchronous output (other players'
`say`, combat rounds) can arrive at any time. It ends with a newline, and
combat rounds also re-send the prompt.

## Command mix

`loadbot/mix.tsv`: `weight<TAB>step;step;...`, with placeholders `{peer}`
(another bot's name) and `{n}` (random 1–999). Every entry starts and ends in
the Entrance Hall, so an unattended bot never wanders into combat. Multi-step
entries: send one step, wait for the prompt, then send the next.

The mix covers output fan-out (`say`, `emote`, `tell` to a peer, and `look`
with many players in one room, which lists them all), movement and room
messages, object moves (`get`/`drop`/`wield`), and cheap reads (`who`,
`score`, `inventory`, `help`). With 150 bots in one hall, `say` fans out to
150 connections. That is the realistic worst case for an alpha start room,
and it is intentional.

## Slow-reader cohort

Nothing mudlib-specific: slow readers use the same mix. The start room's
fan-out produces plenty of unsolicited output to back up on.

## Smoke check

`tests/smoke.py` in this repo does a scripted login + command session
against a real `loom serve`. The `basics` scenario covers every command in
the mix.
