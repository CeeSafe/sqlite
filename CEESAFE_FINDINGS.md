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

Besides `drop` and `own` (finding 10), `internal` and `match` cannot be used as names (a field `internal`, a
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
