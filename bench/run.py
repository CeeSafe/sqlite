#!/usr/bin/env python3
"""The benchmark (README.md, "Benchmark"): bench/src/main.cee on this package's engine against bench/c/bench.c on
SQLite, the same workloads with the same SQL, parameters and checksums.

    python3 bench/run.py [--rows N] [--runs R] [--work DIR]

It downloads SQLite's amalgamation (checked against sqlite.org's SHA3-256) into bench/out, builds it, bench.c and
its shell at -O2, builds the CeeSafe program at -O2, then runs every engine R times, each on a new file in DIR,
taking turns. It stops if any checksum differs between the engines, checks every engine's last file with SQLite's
shell (PRAGMA integrity_check, and the same answer to a query of its rows), and prints the medians."""

import argparse
import hashlib
import os
import platform
import statistics
import subprocess
import sys
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
SQLITE = "3540100"
SQLITE_YEAR = "2026"
SQLITE_NAME = "3.54.1"

ENGINES = ["ceesafe", "sqlite-reprepare", "sqlite-prepared"]


def sh(args, cwd=None):
    subprocess.run(args, cwd=cwd, check=True)


def amalgamation():
    """The amalgamation's directory, downloaded once."""
    name = f"sqlite-amalgamation-{SQLITE}"
    folder = os.path.join(OUT, name)
    if os.path.exists(os.path.join(folder, "sqlite3.c")):
        return folder
    os.makedirs(OUT, exist_ok=True)
    url = f"https://www.sqlite.org/{SQLITE_YEAR}/{name}.zip"
    page = urllib.request.urlopen("https://www.sqlite.org/download.html").read().decode()
    # download.html lists each product as "PRODUCT,VERSION,PATH,SIZE,SHA3-256".
    sums = [line.split(",") for line in page.splitlines() if line.startswith("PRODUCT,")]
    wanted = [s[4] for s in sums if len(s) >= 5 and s[2].endswith(f"{name}.zip")]
    if not wanted:
        sys.exit(f"sqlite.org's download page does not list {name}.zip")
    data = urllib.request.urlopen(url).read()
    if hashlib.sha3_256(data).hexdigest() != wanted[0].strip():
        sys.exit(f"{name}.zip does not have the SHA3-256 sqlite.org gives")
    archive = os.path.join(OUT, f"{name}.zip")
    with open(archive, "wb") as f:
        f.write(data)
    with zipfile.ZipFile(archive) as z:
        z.extractall(OUT)
    return folder


def build(cc):
    folder = amalgamation()
    common = [cc, "-O2", "-I", folder]
    libs = ["-lpthread", "-lm"] + (["-ldl"] if platform.system() == "Linux" else [])
    sqlite_bench = os.path.join(OUT, "bench-sqlite")
    shell = os.path.join(OUT, "sqlite3")
    sh(common + ["-o", sqlite_bench, os.path.join(HERE, "c", "bench.c"), os.path.join(folder, "sqlite3.c")] + libs)
    if not os.path.exists(shell):
        sh(common + ["-o", shell, os.path.join(folder, "shell.c"), os.path.join(folder, "sqlite3.c")] + libs)
    sh(["ceesafec", "build", "--cflag", "-O2"], cwd=HERE)
    version = subprocess.run(["ceesafec", "--version"], capture_output=True, text=True).stdout.strip()
    return sqlite_bench, shell, os.path.join(OUT, "sqlite_bench"), version


def fresh(path):
    for suffix in ("", "-journal", "-wal", "-shm"):
        if os.path.exists(path + suffix):
            os.remove(path + suffix)


def run(command):
    """Each workload's (name, operations, nanoseconds, checksum)."""
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode != 0:
        sys.exit(f"{' '.join(command)} failed ({done.returncode}):\n{done.stderr}")
    rows = []
    for line in done.stdout.splitlines():
        name, ops, ns, checksum = line.split("\t")
        rows.append((name, int(ops), int(ns), int(checksum)))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rows", type=int, default=100000)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--work", default=os.path.join(OUT, "work"), help="where the databases are made (a disk)")
    parser.add_argument("--cc", default=os.environ.get("CC", "cc"))
    a = parser.parse_args()
    os.makedirs(a.work, exist_ok=True)
    sqlite_bench, shell, ceesafe_bench, version = build(a.cc)

    times = {e: {} for e in ENGINES}
    checks = {}
    ops = {}
    order = []
    files = {}
    for r in range(a.runs):
        for engine in ENGINES:
            path = os.path.join(a.work, f"{engine}.db")
            fresh(path)
            files[engine] = path
            if engine == "ceesafe":
                command = [ceesafe_bench, path, str(a.rows)]
            else:
                command = [sqlite_bench, path, str(a.rows), engine.split("-")[1]]
            print(f"run {r + 1}/{a.runs}: {engine}", file=sys.stderr, flush=True)
            for name, n, ns, checksum in run(command):
                if name not in ops:
                    order.append(name)
                    ops[name] = n
                times[engine].setdefault(name, []).append(ns)
                checks.setdefault(name, set()).add(checksum)
    differ = [name for name in order if len(checks[name]) != 1]
    if differ:
        sys.exit(f"the engines' answers differ in: {', '.join(differ)}: {[checks[d] for d in differ]}")

    query = "PRAGMA integrity_check; SELECT count(*), sum(a), sum(b), sum(length(c)), sum(length(c) * a % 7) FROM t1; SELECT count(*), sum(a) FROM t3;"
    answers = {e: subprocess.run([shell, files[e], query], capture_output=True, text=True).stdout for e in ENGINES}
    for e in ENGINES:
        if not answers[e].startswith("ok\n") or answers[e] != answers["sqlite-prepared"]:
            sys.exit(f"SQLite's shell finds {e}'s file different:\n{answers[e]}\nnot\n{answers['sqlite-prepared']}")

    def ms(engine, name):
        return statistics.median(times[engine][name]) / 1e6

    print(f"rows {a.rows}, {a.runs} runs, medians in ms; ceesafec {version.split()[-1]} and SQLite {SQLITE_NAME}, both -O2 "
          f"({a.cc}); {platform.system()} {platform.machine()}")
    print("every checksum agrees; each engine's file passes integrity_check in SQLite's shell, with the same rows")
    print()
    print("| workload | statements | CeeSafe | SQLite, prepared each time | SQLite, prepared once | × reprepared | × prepared |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    totals = {e: 0.0 for e in ENGINES}
    for name in order:
        t = {e: ms(e, name) for e in ENGINES}
        for e in ENGINES:
            totals[e] += t[e]
        ratio = lambda e: f"{t['ceesafe'] / t[e]:.1f}" if t[e] > 0 else "-"
        print(f"| {name} | {ops[name]} | {t['ceesafe']:.1f} | {t['sqlite-reprepare']:.1f} | {t['sqlite-prepared']:.1f} "
              f"| {ratio('sqlite-reprepare')} | {ratio('sqlite-prepared')} |")
    print(f"| total | | {totals['ceesafe']:.1f} | {totals['sqlite-reprepare']:.1f} | {totals['sqlite-prepared']:.1f} "
          f"| {totals['ceesafe'] / totals['sqlite-reprepare']:.1f} | {totals['ceesafe'] / totals['sqlite-prepared']:.1f} |")


if __name__ == "__main__":
    main()
