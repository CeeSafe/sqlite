# CeeSafe findings

Gaps and rough edges in CeeSafe met while porting the SQLite engine, to be fixed in CeeSafe later. Compiler:
`ceesafec 0.93.7`. Each entry says what was needed, what happened, and the workaround used in this package.

## Status (ceesafec 0.95.2)

| Finding | Status |
|---|---|
| 1, 20 | fixed in 0.95.0: float math methods (`exp`, `ln`, `pow`, trigonometry, `fma`, `copySign`, `scaleB`, `roundEven`, …), ADR 0218; hexadecimal float literals and `frexp` not added; workaround removed (`src/libm.cee` deleted: the math functions call the platform's libm, and match sqlite3 bit for bit) |
| 2 | fixed in 0.95.0: `wrappingShl`/`wrappingShr` on signed integers (arithmetic shift), ADR 0223; workaround removed (`pwr10to2`/`pwr2to10` shift; `floorDivide` stays for divisions by 27, 1000, 146097) |
| 3 | fixed in 0.95.0: byte-range advisory locks `lock`/`tryLock`/`unlock`, interoperating with sqlite3's, ADR 0220; workaround removed: the writable pager takes os_unix.c's locks (`src/pagerw.cee`), README.md's "one process at a time" limit is gone (and with 26's, WAL mode's turns too) |
| 4 | fixed in 0.95.0: `Arc.getMut()`, ADR 0224; workaround removed (the writable pager keeps `Arc` pages: a read shares the page, a write copies it only while a reader still has it) |
| 5 | already there: `appendChar`/`appendUtf8` are documented; now used (`appendAscii` is `appendUtf8` checked) |
| 7 | diagnostic in 0.95.0: float patterns say to use a guard or `==` (ADR 0228); not added as patterns, by choice |
| 8 | diagnostic in 0.95.0: `*b` on a box says `let inner: T = b;` (ADR 0228) |
| 11 | fixed in 0.94.5: arrays whose elements need drop; `CollationInfo` stays, as the snapshot taken before an operand moves into its node |
| 13, 22 | fixed in 0.95.0: `v.drain()`, ADR 0224; workaround removed (`takeRow` gone; the recursive CTE's step is linear now) |
| 14 | fixed in 0.55.0 (missed by the port): `Clock.localOffset(at)`, ADR 0153; workaround removed ('localtime' and 'utc' as SQLite's toLocaltime, tested under eight TZ values) |
| 16 | fixed in 0.95.0: floats in constant arrays, ADR 0226 |
| 17 | diagnostic in 0.95.0: N0245 shows the `static` table form (ADR 0226) |
| 23, 30 | fixed in 0.95.0: `Thread.sleep`, `recvTimeout`, `t.isFinished()`, ADR 0222; 30's workaround removed (`pgwire` reaps its client threads, the daemon waits with `Thread.sleep`); 23's workaround removed: the polling `takeFrom` is gone, a busy wait sleeps as SQLite's busy handler does (`busyWait`, `src/pagerw.cee`) and a pool checkout waits with `recvTimeout` |
| 24 | fixed in 0.94.5: `Mutex.constant`, `OnceLock.constant`, `Vector.empty` in statics; workaround removed, and no registry needed: file locks owned by each open file keep every connection apart, so the pool's gate is gone |
| 25 | fixed by 0.94.5 |
| 27, 29 | fixed in 0.95.0: `File.createReadWrite`, `IoError.BadDescriptor`, `Console.isTerminal`, ADR 0221; 29's workaround removed (`cli` prompts at a terminal); 27's workaround removed: the log is made with `File.openOrCreate` when a connection opens it in WAL mode (`SharedWal.open`, `src/walindex.cee`) |
| 28, 33 | fixed in 0.95.0: `borrow` of a value lent to its statement; a field moved out of `e?.f`/`e!.f`, ADR 0227; 33's site was since rewritten (`let Some(choice) = … else`) |
| 31 | diagnostic in 0.95.0: N0245 names a region parameter for a result holding a reference (ADR 0228); workaround removed (`Cursor.skip` returns the slice) |
| 32 | fixed in 0.95.0: `sortStableBy`, ADR 0225; workaround removed (every ORDER BY sort, the compound one included, which was unstable) |
| 34 | fixed in 0.95.0 for an expected slice or number (ADR 0226); `let a = [1, 2];` stays `i32`, as `let x = 1;` does; `logEst`'s tables are typed `[i64; N]` |
| 9, 10, 12, 18, 21 | by design: closures are typed where a function type is expected; reserved words, now named as such in the error; references are not re-pointed; ranges are half-open (ADR 0085) |
| 6 | fixed in 0.95.2: methods of one name from several interfaces, and `I.m(x, …)` to name one (N0267 when a call on the type is ambiguous), ADR 0229; workaround removed (`PageSink.usableSize` again, beside `PageSource.usableSize`) |
| 15 | fixed in 0.95.2: a file's `private` items have a scope of their own, so two files may each have a private item of one name, ADR 0230; workaround removed (`datetime.cee` and `printf.cee` each have a private `appendInteger` and `appendFloat`) |
| 19 | fixed in 0.95.2: `ByteString`/`ByteStringView` in lib/core, any bytes kept as they are, with `toUtf8`, `toUtf8Lossy` and `chunks`, ADR 0231; workaround removed: `SqliteValue.Text` holds a `ByteString`, `textFromBytesLossy` is gone, and the text functions read bytes by SQLite's rules (README's "Text of any bytes") |
| 26 | fixed in 0.95.2: `SharedMapping`, `f.mapShared(offset, length)`, with `readAt`/`writeAt` and 32- and 64-bit atomics, checked against a live sqlite3 `-shm`, ADR 0232; workaround removed: the `-shm` is mapped in 32 KiB blocks and kept as wal.c keeps it, with os_unix.c's fcntl locks on its bytes (`src/walindex.cee`), and the turns are gone: a connection in WAL mode holds SHARED on the database file while it has it open, readers take read marks beside the writer, in this engine and with a running sqlite3, both ways (`tests/shm_tests.cee`); what is still missing (finding 37) is worked around or refused, and README.md's Limits say how |
| 35 | fixed in 0.95.2: a `Thread<void>` in a generic signature is checked as a return type, no longer N0226; workaround removed (`pgwire`'s client threads are `Thread<void>`) |
| 36 | open: found while removing the workarounds for 3, 23, 24 and 27 (below) |
| 37 | open: found with 26's fix (below); met by the `-shm` port: no 16-bit atomics either (the hash slots are reached through the aligned 32-bit word holding two) |
| 38 | open: found with 19's fix (below) |
| 39 | open: found while removing 19's workaround (below) |
| 41 | open: found while making SQL text bytes (below) |
| 40 | misreported: `cfg("target.windows")` (ADR 0179, guide/unsafe-and-c.md "Code for one system") names the system a build is for, in any code; `onWindows()` uses it, and the environment-variable check is gone |

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

Workaround (removed with 0.95.0): documented as a limit in README.md ("one process at a time").

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

Workaround (removed with 0.95.0): `takeFrom` (`src/api.cee`) polled `tryRecv()` against `Timer.now()` until the deadline, which spins a
core while it waits. A `recvTimeout(ms)` on `Channel`, or `Thread.sleep(ms)`, would do it without spinning.

### 24. No process-wide mutable state

The guide lists `Mutex<T>.constant(v)`, `OnceLock<T>.constant()` and `Vector<T>.empty()` for statics, but
`ceesafec 0.94.4` has none of them (N0200: "has no function named 'constant'"), so a `static` cannot hold a
registry. The C# kept one per process (`SharedStore`) so that every connection to a file found the same lock.

Workaround (removed with 0.95.0, file locks making a registry unnecessary): only connections of one
`ConnectionPool` shared a gate; connections opened on their own each have
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
no `-shm` is written; sqlite3 rebuilds its own. Since finding 3's locks, each transaction in WAL mode holds the
database file's EXCLUSIVE lock (as SQLite's `locking_mode=EXCLUSIVE` does without a `-shm`), so connections in WAL
mode take turns instead of reading beside a writer (README.md, Limits, "No wal-index").

### 27. A file cannot be created for reading and writing

`File.create` makes (or empties) a file and opens it for writing only, and `File.openReadWrite` fails when the
file does not exist; there is no `O_RDWR | O_CREAT`. Reading from the handle `File.create` gives fails with
"Input/output error", which does not say that the handle was opened write-only (EBADF), so the WAL writer's
first checkpoint failed in a way that took a while to trace.

Workaround (removed with 0.95.0): create the file, drop the handle, and open it again with `File.openReadWrite`
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
Removed with 0.95.0: at a terminal the shell prints sqlite3's banner and prompts.

### 30. A finished thread cannot be reaped

A `Thread<T>` has only `join()`, which waits; there is no `tryJoin` or `isFinished`. A server that starts a thread
for each client and runs for days cannot keep the handles (the vector would only grow) nor join them as their
clients leave. `Thread.service` starts a thread that is never joined, which fits, but then nothing tells the
program when the thread is done: `ceesafec test` reports a test as "leaked" when a client's service thread is
still freeing its session as the test ends.

Workaround: `pgwire/src/server.cee` serves each client on a service thread and counts the clients in an
`AtomicUSize`; the tests, and the daemon when it stops, poll the count down to zero (`PgServer.waitForClients`,
spinning against `Timer.now()` for want of a sleep: finding 23). Removed with 0.95.0: `serve` keeps its clients'
threads in a `Vector<Thread<u64>>` (finding 35), joins the finished ones as clients come, and joins the rest when
its listener is shut down; the daemon waits for `serve`'s thread with `isFinished` and `Thread.sleep`.

### 31. N0245's suggested fix does not fit a result that holds a slice

A method `fn span(borrow mut this, bytes: Slice<u8>, n: usize) -> Result<Slice<u8>, E>` is N0245 ("several
reference parameters: name the ones the result is borrowed from, e.g. 'borrow(a, b) T'"). Following it,
`-> borrow(bytes) Result<Slice<u8>, E>` makes the whole `Result` a reference (N0205, "expected 'borrow Result<…>'").
What works is a region parameter, `fn span<region r>(…, bytes: Slice<r, u8>, …) -> Result<Slice<r, u8>, E>`,
which the message does not mention.

Workaround: `Cursor.skip` in `pgwire/src/wire.cee` returns the index where the bytes start, and the caller slices.
Removed with 0.95.0: it is `fn skip<region r>(…, bytes: Slice<r, u8>, …) -> Result<Slice<r, u8>, WireError>`.

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

### 35. `Vector<Thread<void>>.swapRemove` is refused

Found while adding `t.isFinished()` (ADR 0222): `swapRemove` on a vector of `Thread<void>` is N0226, though a
`Thread<u64>` works. Workaround: give the threads a result type.

### 36. A lock cannot be tested without taking it

Found while following os_unix.c with ADR 0220's locks. SQLite's hot-journal check asks whether another
connection holds RESERVED (`unixCheckReservedLock`, an `F_GETLK` on the RESERVED byte), which changes nothing.
`File` has `lock`, `tryLock` and `unlock` only, so the test takes the byte with `tryLock` and releases it: in that
instant another connection's RESERVED attempt fails once and goes to its busy handler. A `f.testLock(kind, start,
length) -> Result<bool, IoError>` (or the holder's process id, as `F_GETLK` gives) would say it without side
effect. Also, ADR 0220's portable contract forbids converting a held lock in place, which is how os_unix.c goes
from SHARED to EXCLUSIVE; os_win.c instead unlocks and relocks a random byte of the range. The port follows
os_unix.c (POSIX hosts only); a Windows build would need the os_win.c scheme.

Workaround: `tryLock` then `unlock` (`WritablePager.tryStart`, `src/pagerw.cee`); README.md, Limits, "Sharing a
file". The `-shm`'s DMS byte, which os_unix.c tests with `F_GETLK` (unixLockSharedMemory), is tried exclusively
and, failing that, shared (`SharedWal.open`, `src/walindex.cee`), which takes the same decision without a test.

### 37. A shared mapping lacks what SQLite's wal-index uses beyond reads, writes and atomics

Found with finding 26's fix (ADR 0232, 0.95.2). `SharedMapping` maps a region read-write and gives copies and
atomics, which covers the wal-index's header and hash tables. Still missing for a full `-shm` as os_unix.c keeps it:
a read-only mapping (SQLite's `readonly_shm`, for a database whose `-shm` cannot be written); a shortened file is
SIGBUS, which ends the program instead of becoming an `IoError` (CeeSafe never shortens one itself, and Windows
refuses to); the interpreter models a mapping by positional reads and writes, so its atomics are atomic among the
program's threads but not against another process. The Windows code is compiled by the release workflow but has
not been run against sqlite3 there.

Also missing, found while writing the `-shm` (finding 26's workaround removed): 16-bit atomics. wal.c's hash
tables are arrays of `u16` slots that readers load atomically while the writer stores; `SharedMapping` has 32- and
64-bit atomics only, and `readAt` of two bytes is a copy that could, in principle, tear.

Workaround: the `-shm` is opened read-write, and a database whose `-shm` cannot be written fails with the
`IoError` (SQLite would fall back to `readonly_shm` or heap memory); a hash slot is read with `load32` of the
aligned word that holds it and its neighbour, and the writer stores whole words (`findInBlock`, `writeBlock`,
`src/walindex.cee`); nothing protects against another process shortening the file (SQLite has the same exposure).
The DMS test uses `tryLock` (finding 36).

### 38. An optional borrow cannot be compared with `Some(…)`

Found with finding 19's fix. `m.get(k) == Some(x)`, where `get` gives a `borrow V?`, is N0205 or N0207, though
`o == Some(3)` works on an owned optional (the guide's "Common mistakes"). The tests match instead:
`match (m.get(k)) { Some(v) => …, null => … }`.

Workaround: `match`, or `m.get(k).isSome()` and a separate comparison.

### 39. A `String` cannot become a `ByteString` without a copy

Found while removing finding 19's workaround. `ByteString.fromBytes(v)` takes a `Vector<u8>` without copying, but
a `String` has no `intoBytes()` and `ByteString` no `fromString(s)`, so text built in a `String` (a number written
by `appendReal`, an ALTER TABLE's edited SQL, CURRENT_TIMESTAMP) is copied again to become a TEXT value:
`ByteString.fromText(s.view())`. A `String` is valid UTF-8, so the move cannot break anything. Nor does
`ceesafec doc` take a type's name (`ceesafec doc ByteString` is "not a .cee or .c file"), so the members of a
lib/core type are found in its source or through the MCP server.

Workaround: the copy (`SqliteValue.text(s.view())`), or building the bytes in a `ByteString` or `Vector<u8>` from
the start where the text is a function's result (`concat`, `group_concat`, `printf`, `hex`, `upper`).

### 41. Text code written for `StringView` cannot take a `ByteStringView`

Found while making the engine take SQL as bytes (README's "SQL text of any bytes"). The tokenizer, the parser, the
catalog's names and every error message are written against `String` and `StringView`: `==` with a literal,
`equalsIgnoreAsciiCase`, `split`, `splitOnce`, `parseInt`, slicing, `String.append`. `ByteStringView` has a
subset of these, its search methods take a `Slice<u8>` rather than text (`m.startsWith("UNIQUE")` is N0205,
"expected 'Slice<u8>', found 'StringView'"; it must be `m.startsWith("UNIQUE".bytes())`), and no interface covers
both views, so a function cannot be written once for either. Moving some 36,000 lines from `String` names to
`ByteString` ones would have meant rewriting every name comparison, message and slice.

Workaround: SQL text stays a `String` inside the engine, in a lossless form: each byte of a sequence that is not
UTF-8 stands as one code point of U+10FF80..U+10FFFF, and a real one of those is escaped the same way
(`src/sqltext.cee`); the API takes `ByteStringView`, and names leave as bytes where they become values or
messages. A text-view interface implemented by both `StringView` and `ByteStringView` (or `ByteStringView`
methods that take text, as `ByteString.append` does) would let such code be generic.
