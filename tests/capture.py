"""Runs a program with its standard streams in files, for the tests on Windows, where CeeSafe's Process.capture and
Process.run cannot run the sqlite3 shell at ceesafec 0.95.5 (CEESAFE_FINDINGS.md 45 and 46;
tests/shell_runner_tests.cee).

usage: capture.py <input> <output> <errors> <program> [<argument>...]

The exit status is the program's, or 127 when it cannot be started (the reason is then in <errors>).
"""

import subprocess
import sys


def main():
    if len(sys.argv) < 5:
        sys.stderr.write(__doc__)
        return 2
    input_path, output_path, errors_path = sys.argv[1:4]
    command = sys.argv[4:]
    with open(input_path, "rb") as given, open(output_path, "wb") as output, open(errors_path, "wb") as errors:
        try:
            return subprocess.run(command, stdin=given, stdout=output, stderr=errors).returncode
        except OSError as error:
            errors.write(str(error).encode("utf-8"))
            return 127


sys.exit(main())
