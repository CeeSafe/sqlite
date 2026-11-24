"""Runs a program with its standard streams in files, for the tests on Windows, where CeeSafe's Process.capture and
Process.run cannot run the sqlite3 shell at ceesafec 0.95.5 (CEESAFE_FINDINGS.md 45 and 46;
tests/shell_runner_tests.cee).

usage: capture.py [--sqliterc=TEXT] <input> <output> <errors> <program> [<argument>...]

With --sqliterc, the program runs with HOME set to a new directory whose .sqliterc holds TEXT, which the sqlite3
shell reads before its arguments. The exit status is the program's, or 127 when it cannot be started (the reason
is then in <errors>).
"""

import os
import subprocess
import sys
import tempfile


def main():
    arguments = sys.argv[1:]
    sqliterc = None
    if arguments and arguments[0].startswith("--sqliterc="):
        sqliterc = arguments[0][len("--sqliterc="):]
        arguments = arguments[1:]
    if len(arguments) < 4:
        sys.stderr.write(__doc__)
        return 2
    input_path, output_path, errors_path = arguments[:3]
    command = arguments[3:]
    with tempfile.TemporaryDirectory() as home:
        env = None
        if sqliterc is not None:
            with open(os.path.join(home, ".sqliterc"), "w", newline="\n") as rc:
                rc.write(sqliterc + "\n")
            env = dict(os.environ, HOME=home, USERPROFILE=home)
        with open(input_path, "rb") as given, open(output_path, "wb") as output, open(errors_path, "wb") as errors:
            try:
                return subprocess.run(command, stdin=given, stdout=output, stderr=errors, env=env).returncode
            except OSError as error:
                errors.write(str(error).encode("utf-8"))
                return 127


sys.exit(main())
