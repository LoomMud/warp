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
# the world tick (NetEvent::Tick, OBI-82); scenarios that need it are
# skipped with a note unless LOOM_HAS_TICK=1.
# Exit status 0 = every scenario that ran passed.

import os
import re
import socket
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOOM = os.environ.get("LOOM_CLI", "loom-cli")
HAS_TICK = os.environ.get("LOOM_HAS_TICK") == "1"


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Server:
    def __init__(self):
        self.port = free_port()
        env = dict(os.environ, LOOM_TELNET_ADDR=f"127.0.0.1:{self.port}")
        env.setdefault("RUST_LOG", "warn")
        self.proc = subprocess.Popen(
            [LOOM, "serve", "--mudlib", ROOT],
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

    def stop(self):
        self.proc.terminate()
        try:
            self.proc.wait(5)
        except subprocess.TimeoutExpired:
            self.proc.kill()


class Client:
    def __init__(self, server, label):
        self.label = label
        self.sock = socket.create_connection(("127.0.0.1", server.port))
        self.sock.settimeout(0.05)
        self.buf = ""
        self.log = []

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
        self.sock.sendall((line + "\r\n").encode())

    def cmd(self, line, pattern=r"<\d+/\d+hp> ", timeout=3.0):
        """Send a command and wait for `pattern` (default: the prompt)."""
        self.buf = ""
        self.send(line)
        return self.expect(pattern, timeout)

    def close(self):
        self.sock.close()


def login(server, name, cls="warrior"):
    c = Client(server, name)
    c.expect(r"By what name")
    c.send(name)
    m = c.expect(r"Create a new character|You take over")
    if m.group(0).startswith("Create"):
        c.send("yes")
        c.expect(r"Choose a class")
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
    # Reconnect by name picks up the link-dead body.
    b2 = Client(server, "bobby2")
    b2.expect(r"By what name")
    b2.send("bobby")
    b2.expect(r"You take over your body again")
    b2.expect(r"<\d+/\d+hp> ")
    # A connected character can't be taken over.
    x = Client(server, "intruder")
    x.expect(r"By what name")
    x.send("alice")
    x.expect(r"already playing")
    for c in (a, b2, x):
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
    w.cmd("update /std/item.wf", r"/std/item: Updated\.")
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


def scenario_upgrade_live(server):
    """Live `update` of /std/room keeps players connected (Phase 0 E0.1 again)."""
    w = login(server, "legolas")
    p = login(server, "carol")
    w.cmd("update /std/room", r"/std/room: Updated\.")
    w.cmd("update /std/living", r"/std/living: Updated\.")
    p.cmd("look", r"Entrance Hall")
    p.cmd("score", r"Carol the warrior")
    w.close()
    p.close()


def scenario_item10k(server):
    """Clone 10k /std/item into the warehouse, then `update /std/item` live
    (Phase 0 semantics until V4). Checks nobody is disconnected."""
    w = login(server, "aragorn")
    p = login(server, "watcher")
    for _ in range(10):
        m = w.cmd("fixture item10k fill 1000", r"item10k: (\d+) items\.", timeout=30)
    assert m.group(1) == "10000", m.group(0)
    w.cmd("fixture item10k status", r"10000 items, version sum 10000\.", timeout=30)
    t0 = time.time()
    w.cmd("update /std/item", r"/std/item: Updated\.", timeout=60)
    print(f"     update /std/item with 10k clones: {time.time() - t0:.2f}s")
    w.cmd("fixture item10k status", r"10000 items, version sum 10000\.", timeout=30)
    p.cmd("look", r"Entrance Hall")
    w.close()
    p.close()


SCENARIOS = {
    "basics": (scenario_basics, False),
    "builder": (scenario_builder, False),
    "upgrade_live": (scenario_upgrade_live, False),
    "combat": (scenario_combat, True),
    "item10k": (scenario_item10k, False),
}


def main():
    names = sys.argv[1:] or list(SCENARIOS)
    server = Server()
    failed = 0
    try:
        for n in names:
            fn, needs_tick = SCENARIOS[n]
            if needs_tick and not HAS_TICK:
                print(f"SKIP {n} (needs the world tick, OBI-82; set LOOM_HAS_TICK=1)")
                continue
            t0 = time.time()
            try:
                fn(server)
                print(f"ok   {n} ({time.time() - t0:.1f}s)")
            except (AssertionError, EOFError) as e:
                failed += 1
                print(f"FAIL {n}: {e}")
    finally:
        server.stop()
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
