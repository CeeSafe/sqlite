# CeeSafe findings

Gaps and rough edges in CeeSafe met while porting the SQLite engine, to be fixed in CeeSafe later. Compiler:
`ceesafec 0.93.7`. Each entry says what was needed, what happened, and the workaround used in this package.

## Gaps

### 1. No transcendental math on floats

`f64` has `sqrt`, `abs`, `floor`, `ceil`, `min`, `max` (type-system.md §35.8) and nothing else: no `exp`, `ln`,
`log10`, `log2`, `pow`, `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2`, `sinh`, `cosh`, `tanh` and their
inverses. SQLite's math functions (`exp()`, `ln()`, `pow()`, `sin()` …) need all of them, with results identical to
the platform libm in the last bit, since reals are shown with 17 significant digits.

Workaround: `src/libm.cee`, a port of FreeBSD msun with double-double versions of exp, the logs, pow, sinh, cosh,
tanh, asin, acos and atan2. It still differs from macOS's libm in the last bit for some arguments (README.md lists
how often); a correctly rounded library in `lib/core` would serve every program.

### 2. No arithmetic right shift, no shifts on signed integers

`>>` and `<<` take unsigned operands only. SQLite's `pwr10to2(p) = (p*108853) >> 15` relies on an arithmetic shift
of a negative number (a floor division by a power of two).

Workaround: `floorDivide(value, divisor)` written by hand (`src/numeric.cee`). A `shiftRightArithmetic` (or `>>` on
signed types, defined as arithmetic) would say it directly.

### 3. No advisory file locks

There is no `flock`/`fcntl` locking on `File`. SQLite's locking protocol (shared, reserved, pending, exclusive locks
on the database file) cannot be followed, so this engine cannot safely share a database with another process.

Workaround: documented as a limit in README.md ("one process at a time").

### 4. Arc has no access for mutation

`Arc<T>` gives `get(borrow this) -> borrow T` only: there is no `getMut` when the count is one, nor a copy-on-write
`makeMut`. Pages shared between a cache and readers could be updated in place otherwise.

Workaround: the writable pager keeps pages as `Vector<u8>` and copies one into a new `Arc` for each reader
(`src/pagerw.cee`, `readPage`).

### 5. Appending ASCII bytes to a String is roundabout

There is no `String.push(byte)` or `appendAscii(bytes)`; building numbers digit by digit needs
`out.append(StringView.fromUtf8(bytes)!)` with an unwrap that cannot fail. `appendChar` and `appendUtf8` exist on
`String` (the compiler lists them in a "did you mean") but are not documented in the guide or the API pages.

Workaround: a local `appendAscii` helper (`src/numeric.cee`).

### 14. No local time zone

`Clock` gives UTC only: there is no `localtime_r` equivalent (the offset from UTC and whether daylight saving
applies at a given moment), nor a way to read the system's zone. SQLite's 'localtime' and 'utc' modifiers convert
through it.

Workaround: those modifiers are an error, "local time unavailable", where SQLite would consult the zone
(`src/datetime.cee`). Reading `TZ` and the TZif files under `/usr/share/zoneinfo` by hand is possible but would
reimplement the C library's zone rules.

## Rough edges

### 6. Two interfaces cannot each have a method of the same name on one type

`impl PageSource for WritablePager` and `impl PageSink for WritablePager`, both with `fn usableSize(borrow this)`,
is N0228 ("already has a member named 'usableSize'"), even with identical signatures.

Workaround: the sink's method is named `usableBytes`.

### 7. Float literals are not patterns

`value is SqliteValue.Real(1000.0)` is a parse error: "expected identifier, found float literal". Integer literals
work in the same place.

Workaround: `value is SqliteValue.Real(r) && r == 1000.0`.

### 8. Moving out of a Box is not discoverable

`*boxed` on a `Box<Expr>` is N0205 ("'*' reads through a reference"). The way that works,
`let inner: Expr = boxed;` (type-system.md §18.3), is not suggested by the diagnostic.

### 9. Closure parameter types are not inferred from use

`let at = (index) => if (index < n) text[index] else 0u8;` is N0236; the parameter needs `index: usize` although
every use fixes it.

### 10. Common names are reserved

`drop` (a method name) and `own` (a binding) are reserved words. The diagnostic is clear; listed because they are
natural names in a database engine (`DROP TABLE`, an owned value).

### 11. Arrays need elements without drop

`let parts = [a, b];` where the elements own a `Vector` is N0259 ("an array's elements must not need drop yet").
Small fixed lists of owned values (two operands' descriptions) have to be a `Vector` or be reduced to Copy data.

Workaround: a Copy `CollationInfo` struct holds what the array needed (`src/compile.cee`).

### 12. A reference variable cannot be re-pointed

`var e = borrow term.expr; if (e is Expr.Collate(inner, _)) { e = inner; }` is N0246: a `var` reference writes
through on assignment. Choosing one of two borrows needs a function or an `if` expression:
`let e = if (…) borrow a else borrow b;`.

Workaround: `withoutCollate(e) -> borrow Expr` (`src/select.cee`).

### 13. No consuming `for` over a Vector

`for (row in rows)` borrows each element, so moving rows out of a vector one by one needs an index loop and
`replace(mut rows[i], Vector.create())`, or repeated `remove(0)`, which is quadratic.

Workaround: `takeRow` (`src/run.cee`).

### 15. A package has one namespace for top-level names

Every top-level function of a package shares one namespace, and there is no file-private visibility. Two
files written apart (`datetime.cee` and `printf.cee`, ported in parallel) each defined `appendInteger` and
`appendFloat`, and the merge stopped compiling with N0201. A file-private (or module) scope would let helpers keep
short names.

Workaround: prefix helpers with their file's subject (`printfInteger`).

### 16. Constant arrays cannot hold `f64`

A `const` or `static` array of `f64` is refused, so tables of factors (date.c's unit limits) are kept as `i64`
and converted where they are used.

### 17. A slice of an array literal cannot be returned

`return [a, b][..];` from a function returning `Slice<T>` is refused: the array literal is a temporary. Fixed
tables need a `static`, even when the values are constants.

Workaround: `static PRAGMA_COLUMNS_n` (`src/pragma.cee`).

### 18. More common names are reserved

Besides `drop` and `own` (finding 10), `internal`, `match` and `private` cannot be used as names (a field `internal`, a
function `match`), and the error does not say the word is reserved.

### 19. Text that is not UTF-8 has no text type

`String` and `StringView` hold valid UTF-8 only, and there is no text type for bytes that are mostly UTF-8 (C's
`char *`, Rust's `OsString`/`bstr`). SQLite's TEXT may hold any bytes: its JSON functions decode `"\ud800"` to
ED A0 80, an unpaired surrogate, and `CAST(x'ff' AS TEXT)` keeps the byte. A value type built on `String` cannot
carry those bytes through.

Workaround: `textFromBytesLossy` (`src/value.cee`) turns each byte of an invalid sequence into U+FFFD, and the
difference is listed in README.md. A byte-string type with UTF-8 views on demand would let the engine keep
SQLite's bytes.

### 20. No fused multiply-add, and none of C's float helpers besides sqrt

Finding 1's workaround is now `src/libm.cee`, a port of FreeBSD's msun plus double-double arithmetic. Porting it
met more gaps of the same kind: there is no `fma` (an exact product needs Dekker's split into 26-bit halves,
about ten operations instead of one), no `scalbn`/`ldexp`/`frexp`, no `copysign`, no round-to-nearest-integer
(`rint`; `x + 0x1.8p52 - 0x1.8p52` does it), and no hexadecimal float literals, so exact constants are written as
`f64.fromBits(0x...)`. Nor is there a `wrapping` form of the bit tricks C does on signed words: msun's
`(hx - 0x3ff00000) | lx` and `j += n << 20` had to become comparisons and `i64` arithmetic.

Workaround: `libmScalbn`, `libmWords`, `ddTwoProduct` and friends in `src/libm.cee`. A correctly rounded math
library in `lib/core` (CORE-MATH's functions are small and exact) would make all of it unnecessary.

### 21. No inclusive range

`0..=n` is refused (N0100, "ranges in expressions are half-open"), so a C loop `for (i = 0; i <= m; i++)` becomes
`0..m + 1`, which reads as a different bound and overflows when `m` is the type's maximum.

Workaround: `0..m + 1` (`src/libm.cee`).

### 22. A Vector cannot be iterated by value

`for (t in v)` borrows each element, and there is no consuming iteration (`drain`, `intoIter`), so moving every
element of a vector into another container in order takes `while (v.length != 0) { w.push(v.remove(0))?; }`,
which is quadratic, or a reversed `pop` loop and a second reversal. `integrity.cee` (`tablesInSqliteOrder`) does
the former on short lists. A `for (t in move v)` or a `Vector.drain()` iterator would say what is meant.

### 23. No timed wait for threads

There is no blocking sleep outside async code (`Timer.sleep` is async), no `Channel.recv` with a timeout, and no
condition variable. A connection waiting for another's transaction to end (SQLite's busy timeout), and a pool
checkout waiting for a free connection, must give up after a time, so neither can use the blocking `recv()`.

Workaround: `takeFrom` (`src/api.cee`) polls `tryRecv()` against `Timer.now()` until the deadline, which spins a
core while it waits. A `recvTimeout(ms)` on `Channel`, or `Thread.sleep(ms)`, would do it without spinning.

### 24. No process-wide mutable state

The guide lists `Mutex<T>.constant(v)`, `OnceLock<T>.constant()` and `Vector<T>.empty()` for statics, but
`ceesafec 0.94.4` has none of them (N0200: "has no function named 'constant'"), so a `static` cannot hold a
registry. The C# kept one per process (`SharedStore`) so that every connection to a file found the same lock.

Workaround: only connections of one `ConnectionPool` share a gate; connections opened on their own each have
their own, and README.md says to use one pool per file.

### 25. A generic type argument is not inferred from a function passed by name

`connection.transaction(insertTwo)`, where `transaction<T: Send>` takes `work: borrow fn(borrow mut Connection) ->
Result<T, SqliteError>` and `insertTwo` returns `Result<i64, SqliteError>`, is N0265 ("cannot infer 'T'"); it
needs `transaction<i64>(insertTwo)`. Also `Pool` is a built-in name (N0201), like those of findings 10 and 18.

Workaround: the type argument is written (`tests/api_tests.cee`).

### 26. No shared memory

There is no memory-mapped file (`mmap` with `MAP_SHARED`) in the library. SQLite's WAL mode keeps its
wal-index in `<database>-shm`, mapped by every connection, with locks on bytes of it (finding 3); without
mapping, the index cannot be shared with sqlite3 or kept current across processes.

Workaround: the index is built in memory from the `-wal` file when the database is opened (`src/wal.cee`), and
no `-shm` is written; sqlite3 rebuilds its own. This is sound only with one process at a time (README.md,
Limits).

### 27. A file cannot be created for reading and writing

`File.create` makes (or empties) a file and opens it for writing only, and `File.openReadWrite` fails when the
file does not exist; there is no `O_RDWR | O_CREAT`. Reading from the handle `File.create` gives fails with
"Input/output error", which does not say that the handle was opened write-only (EBADF), so the WAL writer's
first checkpoint failed in a way that took a while to trace.

Workaround: create the file, drop the handle, and open it again with `File.openReadWrite`
(`WalLog.beginCommit` in `src/wal.cee`); between the two another process could replace it. An open-options
builder (read, write, create, truncate, exclusive) would cover this and `O_EXCL`.

### 28. A literal cannot be borrowed

`map.contains(borrow 1u32)` is refused (N0247, "only a variable, a field, or a place reached through a
reference can be borrowed"), so a lookup by a constant key needs a local first (`let first: u32 = 1;`,
`WritablePager.commit` in `src/pagerw.cee`). Borrowing a temporary for the length of the call, as Rust's `&1`
does, would remove the extra line.

### 29. No way to tell whether standard input is a terminal

There is no `isatty` (`Console.isTerminal()` or the like). The sqlite3 shell prints a banner and prompts when a
person types at it, and reads a script silently when its input is a pipe or a file; without the test, `cli/`
cannot tell the two apart.

Workaround: the shell always reads standard input as a script, without prompts (README.md, "Front ends").

### 30. A finished thread cannot be reaped

A `Thread<T>` has only `join()`, which waits; there is no `tryJoin` or `isFinished`. A server that starts a thread
for each client and runs for days cannot keep the handles (the vector would only grow) nor join them as their
clients leave. `Thread.service` starts a thread that is never joined, which fits, but then nothing tells the
program when the thread is done: `ceesafec test` reports a test as "leaked" when a client's service thread is
still freeing its session as the test ends.

Workaround: `pgwire/src/server.cee` serves each client on a service thread and counts the clients in an
`AtomicUSize`; the tests, and the daemon when it stops, poll the count down to zero (`PgServer.waitForClients`,
spinning against `Timer.now()` for want of a sleep: finding 23).

### 31. N0245's suggested fix does not fit a result that holds a slice

A method `fn span(borrow mut this, bytes: Slice<u8>, n: usize) -> Result<Slice<u8>, E>` is N0245 ("several
reference parameters: name the ones the result is borrowed from, e.g. 'borrow(a, b) T'"). Following it,
`-> borrow(bytes) Result<Slice<u8>, E>` makes the whole `Result` a reference (N0205, "expected 'borrow Result<…>'").
What works is a region parameter, `fn span<region r>(…, bytes: Slice<r, u8>, …) -> Result<Slice<r, u8>, E>`,
which the message does not mention.

Workaround: `Cursor.skip` in `pgwire/src/wire.cee` returns the index where the bytes start, and the caller slices.

### 32. No stable sort

`sortBy` is an introsort and documented as not stable; the library has no stable sort. SQLite's sorter keeps rows
with equal ORDER BY keys in the order they came, and answers must match it.

Workaround: `runSelect` (`src/run.cee`) appends each row's place as a last key and compares it after the ORDER BY
terms (`compareKeysThenPlace`).

### 33. A field cannot be moved out of an unwrapped temporary

`var seek = replace(mut best, null)!.seek;`, taking the one field wanted out of an optional that is owned and
dropped at once, is N0251 ("cannot move a 'IndexSeek' out of an element or enum payload of 'a temporary'; only
Copy values can be read from there"). The temporary is not borrowed from anywhere, so moving a field out of it
(and dropping the rest) would be safe.

Workaround: bind it first, `if (best is Some(b)) { var seek = b.seek; … }` (`planSource` in `src/plan.cee`).

### 34. An array literal's integers are `i32` whatever the context

`let a = [0, 2, 3, 5]; return a[i] + y;` with `y: i64` is N0205 (expected 'i64', found 'i32'): the literal's type
is not taken from its use, and an array literal has no suffix or annotation in the expression to give it.

Workaround: `(a[i] as i64) + y` (`logEst` in `src/plan.cee`).
