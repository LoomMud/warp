# Warp

Warp is Oberfield's base mudlib, written from scratch in **Weft** for the **Loom** driver (spec v2, Paperclip OBI-4).
It owns all game policy: master object, login, rooms, items, commands, combat.

Layout (spec §3.2): `/secure` (master, roles, login), `/std` (base classes), `/cmds`, `/domains/<area>`,
`/builders/<uid>` (staff workrooms).

Rules: DCO sign-off on every commit (`git commit -s`), SPDX header in every `.wf` file
(`// SPDX-License-Identifier: LicenseRef-Oberfield-Proprietary`), no secrets or unlicensed assets.
Interim origin until the GitHub org exists: `/paperclip/instances/default/shared/oberfield/warp.git`.
