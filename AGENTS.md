<!--CEESAFE START-->

# Using CeeSafe

This package is written in CeeSafe, a memory-safe systems programming language with modern syntax that
`ceesafec` compiles ahead of time to C. Ownership and borrowing are checked at compile time; there is no garbage
collector. CeeSafe is new: code that looks right from C#, TypeScript or Rust often is not CeeSafe. Check every edit with the
compiler, and read the guide for agents: https://ceesafe.github.io/CeeSafe/guide/for-agents (the whole guide and
specification for a model's context: https://ceesafe.github.io/CeeSafe/llms-full.txt).

## The package

- `ceesafe.toml` names the package, its kind (`executable` or `library`) and its dependencies; `ceesafe.lock` pins them.
- The sources are the `.cee` files under `src/`. A program starts at `fn main()`.
- `ceesafec build` writes to `out/`, which is not committed.

## Commands

Run them in the package's directory; without file arguments they use the package.

| Command | What it does |
|---|---|
| `ceesafec check` | parse, type-check and borrow-check; the fastest way to find errors |
| `ceesafec fix` | apply the fixes the compiler is sure of, then check again |
| `ceesafec explain N0249` | what a diagnostic code means |
| `ceesafec run --interp` | run the program in the interpreter |
| `ceesafec build` | compile through C to `out/<name>` |
| `ceesafec fmt` | format in the one canonical style; `ceesafec fmt --check` lists files that would change |
| `ceesafec fetch` | resolve the dependencies and write `ceesafe.lock` |

Add `--diagnostics-format=json` to `check`, `build`, `run` or `fix` for one JSON document with every diagnostic, its
position and its fixes.

## The MCP server

If you have the `ceesafe` MCP server (`ceesafec mcp`), use its tools: `ceesafe_check` after every edit, `ceesafe_fix` for the
fixes it offers, `ceesafe_explain` for a code, `ceesafe_spec_search` and `ceesafe_spec_section` for the rules, `ceesafe_run` to
run code in a sandbox. The specification is embedded in `ceesafec`, so its answers match the compiler.

## Before you finish

- [ ] `ceesafec check` reports no errors (run `ceesafec fix` first).
- [ ] `ceesafec fmt --check` lists no file.
- [ ] The program does what was asked: `ceesafec run --interp`, or `ceesafec build` and run it.

## Common mistakes

- `~x`, `& | ^` and shifts take unsigned integers only; `!` is for `bool`. There are no type aliases or tuples, and no
  `==` on structs.
- An optional's fallback is `o ?? value`, or a block that leaves, `o ?? { return Err(e); }`; `o.isSome()` and
  `o.isNull()` test it, and `o == Some(3)` compares. `let _ = f();` discards a value.
- Indexes are `usize`. `0..4` is a `usize` range when the body indexes with its variable, else `i32`; `0..values.length` is `usize`.
- `if` and `match` expressions take expressions, `let s = if (x < 0) -1 else 1;`, or blocks that end with their value
  without `;`; a statement's block has no value.
- A variable that changes is `var`; a `let` cannot be assigned. A `borrow mut` argument is written `mut x`.
- `as` converts only without loss; `truncate<u8>(x)` wraps; `checkedTruncate<i64>(n)` (an optional) and
  `saturatingTruncate<u8>(n)` check or clamp, for integers and floats.
- `for (part in text.split(","))` loops over any value with `fn next(borrow mut this) -> T?`.
- A multi-line string is a raw `"""` literal: the closing `"""` line's indentation is removed, and there are no escapes.
- A function that always exits returns `never`: `fn die(m: StringView) -> never { …; Process.exit(1); }`.
- An `async move` child (`s.spawn`, `set.spawn`, `Async.timeout`/`race`/`all`) owns its captures and may move them.
- A view of a temporary, `make().view()`, lasts until the end of its statement: to keep it, bind the value to a local.
- There is no string interpolation: `"x = {x}"` prints `{x}` (warning N0400); write the value in a call of its own.
- A function or closure in a field is called as `c.step(n)`; a struct that borrows a closure has a region parameter.
- A `StringView` inside an enum or struct needs a region parameter; for fixed messages, use an enum of reasons.
- A method cannot have the name of a field.
- Look a name up before deciding it does not exist: MCP `ceesafe_api` (`TextWriter.decimal`, `Process.argument`), or
  the guide's built-in types page and the lib/core and lib/std API pages. A "did you mean" in an error names the real one.
- A lookup that may find nothing is an optional (`Process.argument(i)`, `StringView.fromUtf8(b)`): `Some`/`null`.
- Some keywords read like names (`own`, `type`, `move`, `drop`, `where`); async code uses `AsyncConsole`, not `Console`.

<!--CEESAFE END-->

# sqlite project rules

- This package is a SQLite engine (byte-compatible file format, SQL, storage) ported from the pure-C# engine in
  `~/dev/CosmoStack/src/CosmoNova.Engine.Sqlite` (tests: `~/dev/CosmoStack/tests/CosmoNova.Sqlite.Engine.Tests`).
- The C# is a reference for behaviour, not a text to transcribe: do not carry its bugs over. Read each file
  critically, fix what is wrong, and add the difference to README.md's "Differences from the C# engine" with a test
  that would fail on the C# behaviour. Where the C# and real SQLite disagree, SQLite is right.
- Nothing in the file is trusted: every offset, length and page pointer read from a database is checked, and a
  damaged file is `SqliteError.Corrupt`, never a panic or a hang. Tree walks use explicit stacks or a depth limit.
- There are no exceptions: fallible functions return `Result<T, SqliteError>` (`src/errors.cee`).
- Tests are differential: fixtures are made by the `sqlite3` shell (`makeDatabase`), and answers are compared with
  what it prints (`askSqlite`). Files the engine writes must pass `PRAGMA integrity_check` in the shell.
- README.md's "Status" lists what is ported and what is next; keep it current.
- New CeeSafe gaps or bugs go in CEESAFE_FINDINGS.md.
- The executor writes changes to the pages of the transaction's WritablePager instead of loading tables into memory
  as the C# did, and queries stream rows from cursors (README.md says why). Notes for the rest of the port:
  - tests are differential: `sameAnswers` (queries), `sameScript` (one sqlite3 process a statement) and
    `sameSession` (one sqlite3 process for a whole script, for transactions) compare answers and errors;
  - functions not yet ported (date/time, printf, JSON, transcendental math) report "no such function";
  - a column with REAL affinity may hold an integer in a record SQLite wrote (it stores `3.0` as `3`): convert on
    read;
  - a VIRTUAL generated column has no place in a record, so record positions and column positions differ;
  - a WITHOUT ROWID table's record holds the primary key's columns first (`buildWithoutRowidTable`);
  - automatic indexes have no SQL in `sqlite_schema`; `TableSchema.keys` lists them in `sqlite_autoindex_T_n` order;
  - the catalog does not yet give `IndexSchema`s for automatic indexes: add that with the planner;
  - window functions compile (`WindowSpec`) but do not run yet; `OVER w` is resolved by name at compile time;
  - result column names should come from the statement's own text, as in SQLite, not from `SqlWriter`.
