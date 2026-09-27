<!--
SPDX-FileCopyrightText: 2026 Oberfield
SPDX-License-Identifier: AGPL-3.0-only
-->

# Load-bot contract (R4, OBI-40)

This is what the Rust load bot in `loom` needs to know to drive Warp. If you
change any of it, change it here in the same PR.

## Login

Every bot has an R2 account (the driver's in-memory backend when there is
no `DATABASE_URL`). One account is one character, and they share a name.

| Wait for (regex) | Send |
|---|---|
| `By what name` | the bot's name: 3–16 letters `a`–`z` (no digits). Suggested: `bot` + base-26 of the index, e.g. `botaaa`, `botaab`, … |
| `Password: ` | the bot's password (6–128 characters) |
| then one of the three rows below | |
| `Create a new character` | *(no such account yet)* `yes`, then on `Choose a password` send the password, then on `Confirm password` send it again |
| `Choose a class` | `warrior` (or `rogue`). This appears after creation, and for an existing account whose character isn't in memory (e.g. after a driver restart) |
| `You take over your body again` | *(reconnect to a link-dead character; nothing to send)* |
| `<\d+/\d+hp> ` | *(logged in)* |

Failure prompts: `already playing` (that character is connected; the bot
must wait until its old connection has dropped), `That name was just taken`
(two creations raced), `Too many failed attempts` (disconnects after 3 wrong
passwords), and `The account service is unavailable` (backend queue full or
down; retry later).

Passwords are hashed with Argon2id (19 MiB, t=2) off the world thread, so
each login costs real CPU time, but it does
not stall the tick. Ramp logins up (e.g. 10/s) rather than connecting 500
bots at once, and report login latency separately from command latency.
Characters are not saved across driver restarts.

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

`tests/smoke.py` in this repo runs scripted sessions against a real
`loom serve`. Its `login()` is the reference implementation of the flow
above, and the `basics` scenario covers every command in the mix.
