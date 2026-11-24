#!/usr/bin/env python3
"""The shell at a terminal, compared with sqlite3: each case makes the same database twice with sqlite3, then runs
sqlite3 on one copy and this shell on the other under a pseudo-terminal (Python's `pty`, POSIX only), typing the
same lines into each, and compares what the terminal shows and the exit status. The file this shell wrote must then
pass sqlite3's integrity check.

sqlite3 is given the classic prompts ("sqlite> ", "   ...> ") through SQLITE_PS1 and SQLITE_PS2, which this shell
shows; its own default (3.54) is a coloured prompt naming the database. What is left out of the comparison: the
version line's version and date (the engine's version, without a date), the lines sqlite3 prints under a statement
it cannot prepare to point at the error (the statement, indented by two spaces, and a caret), and the backspaces a terminal echoes after
`^D`, where sqlite3's line editor echoes none.

usage: python3 tests/terminal.py SHELL WORK_DIRECTORY
"""

import os
import select
import subprocess
import sys
import time

PEOPLE = """
CREATE TABLE people(id INTEGER PRIMARY KEY, name TEXT, score REAL);
INSERT INTO people VALUES (1, 'Ann', 1.5), (22, 'Bob', -2), (333, 'Cy', NULL);
"""

# (name, options, setup, lines typed[, SQL arguments]); each case ends with Ctrl+D unless the shell has stopped.
# With SQL arguments, neither shell reads the terminal.
CASES = [
    ("arguments", ["-list"], PEOPLE, ["select 'not read';"], ["select count(*) from people", "select nope"]),
    ("session", ["-list"], "", [
        "create table t(a);",
        "insert into t values(1),(2);",
        "select * from",
        "t;",
        "select x;",
        ".mode csv",
        "select 1,",
        "2;",
        ".bogus",
        "",
        "   ",
        "-- a comment",
        "#hash",
        "select 3; select",
    ]),
    ("errors-do-not-stop", ["-list"], PEOPLE, [
        ".bail on",
        "select nope;",
        "select 1; select nope; select 2;",
        "select abs(-9223372036854775808);",
        "insert into people(id) values (1);",
        "select count(*) from people;",
    ]),
    ("modes-and-quotes", ["-header", "-column"], PEOPLE, [
        "select * from people order by id;",
        "select 'two",
        "lines' as text;",
        "/* a comment",
        "*/ select 1 as one;",
        "select 2 as two -- to the end",
        ";",
        ".mode line",
        "select name, score from people where id = 22;",
        ".headers off",
        ".mode list",
        "select name from people where id = 1;",
    ]),
    ("quit", ["-csv"], PEOPLE, [
        "select name, score from people where id < 30;",
        ".quit",
        "select 'not read';",
    ]),
    ("exit-status", [], PEOPLE, [
        ".exit 3",
    ]),
    ("transaction", ["-list"], PEOPLE, [
        "begin;",
        "delete from people where id = 1;",
        "rollback;",
        "begin;",
        "update people set score = 9 where id = 22;",
        "commit;",
        "select id, score from people order by id;",
        ".tables",
        ".schema people",
    ]),
]

PROMPTS = (b"sqlite> ", b"   ...> ")


def run_at_terminal(command, lines, env):
    """What the terminal showed while `lines` were typed into `command`, and its exit status."""
    import pty
    master, slave = pty.openpty()
    p = subprocess.Popen(command, stdin=slave, stdout=slave, stderr=slave, env=env, close_fds=True)
    os.close(slave)
    shown = b""

    def read_until_prompt(timeout=20.0):
        # Reads until the shell shows a prompt (it then waits for a line) or ends.
        nonlocal shown
        deadline = time.time() + timeout
        while time.time() < deadline:
            if shown.endswith(PROMPTS) and not select.select([master], [], [], 0.05)[0]:
                return True
            if not select.select([master], [], [], 0.1)[0]:
                if p.poll() is not None:
                    return False
                continue
            try:
                chunk = os.read(master, 4096)
            except OSError:
                return False  # Linux: EIO once the other side is closed
            if not chunk:
                return False
            shown += chunk
        return False

    alive = read_until_prompt()
    for line in lines + [None]:
        if not alive:
            break
        try:
            os.write(master, b"\x04" if line is None else line.encode() + b"\n")
        except OSError:
            break
        alive = read_until_prompt()
    try:
        status = p.wait(timeout=20)
    except subprocess.TimeoutExpired:
        p.kill()
        status = "hung"
    # macOS drops what the terminal holds once the last descriptor of the other side closes: read it first.
    while select.select([master], [], [], 0.2)[0]:
        try:
            chunk = os.read(master, 4096)
        except OSError:
            break
        if not chunk:
            break
        shown += chunk
    os.close(master)
    return shown, status


def normalized(shown):
    text = shown.decode(errors="replace").replace("\x08", "").replace("\r\n", "\n")
    lines = text.split("\n")
    if lines and lines[0].startswith("SQLite version "):
        lines[0] = "SQLite version"
    kept = []
    for line in lines:
        if line.lstrip(" ").startswith("^--- error here"):
            # The statement sqlite3 shows above the caret, a line or more, each indented by two spaces.
            while kept and kept[-1].startswith("  ") and not kept[-1].startswith(PROMPTS[1].decode()):
                kept.pop()
            continue
        kept.append(line)
    return "\n".join(kept)


def make_database(path, sql):
    if os.path.exists(path):
        os.remove(path)
    if sql:
        subprocess.run(["sqlite3", path, sql], check=True)


def main():
    if os.name == "nt":
        print("terminal: skipped (pseudo-terminals are POSIX only)")
        return
    shell, work = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    os.makedirs(work, exist_ok=True)
    env = dict(os.environ, SQLITE_PS1="sqlite> ", SQLITE_PS2="   ...> ", HOME=work)
    problems = []
    for case in CASES:
        name, options, setup, lines = case[:4]
        arguments = case[4] if len(case) > 4 else []
        theirs_db = os.path.join(work, "terminal-" + name + "-theirs.db")
        ours_db = os.path.join(work, "terminal-" + name + "-ours.db")
        make_database(theirs_db, setup)
        make_database(ours_db, setup)
        theirs, their_status = run_at_terminal(["sqlite3"] + options + [theirs_db] + arguments, lines, env)
        ours, our_status = run_at_terminal([shell] + options + [ours_db] + arguments, lines, env)
        a, b = normalized(theirs).replace(theirs_db, "DB"), normalized(ours).replace(ours_db, "DB")
        if a != b or their_status != our_status:
            problems.append(f"{name}:\n  sqlite3 showed (status {their_status}):\n{a}\n"
                            f"  this shell showed (status {our_status}):\n{b}")
            continue
        if os.path.exists(ours_db):
            check = subprocess.run(["sqlite3", ours_db, "PRAGMA integrity_check"], capture_output=True, text=True)
            if check.stdout != "ok\n":
                problems.append(f"{name}: integrity_check says {check.stdout!r}")
    print(f"terminal: {len(CASES)} sessions at a terminal; {len(problems)} differences")
    for problem in problems:
        print("FAIL " + problem)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
