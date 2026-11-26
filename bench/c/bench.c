/* bench.c: bench/src/main.cee's workloads on SQLite itself, with the same SQL, parameters and checksums
 * (README.md, "Benchmark"). Built by bench/run.py with the amalgamation.
 *
 *   bench FILE [N] [prepared|reprepare]
 *
 * "prepared" prepares each workload's statement once and resets it between runs, as an application written for
 * SQLite does; "reprepare" (the default) prepares and finalizes it for every run, as this package's API does,
 * which parses each statement it is given. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "sqlite3.h"

static sqlite3 *db;
static int reprepare = 1;

static void die(const char *what) {
    fprintf(stderr, "%s: %s\n", what, sqlite3_errmsg(db));
    exit(1);
}

static unsigned long long nanos(void) {
    struct timespec t;
    clock_gettime(CLOCK_MONOTONIC, &t);
    return (unsigned long long)t.tv_sec * 1000000000ull + (unsigned long long)t.tv_nsec;
}

static long long rnd(long long i) { return (i * 1103515245 + 12345) % 1000000; }

static int label(char *out, long long i) { return sprintf(out, "v%lld", rnd(i)); }

static void exec(const char *sql) {
    char *err = 0;
    if (sqlite3_exec(db, sql, 0, 0, &err) != SQLITE_OK) {
        fprintf(stderr, "%s: %s\n", sql, err);
        exit(1);
    }
}

/* One workload's statement: prepared once, or again for each run. */
typedef struct {
    const char *sql;
    sqlite3_stmt *stmt;
} Statement;

static sqlite3_stmt *start(Statement *s) {
    if (s->stmt == 0) {
        if (sqlite3_prepare_v2(db, s->sql, -1, &s->stmt, 0) != SQLITE_OK) die(s->sql);
    }
    return s->stmt;
}

static void finish(Statement *s) {
    if (reprepare) {
        sqlite3_finalize(s->stmt);
        s->stmt = 0;
    } else {
        sqlite3_reset(s->stmt);
        sqlite3_clear_bindings(s->stmt);
    }
}

static void done(Statement *s) {
    if (s->stmt) sqlite3_finalize(s->stmt);
    s->stmt = 0;
}

/* main.cee's weight(): an integer itself, a real's thousandths, a text's or blob's length in bytes. */
static long long weight(sqlite3_stmt *st, int c) {
    switch (sqlite3_column_type(st, c)) {
    case SQLITE_INTEGER: return sqlite3_column_int64(st, c);
    case SQLITE_FLOAT: {
        double r = sqlite3_column_double(st, c) * 1000.0;
        if (r >= 9223372036854775807.0) return 9223372036854775807ll;
        if (r <= -9223372036854775808.0) return (-9223372036854775807ll - 1);
        return (long long)r;
    }
    case SQLITE_TEXT: return sqlite3_column_bytes(st, c);
    case SQLITE_BLOB: return sqlite3_column_bytes(st, c);
    default: return 0;
    }
}

static long long wrapAdd(long long a, long long b) {
    return (long long)((unsigned long long)a + (unsigned long long)b);
}

/* Runs a bound statement: a query's checksum, or the rows a change changed. */
static long long step(Statement *s) {
    sqlite3_stmt *st = s->stmt;
    long long total = 0;
    int rc;
    int columns = sqlite3_column_count(st);
    while ((rc = sqlite3_step(st)) == SQLITE_ROW) {
        for (int c = 0; c < columns; c++) total = wrapAdd(total, weight(st, c));
    }
    if (rc != SQLITE_DONE) die(s->sql);
    if (columns == 0) total = sqlite3_changes(db);
    finish(s);
    return total;
}

static long long one(Statement *s, long long a) {
    sqlite3_bind_int64(start(s), 1, a);
    return step(s);
}

static long long none(Statement *s) {
    start(s);
    return step(s);
}

static void report(const char *name, long long ops, unsigned long long started, long long checksum) {
    unsigned long long ns = nanos() - started;
    printf("%s\t%lld\t%llu\t%lld\n", name, ops, ns, checksum);
    fflush(stdout);
}

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "usage: bench FILE [N] [prepared|reprepare]\n");
        return 2;
    }
    long long n = argc > 2 ? atoll(argv[2]) : 100000;
    if (n < 100) {
        fprintf(stderr, "usage: bench FILE [N] [prepared|reprepare]\n");
        return 2;
    }
    if (argc > 3) reprepare = strcmp(argv[3], "prepared") != 0;
    if (sqlite3_open(argv[1], &db) != SQLITE_OK) die("open");
    char text[64];
    unsigned long long started;
    long long sum;

    exec("CREATE TABLE t1(a INTEGER PRIMARY KEY, b INTEGER, c TEXT); CREATE TABLE t2(k INTEGER PRIMARY KEY, name TEXT); CREATE TABLE t3(a INTEGER, b TEXT)");
    exec("BEGIN");
    {
        Statement s = {"INSERT INTO t2(k, name) VALUES (?1, ?2)", 0};
        for (long long k = 0; k < 1000; k++) {
            sqlite3_bind_int64(start(&s), 1, k);
            int len = label(text, k);
            sqlite3_bind_text(s.stmt, 2, text, len, SQLITE_TRANSIENT);
            step(&s);
        }
        done(&s);
    }
    exec("COMMIT");

    {
        Statement s = {"INSERT INTO t1(a, b, c) VALUES (?1, ?2, ?3)", 0};
        started = nanos();
        sum = 0;
        exec("BEGIN");
        for (long long i = 1; i < n + 1; i++) {
            sqlite3_bind_int64(start(&s), 1, i);
            sqlite3_bind_int64(s.stmt, 2, rnd(i));
            int len = label(text, i);
            sqlite3_bind_text(s.stmt, 3, text, len, SQLITE_TRANSIENT);
            sum += step(&s);
        }
        exec("COMMIT");
        report("insert-txn", n, started, sum);
        done(&s);
    }

    long long k = n / 100;
    {
        Statement s = {"INSERT INTO t3(a, b) VALUES (?1, ?2)", 0};
        started = nanos();
        sum = 0;
        for (long long i = 0; i < k; i++) {
            sqlite3_bind_int64(start(&s), 1, i);
            int len = label(text, i);
            sqlite3_bind_text(s.stmt, 2, text, len, SQLITE_TRANSIENT);
            sum += step(&s);
        }
        report("insert-autocommit", k, started, sum);
        done(&s);
    }

    {
        Statement s = {"CREATE INDEX t1b ON t1(b)", 0};
        started = nanos();
        sum = none(&s);
        report("create-index", 1, started, 0);
        done(&s);
    }

    long long m = n / 5;
    {
        Statement s = {"SELECT b, c FROM t1 WHERE a = ?1", 0};
        started = nanos();
        sum = 0;
        for (long long i = 0; i < m; i++) sum = wrapAdd(sum, one(&s, (i * 7919) % n + 1));
        report("select-rowid", m, started, sum);
        done(&s);
    }
    {
        Statement s = {"SELECT a FROM t1 WHERE b = ?1", 0};
        started = nanos();
        sum = 0;
        for (long long i = 0; i < m; i++) sum = wrapAdd(sum, one(&s, rnd((i * 7919) % n + 1)));
        report("select-index-eq", m, started, sum);
        done(&s);
    }
    {
        Statement s = {"SELECT count(*), sum(a) FROM t1 WHERE b >= ?1 AND b < ?1 + 1000", 0};
        started = nanos();
        sum = 0;
        for (long long i = 0; i < 1000; i++) sum = wrapAdd(sum, one(&s, (i * 997) % 1000000));
        report("select-index-range", 1000, started, sum);
        done(&s);
    }
    {
        Statement s = {"SELECT count(*) FROM t1 WHERE c LIKE ?1", 0};
        started = nanos();
        sum = 0;
        for (long long i = 0; i < 10; i++) {
            int len = sprintf(text, "%%%lld7%%", i);
            sqlite3_bind_text(start(&s), 1, text, len, SQLITE_TRANSIENT);
            sum = wrapAdd(sum, step(&s));
        }
        report("scan-like", 10, started, sum);
        done(&s);
    }
    {
        Statement s = {"SELECT count(*), sum(b), max(length(c)) FROM t1 WHERE a % ?1 = 0", 0};
        started = nanos();
        sum = 0;
        for (long long i = 0; i < 10; i++) sum = wrapAdd(sum, one(&s, i + 2));
        report("scan-aggregate", 10, started, sum);
        done(&s);
    }
    {
        Statement s = {"SELECT b % ?1, count(*) FROM t1 GROUP BY 1", 0};
        started = nanos();
        sum = 0;
        for (long long i = 0; i < 10; i++) sum = wrapAdd(sum, one(&s, 100 + i));
        report("group-by", 10, started, sum);
        done(&s);
    }
    {
        Statement s = {"SELECT a, c FROM t1 ORDER BY c DESC, a LIMIT 100 OFFSET ?1", 0};
        started = nanos();
        sum = 0;
        for (long long i = 0; i < 5; i++) sum = wrapAdd(sum, one(&s, i * 1000));
        report("order-by", 5, started, sum);
        done(&s);
    }
    {
        Statement s = {"SELECT count(*), sum(t2.k) FROM t1 JOIN t2 ON t2.k = t1.b % 1000 WHERE t1.a % 10 = ?1", 0};
        started = nanos();
        sum = 0;
        for (long long i = 0; i < 5; i++) sum = wrapAdd(sum, one(&s, i));
        report("join", 5, started, sum);
        done(&s);
    }

    long long u = n / 10;
    {
        Statement s = {"UPDATE t1 SET b = b + 1 WHERE a = ?1", 0};
        started = nanos();
        sum = 0;
        exec("BEGIN");
        for (long long i = 0; i < u; i++) sum += one(&s, (i * 7919) % n + 1);
        exec("COMMIT");
        report("update-point", u, started, sum);
        done(&s);
    }
    {
        Statement s = {"UPDATE t1 SET c = c || 'x' WHERE a % 10 = 0", 0};
        started = nanos();
        sum = none(&s);
        report("update-bulk", 1, started, sum);
        done(&s);
    }
    {
        Statement s = {"DELETE FROM t1 WHERE a % 3 = 0", 0};
        started = nanos();
        sum = none(&s);
        report("delete-bulk", 1, started, sum);
        done(&s);
    }
    {
        Statement s = {"PRAGMA integrity_check", 0};
        started = nanos();
        sum = none(&s);
        report("integrity-check", 1, started, sum);
        done(&s);
    }
    started = nanos();
    exec("VACUUM");
    report("vacuum", 1, started, 0);
    {
        Statement s = {"SELECT count(*), sum(a), sum(b), sum(length(c)) FROM t1", 0};
        started = nanos();
        sum = none(&s);
        report("final-scan", 1, started, sum);
        done(&s);
    }
    if (sqlite3_close(db) != SQLITE_OK) die("close");
    return 0;
}
