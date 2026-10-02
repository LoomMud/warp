#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Oberfield
# SPDX-License-Identifier: AGPL-3.0-only
#
# End-to-end smoke test of the Warp alpha on a real `loom serve`.
#
#   LOOM_CLI=/path/to/loom-cli tests/smoke.py [scenario ...]
#
# Boots the driver on a free port with this checkout as the mudlib, then runs
# scripted telnet sessions and checks their output. Combat and resets need
# the world tick (NetEvent::Tick, OBI-82).
# Exit status 0 = every scenario that ran passed.

import os
import re
import shutil
import socket
import tempfile
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOOM = os.environ.get("LOOM_CLI", "loom-cli")
# Combat and resets need the world tick (NetEvent::Tick, OBI-82), which loom
# main has; LOOM_HAS_TICK=0 skips those scenarios on an older driver.
HAS_TICK = os.environ.get("LOOM_HAS_TICK", "1") == "1"


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Server:
    def __init__(self, root=ROOT, save_dir=None):
        self.root = root
        self.port = free_port()
        env = dict(os.environ, LOOM_TELNET_ADDR=f"127.0.0.1:{self.port}")
        # Character saves (OBI-172) go to a scratch dir, never next to the
        # checkout (the driver's default is <mudlib>/../saves).
        self.own_save_dir = save_dir is None
        self.save_dir = save_dir or tempfile.mkdtemp(prefix="warp-saves-")
        env["LOOM_SAVE_DIR"] = self.save_dir
        # Staff tiers without Postgres (OBI-36): the driver loads this
        # snapshot at boot; see tests/roles-seed.json.
        env.setdefault("LOOM_ROLES_SEED", os.path.join(ROOT, "tests", "roles-seed.json"))
        # Never inherit DATABASE_URL: in agent and CI shells it can point at
        # an unrelated database. Opt in with LOOM_SMOKE_DATABASE_URL (a
        # migrated loom database); without it the driver's in-memory dev
        # backend serves accounts and the seed above serves roles.
        env.pop("DATABASE_URL", None)
        if os.environ.get("LOOM_SMOKE_DATABASE_URL"):
            env["DATABASE_URL"] = os.environ["LOOM_SMOKE_DATABASE_URL"]
        env.setdefault("RUST_LOG", "warn")
        self.proc = subprocess.Popen(
            [LOOM, "serve", "--mudlib", root],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        deadline = time.time() + 20
        while time.time() < deadline:
            if self.proc.poll() is not None:
                raise SystemExit("loom serve exited:\n" + self.proc.stderr.read().decode())
            try:
                socket.create_connection(("127.0.0.1", self.port), timeout=0.2).close()
                return
            except OSError:
                time.sleep(0.1)
        raise SystemExit("loom serve did not start listening")

    def stop(self, keep_saves=False):
        self.proc.terminate()
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        if self.own_save_dir and not keep_saves:
            shutil.rmtree(self.save_dir, ignore_errors=True)


class Client:
    def __init__(self, server, label):
        self.label = label
        self.sock = socket.create_connection(("127.0.0.1", server.port))
        self.sock.settimeout(0.05)
        self.buf = ""
        self.log = []
        # loom-net drops a connection that sends more than 20 lines in a
        # burst or 5 a second sustained (OBI-26). Stay inside that with the
        # same token bucket (a little slower), or fast scenarios flake.
        self.tokens = 18.0
        self.last = time.time()

    def _pump(self):
        try:
            data = self.sock.recv(65536)
        except socket.timeout:
            return
        if not data:
            raise EOFError(f"{self.label}: connection closed")
        # Drop telnet IAC negotiation (R1a) and CRs.
        data = re.sub(rb"\xff[\xfb-\xfe].|\xff\xfa.*?\xff\xf0", b"", data, flags=re.S)
        text = data.decode(errors="replace").replace("\r", "")
        self.buf += text
        self.log.append(text)

    def expect(self, pattern, timeout=3.0):
        rx = re.compile(pattern, re.S)
        deadline = time.time() + timeout
        while True:
            m = rx.search(self.buf)
            if m:
                self.buf = self.buf[m.end():]
                return m
            if time.time() > deadline:
                raise AssertionError(
                    f"{self.label}: timed out waiting for /{pattern}/; got:\n{self.buf}"
                )
            self._pump()

    def send(self, line):
        now = time.time()
        self.tokens = min(18.0, self.tokens + (now - self.last) * 4.5)
        self.last = now
        if self.tokens < 1.0:
            time.sleep((1.0 - self.tokens) / 4.5)
            self.tokens = 1.0
            self.last = time.time()
        self.tokens -= 1.0
        self.sock.sendall((line + "\r\n").encode())

    def cmd(self, line, pattern=r"<\d+/\d+hp> ", timeout=3.0):
        """Send a command and wait for `pattern` (default: the prompt)."""
        self.buf = ""
        self.send(line)
        return self.expect(pattern, timeout)

    def close(self):
        self.sock.close()


PASSWORD = "alpha-pass"


def login(server, name, cls="warrior", password=PASSWORD):
    """Log in as `name`, creating the account and character if needed."""
    c = Client(server, name)
    c.expect(r"By what name")
    c.send(name)
    c.expect(r"Password: ")
    c.send(password)
    m = c.expect(r"Create a new character|You take over|Choose a class|Welcome back", timeout=15)
    if m.group(0).startswith("Create"):
        c.send("yes")
        c.expect(r"Choose a password")
        c.send(password)
        c.expect(r"Confirm password")
        c.send(password)
        c.expect(r"Choose a class", timeout=15)
        c.send(cls)
    elif m.group(0).startswith("Choose"):
        c.send(cls)
    c.expect(r"<\d+/\d+hp> ")
    return c


# ---- scenarios --------------------------------------------------------------


def scenario_basics(server):
    a = login(server, "alice")
    b = login(server, "bobby", "rogue")
    a.cmd("look", r"Entrance Hall.*Bobby is here")
    a.cmd("say hello there", r"You say: hello there")
    b.expect(r"Alice says: hello there")
    a.cmd("'short form", r"You say: short form")
    a.cmd("emote waves.", r"Alice waves\.")
    b.cmd("tell alice psst", r"You tell Alice: psst")
    a.expect(r"Bobby tells you: psst")
    a.cmd("who", r"Alice the warrior.*Bobby the rogue.*2 players online")
    a.cmd("get torch", r"You take a wooden torch")
    b.expect(r"Alice takes a wooden torch")
    a.cmd("i", r"You are carrying:\n  a wooden torch")
    a.cmd("drop torch", r"You drop a wooden torch")
    a.cmd("get all", r"You take a wooden torch")
    a.cmd("north", r"A Walled Garden.*stone bench")
    a.cmd("get bench", r"can't take a stone bench")
    a.cmd("s", r"Entrance Hall")
    a.cmd("xyzzy", r"What\?")
    a.cmd("help", r"Commands: .*look.*kill")
    a.cmd("help kill", r"kill <living>")
    a.cmd("update", r"What\?")  # players have no builder commands
    a.cmd("score", r"Alice the warrior, level 1")
    b.cmd("quit", r"Goodbye")
    a.expect(r"Bobby has lost their link")
    # A wrong password is refused, and gets the create offer (which the
    # account layer then refuses: the name exists).
    x = Client(server, "intruder")
    x.expect(r"By what name")
    x.send("bobby")
    x.expect(r"Password: ")
    x.send("not-the-password")
    x.expect(r"Wrong password, or no such character", timeout=15)
    x.expect(r"Create a new character")
    x.send("yes")
    x.expect(r"Choose a password")
    x.send("another-pass")
    x.expect(r"Confirm password")
    x.send("another-pass")
    x.expect(r"That name was just taken", timeout=15)
    x.close()
    # The right password reconnects to the link-dead body.
    b2 = Client(server, "bobby2")
    b2.expect(r"By what name")
    b2.send("bobby")
    b2.expect(r"Password: ")
    b2.send(PASSWORD)
    b2.expect(r"You take over your body again", timeout=15)
    b2.expect(r"<\d+/\d+hp> ")
    # A connected character can't be taken over, even with its password.
    y = Client(server, "intruder2")
    y.expect(r"By what name")
    y.send("alice")
    y.expect(r"Password: ")
    y.send(PASSWORD)
    y.expect(r"already playing", timeout=15)
    for c in (a, b2, y):
        c.close()


def scenario_builder(server):
    w = login(server, "builder")
    w.cmd("clone /domains/forest/obj/dagger", r"You clone a notched dagger")
    w.cmd("i", r"a notched dagger")
    w.cmd("wield dagger", r"You wield a notched dagger")
    w.cmd("dest dagger", r"You dest a notched dagger")
    w.cmd("i", r"You are carrying nothing|a wooden torch")
    w.cmd("goto /domains/forest/den", r"Goblin Den")
    w.cmd("goto /domains/start/garden", r"Walled Garden")
    w.cmd("update here", r"/domains/start/garden: Updated\.")
    # Protected code (/std) is recompiled by arches and roots only.
    w.cmd("update /std/item.wf", r"/std/item: update failed")
    w.cmd("update /nope/nothing", r"update failed")
    w.cmd("clone /std/npc", r"into the room")
    w.cmd("reset", r"Room reset")
    w.cmd("reset zone", r"/domains/start/zone: reset")
    # Zone resets top spawns back up: dest one of the two rabbits, reset.
    w.cmd("goto /domains/forest/path", r"Forest Path")
    w.cmd("dest rabbit", r"You dest a brown rabbit")
    m = w.cmd("look", r"Forest Path(.*?)<\d+/\d+hp> ")
    assert m.group(1).count("brown rabbit") == 1, m.group(1)
    w.cmd("reset zone", r"/domains/forest/zone: reset")
    m = w.cmd("look", r"Forest Path(.*?)<\d+/\d+hp> ")
    assert m.group(1).count("brown rabbit") == 2, m.group(1)
    w.close()


def scenario_combat(server):
    p = login(server, "fighter")
    p.cmd("e", r"Edge of the Wood")
    p.cmd("get stick", r"You take a heavy stick")
    p.cmd("wield stick", r"You wield a heavy stick")
    p.cmd("e", r"Forest Path.*brown rabbit")
    p.cmd("kill rabbit", r"You attack the brown rabbit")
    p.expect(r"The brown rabbit is dead! You gain \d+ experience", timeout=40)
    p.cmd("look", r"corpse of a brown rabbit")
    p.cmd("score", r"Experience: [1-9]")
    p.close()


def scenario_ed(server):
    """ed-lite: write a room file, update it, goto it."""
    w = login(server, "builder")
    w.cmd("ed /secure/master.wf", r"You may not edit /secure/master\.wf")
    # A builder writes live only in its workroom; domain content goes to
    # wip/ of its domains (live areas are for leads and arches).
    w.cmd("ed /domains/start/hall.wf", r"You may not edit /domains/start/hall\.wf")
    w.buf = ""
    w.send("ed /domains/test/wip/scratch")
    w.expect(r"scratch\.wf: new file.*:", timeout=5)
    lines = [
        "a",
        "// SPDX-FileCopyrightText: 2026 Oberfield",
        "// SPDX-License-Identifier: AGPL-3.0-only",
        "inherit /std/room",
        "pub override fn short() -> string {",
        '    return "A Scratch Room"',
        "}",
        ".",
    ]
    for l in lines:
        w.send(l)
    w.buf = ""
    w.send("p 3")
    w.expect(r"3\tinherit /std/room")
    w.send("c 5     return \"An Edited Room\"")
    w.send("p 5")
    w.expect(r'5\t    return "An Edited Room"')
    w.send("wq")
    w.expect(r"6 lines written.*Left the editor.*<\d+/\d+hp> ", timeout=5)
    w.cmd("update /domains/test/wip/scratch", r"Updated\.")
    w.cmd("goto /domains/test/wip/scratch", r"An Edited Room")
    # Edit again: q refuses with unsaved changes, q! discards.
    w.buf = ""
    w.send("ed /domains/test/wip/scratch.wf")
    w.expect(r"6 lines")
    w.send("d 6")
    w.expect(r"Deleted 1 line")
    w.send("q")
    w.expect(r"Unsaved changes")
    w.send("q!")
    w.expect(r"Left the editor")
    w.close()
    shutil.rmtree(os.path.join(ROOT, "domains", "test", "wip"))


def scenario_upgrade_live(server):
    """Live `update` of /std/room keeps players connected (Phase 0 E0.1 again)."""
    w = login(server, "aragorn")
    p = login(server, "carol")
    w.cmd("update /std/room", r"/std/room: Updated\.")
    w.cmd("update /std/living", r"/std/living: Updated\.")
    p.cmd("look", r"Entrance Hall")
    p.cmd("score", r"Carol the warrior")
    w.close()
    p.close()


def scenario_item10k(server):
    """E1.2 fixture end to end: 10k /std/item clones, a same-schema
    `update /std/item`, then the v1 -> v2 schema change (condition ->
    durability via upgrade()). Every clone must report v2 with its
    condition preserved, and nobody is disconnected."""
    w = login(server, "aragorn")
    p = login(server, "watcher")
    for _ in range(10):
        m = w.cmd("fixture item10k fill 1000", r"item10k: (\d+) items\.", timeout=30)
    assert m.group(1) == "10000", m.group(0)
    ok_v1 = r"10000 items, version sum 10000, condition sum 505000\."
    w.cmd("fixture item10k status", ok_v1, timeout=30)
    t0 = time.time()
    w.cmd("update /std/item", r"/std/item: Updated\.", timeout=60)
    print(f"     update /std/item (same schema), 10k clones: {time.time() - t0:.2f}s")
    w.cmd("fixture item10k status", ok_v1, timeout=30)
    # Swap in v2 on this server's private copy of the mudlib.
    shutil.copy(os.path.join(server.root, "fixtures", "item10k", "item_v2.wf"),
                os.path.join(server.root, "std", "item.wf"))
    t0 = time.time()
    w.cmd("update /std/item", r"/std/item: Updated\.", timeout=60)
    print(f"     update /std/item v1 -> v2, 10k clones: {time.time() - t0:.2f}s")
    w.cmd("fixture item10k status",
          r"10000 items, version sum 20000, condition sum 505000\.", timeout=60)
    p.cmd("look", r"Entrance Hall")
    w.close()
    p.close()


def scenario_tiers(server):
    """Spec §5.11.4 exit test on a private copy: an apprentice (tier 1)
    cannot write outside its workroom, cannot exceed its quotas and cannot
    escalate; its workroom objects are confined; rank rules hold."""
    fix = os.path.join(ROOT, "tests", "fixtures", "tiers")
    room = os.path.join(server.root, "builders", "appr")
    os.makedirs(room, exist_ok=True)
    for f in ("probe.wf", "box.wf"):
        shutil.copy(os.path.join(fix, f), os.path.join(room, f))
    a = login(server, "appr")
    a.cmd("roles", r"Appr: tier 1 \(apprentice\).*max_objects 200")
    a.cmd("who", r"Appr the warrior \(level 1\) \[staff\]")
    a.cmd("ed /domains/start/hall.wf", r"You may not edit /domains/start/hall\.wf")
    a.cmd("ed /std/item.wf", r"You may not edit /std/item\.wf")
    a.cmd("update /std/item", r"/std/item: update failed")
    a.cmd("update /domains/start/garden", r"/domains/start/garden: update failed")
    a.cmd("promote appr 5 because", r"Refused: you may not change your own tier")
    a.cmd("promote builder 3 because", r"Refused: only domain leads and above")
    a.cmd("grant gimli efun destruct 1 because", r"Refused: only arches and roots")
    # Confinement: a workroom object never enters a live room.
    a.cmd("clone /builders/appr/box", r"You clone a practice box")
    a.cmd("goto /domains/start/hall", r"Entrance Hall")
    a.cmd("drop box", r"drop: .*")
    a.cmd("i", r"a practice box")
    a.cmd("update /builders/appr/probe", r"/builders/appr/probe: Updated\.")
    m = a.cmd("goto /builders/appr/probe", r"Report: ([^\n]*)")
    report = m.group(1)
    for want in ("write-live:denied", "write-std:denied", "write-other-workroom:denied",
                 "write-own:ok", "compile-std:denied", "read-secure:denied",
                 "seteuid:denied", "roles-efun:denied", "roles-facade:refused",
                 "destruct-self:ok:true", "destruct-other:denied",
                 "save-other:denied", "restore-other:denied", "save-vfs-path:denied"):
        assert want in report, f"{want!r} not in report: {report}"
    clones = int(re.search(r"clones:(\d+)", report).group(1))
    assert 150 <= clones < 200, f"max_objects 200 not enforced: {report}"
    assert "callouts:8" in report, f"max_callouts_obj 8 not enforced: {report}"
    assert not os.path.exists(os.path.join(server.root, "domains", "start", "pwned.txt"))
    assert not os.path.exists(os.path.join(server.root, "std", "pwned.txt"))
    assert os.path.exists(os.path.join(room, "notes.txt"))
    # At the object quota now: one more clone is refused.
    a.cmd("clone /builders/appr/box", r"object quota exceeded for `appr` \(limit 200\)")
    # Staff below root cannot promote to tier 4/5; a root's request goes to
    # the two-root proposal path (the dev worker has no Postgres, so the
    # driver answers "unavailable"; loom's roles_demo covers the SQL).
    r = login(server, "aragorn")
    r.cmd("roles appr", r"Appr: tier 1")
    r.cmd("promote appr 2 trial over", r"Request to set Appr to tier 2 sent\.")
    r.expect(r"\[roles\] Request \d+ refused: unavailable", timeout=10)
    r.cmd("promote gimli 4 arch", r"Proposal to set Gimli to tier 4 sent")
    r.expect(r"\[roles\] Request \d+ refused: unavailable", timeout=10)
    l = login(server, "legolas")
    l.cmd("promote gimli 4 arch", r"Refused: tier 4 and 5 changes need a root")
    l.cmd("member start gimli lead x", r"Refused: domain leads may not appoint or remove leads")
    for c in (a, r, l):
        c.close()


def scenario_reserved_names(server):
    """OBI-155 (E1.3 finding, D-S3.1): the login prompt refuses to create an
    account named `root`/`mudlib`/other reserved names, so a player can
    never register the uid the driver would treat as a trusted principal.
    An ordinary name is unaffected."""
    c = Client(server, "reserved-name-check")
    c.expect(r"By what name")
    c.send("root")
    c.expect(r"Names are 3 to 16 letters, a to z\.")
    c.expect(r"By what name")
    c.send("mudlib")
    c.expect(r"Names are 3 to 16 letters, a to z\.")
    c.expect(r"By what name")
    c.send("admin")
    c.expect(r"Names are 3 to 16 letters, a to z\.")
    c.expect(r"By what name")
    # An ordinary name still works after the refusals above.
    c.send("notreserved")
    c.expect(r"Password: ")
    c.close()


def scenario_persist(server):
    """M2.1 / OBI-172: a character (stats, inventory, equipment, location)
    survives quit, a dropped link, being connected at shutdown, and a
    driver restart. Accounts must
    survive the restart too, so this needs LOOM_SMOKE_DATABASE_URL (a
    migrated loom database); without it the scenario is skipped."""
    save_dir = server.save_dir
    k = login(server, "keeper", "rogue")
    k.cmd("e", r"Edge of the Wood")
    k.cmd("get stick", r"You take a heavy stick")
    k.cmd("wield stick", r"You wield a heavy stick")
    if HAS_TICK:
        k.cmd("e", r"Forest Path.*brown rabbit")
        k.cmd("kill rabbit", r"You attack the brown rabbit")
        k.expect(r"The brown rabbit is dead! You gain \d+ experience", timeout=40)
        k.expect(r"<\d+/\d+hp> ")
    m = k.cmd("score", r"Keeper the rogue, level (\d+)\.\nHit points: (\d+)/\d+.*?"
                       r"Experience: (\d+).*?Wielding: a heavy stick")
    level, xp = m.group(1), m.group(3)
    m = k.cmd("look", r"((?:An? |The )?(?:Edge of the Wood|Forest Path))\n")
    room = m.group(1)
    k.cmd("quit", r"Goodbye")
    k.close()
    # A dropped link (no quit) saves too.
    d = login(server, "drifter")
    d.cmd("north", r"A Walled Garden")
    d.sock.close()
    deadline = time.time() + 5
    while time.time() < deadline and not all(
            os.path.exists(os.path.join(save_dir, "players", f"{n}.o"))
            for n in ("keeper", "drifter")):
        time.sleep(0.1)
    for n in ("keeper", "drifter"):
        path = os.path.join(save_dir, "players", f"{n}.o")
        assert os.path.exists(path), f"no save file for {n} in {save_dir}"
    # Still connected when the driver stops: the shutdown drain disconnects
    # it, which saves it like any other disconnect.
    st = login(server, "stayer")
    st.cmd("north", r"A Walled Garden")
    st.cmd("get bench", r"can't take")
    # Restart the driver on the same save dir and database.
    server.stop(keep_saves=True)
    st.close()
    assert os.path.exists(os.path.join(save_dir, "players", "stayer.o")), \
        "a player connected at shutdown was not saved"
    again = Server(server.root, save_dir=save_dir)
    try:
        k = Client(again, "keeper-again")
        k.expect(r"By what name")
        k.send("keeper")
        k.expect(r"Password: ")
        k.send(PASSWORD)
        k.expect(r"Welcome back to Oberfield, Keeper the rogue", timeout=15)
        k.expect(rf"{room}\n")
        k.expect(r"<\d+/\d+hp> ")
        k.cmd("score", rf"Keeper the rogue, level {level}\.\nHit points: \d+/\d+.*?"
                       rf"Experience: {xp} .*?Wielding: a heavy stick")
        k.cmd("i", r"a heavy stick \(wielded\)")
        d = Client(again, "drifter-again")
        d.expect(r"By what name")
        d.send("drifter")
        d.expect(r"Password: ")
        d.send(PASSWORD)
        d.expect(r"Welcome back to Oberfield, Drifter the warrior", timeout=15)
        d.expect(r"A Walled Garden")
        s = login(again, "stayer")
        s.cmd("look", r"A Walled Garden")
        for c in (k, d, s):
            c.close()
    finally:
        again.stop(keep_saves=True)


SCENARIOS = {
    "basics": (scenario_basics, False),
    "builder": (scenario_builder, False),
    "upgrade_live": (scenario_upgrade_live, False),
    "ed": (scenario_ed, False),
    "combat": (scenario_combat, True),
    "item10k": (scenario_item10k, False),  # runs on a private copy
    "tiers": (scenario_tiers, False),  # runs on a private copy
    "reserved_names": (scenario_reserved_names, False),
    "persist": (scenario_persist, False),  # restarts its own server
}


# Scenarios that modify mudlib files get their own server on a scratch copy.
PRIVATE = {"item10k", "tiers", "persist"}


def run(n, server):
    fn, needs_tick = SCENARIOS[n]
    if needs_tick and not HAS_TICK:
        print(f"SKIP {n} (needs the world tick, OBI-82)")
        return True
    if n == "persist" and not os.environ.get("LOOM_SMOKE_DATABASE_URL"):
        print(f"SKIP {n} (accounts must survive a restart: set LOOM_SMOKE_DATABASE_URL)")
        return True
    t0 = time.time()
    try:
        fn(server)
        print(f"ok   {n} ({time.time() - t0:.1f}s)")
        return True
    except (AssertionError, EOFError) as e:
        print(f"FAIL {n}: {e}")
        return False


def main():
    names = sys.argv[1:] or list(SCENARIOS)
    failed = 0
    shared = [n for n in names if n not in PRIVATE]
    if shared:
        server = Server()
        try:
            failed += sum(not run(n, server) for n in shared)
        finally:
            server.stop()
    for n in names:
        if n in PRIVATE:
            tmp = tempfile.mkdtemp(prefix="warp-smoke-")
            copy = os.path.join(tmp, "warp")
            shutil.copytree(ROOT, copy, ignore=shutil.ignore_patterns(".git", "__pycache__"))
            server = Server(copy)
            try:
                failed += not run(n, server)
            finally:
                server.stop()
                shutil.rmtree(server.save_dir, ignore_errors=True)
                shutil.rmtree(tmp)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
