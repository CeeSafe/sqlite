# CeeSafe findings

Gaps and rough edges in CeeSafe met while porting the SQLite engine, to be fixed in CeeSafe later. Compiler:
`ceesafec 0.93.7`. Each entry says what was needed, what happened, and the workaround used in this package.

## Gaps

### 1. No transcendental math on floats

`f64` has `sqrt`, `abs`, `floor`, `ceil`, `min`, `max` (type-system.md §35.8) and nothing else: no `exp`, `ln`,
`log10`, `log2`, `pow`, `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2`, `sinh`, `cosh`, `tanh` and their
inverses. SQLite's math functions (`exp()`, `ln()`, `pow()`, `sin()` …) need all of them, with results identical to
the platform libm in the last bit, since reals are shown with 17 significant digits.

Workaround: none yet; those SQL functions report "no such function". A port of an fdlibm-style library into the
package is the fallback, but a correctly rounded library in `lib/core` would serve every program.

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
