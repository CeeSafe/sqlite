# sqlite

A SQLite engine in CeeSafe: the on-disk file format, read and written byte-compatibly with the stock library,
and (in progress) SQL on top of it. No C, no `unsafe`, no dependency on `libsqlite3`. It is a port of the
pure-managed C# engine `CosmoNova.Engine.Sqlite` from CosmoStack.

## Status

| Part | C# source | Here | State |
|---|---|---|---|
| Varints, records, values | `Engine/Format` | `varint.cee`, `record.cee`, `value.cee` | done |
| Database header, pager, freelist count | `Storage/DatabaseHeader`, `Pager`, `FreelistReader` | `header.cee`, `pager.cee` | done (no WAL overlay yet) |
| Table b-tree reader | `Btree/BTreeReader` | `btree.cee` | done |
| Index b-tree reader | `Btree/IndexBTreeReader` | `index.cee` | done, except the integer batch-count fast paths, which belong with the executor |
| Value ordering, collations | `Exec/ValueComparer` | `compare.cee` | done |
| Schema and tables by name | `SqliteDatabaseReader` | `reader.cee` | done |
| Tokenizer, parser, AST | `Engine/Sql` | `tokenizer.cee`, `parser.cee`, `ast.cee` | done |
| SQL writer | `Sql/SqlWriter` | `sqlwriter.cee` | expressions only, by design (see below) |
| Schema catalog, affinity | `Engine/Schema`, `Exec/Affinity` | `schema.cee` | done |
| Database writer, b-tree builder | `Storage/DatabaseWriter`, `BTreeBuilder`, `PageStore` | `writer.cee`, `builder.cee` | done: files pass `PRAGMA integrity_check` in `sqlite3` |
| Rollback journal, commit of a page image | `Storage/JournaledFile` | `journal.cee` | done: either engine undoes the other's interrupted commit |
| Writable pager, b-tree mutators | `Storage/WritablePager`, `BTreeMutator`, `IndexMutator`, `IndexRebuilder` | `pagerw.cee`, `mutate.cee` | done |
| Numbers as text, text as numbers | `Exec/SqlValueOps` | `numeric.cee` | done: SQLite's own conversion routines, ported |
| Value operations, comparison affinity | `Exec/SqlValueOps`, `ValueComparer` | `valueops.cee`, `compare.cee` | done |
| Expressions: compiler and evaluator | `Exec/ExpressionEvaluator`, `Binding`, `ParameterBinder` | `expr.cee`, `compile.cee` | done |
| Scalar functions, aggregates | `Exec/Functions`, `LikeMatcher` | `functions.cee`, `aggregate.cee`, `libm.cee` | done, with every math function (`libm.cee`: msun and double-double, a last-bit difference from macOS's libm on some arguments) |
| Date and time functions | `Exec/Functions` (date/time part) | `datetime.cee` | done: a port of SQLite's date.c; 'localtime' and 'utc' are an error where they need the time zone, which CeeSafe lacks |
| printf() and format() | `Exec/Functions` (`Printf`) | `printf.cee` | done: a port of SQLite's `sqlite3_str_vappendf`, every conversion and flag of the SQL path |
| JSON functions | `Exec/Json`, `Functions` (JSON1) | `json.cee` | done: SQLite 3.53.4's text JSON functions, `->`, `->>`, `json_group_array` and `json_group_object`, JSON5 input, JSONB blobs as input; the `jsonb_*` functions and the table-valued `json_each` and `json_tree` are not ported and are "no such function" |
| SELECT: joins, subqueries, views, CTEs, grouping, compounds | `Exec/QueryExecutor` | `select.cee`, `run.cee` | done but table functions; RIGHT and FULL joins, rowid and index seeks done |
| Planner: index seeks | `Exec/QueryPlanner` | `plan.cee` | `=`, IS and range terms on the leading columns of plain indexes, for SELECT, UPDATE and DELETE; IN lists, partial and expression indexes, and covering scans next |
| Window functions | `Exec/WindowEvaluator` | `window.cee` | done: every built-in window function, aggregates over frames, ROWS/RANGE/GROUPS, EXCLUDE, named windows |
| INSERT, UPDATE, DELETE | `Exec/QueryExecutor` (DML), `InMemoryDatabase` | `dml.cee` | done: constraints, conflict actions, RETURNING, AUTOINCREMENT, upserts, triggers, foreign keys, UPDATE … FROM; WITHOUT ROWID tables read and written |
| CREATE and DROP of tables, indexes and views | `Exec/QueryExecutor` (DDL) | `ddl.cee` | done |
| Triggers | `Exec/QueryExecutor` (`FireTriggers`) | `triggers.cee` | BEFORE and AFTER on tables, INSTEAD OF on views done |
| ALTER TABLE | `Exec/QueryExecutor` (`ExecuteAlterTable`) | `alter.cee` | RENAME TO, RENAME COLUMN, ADD COLUMN, DROP COLUMN done; renames that views or triggers refer to next |
| PRAGMAs, pragma_* table functions | `Exec/QueryExecutor` (`ExecutePragma`) | `pragma.cee`, `integrity.cee` | schema pragmas, header fields, integrity_check and quick_check done |
| Connection, transactions | `SqliteConnection`, `EngineGlue` | `session.cee` | done: statements commit on their own outside BEGIN, and a failed statement undoes only itself inside it |
| WAL | `Storage/Wal*`, `Shm*` | | until then a database with a non-empty `-wal` file is refused |
| Connection, command, pool | `SqliteConnection`, `SqliteCommand`, `SqliteConnectionPool` | | |
| PostgreSQL wire front end, daemon, CLI | `CosmoNova.Engine.Sqlite.PgWire`, `CosmoSqliteD`, `.Cli` | | not started |

## Differences from the C# engine

The port fixes what was wrong in the source instead of copying it. Each item has a test.

- **Damaged files.** The C# trusts every offset, length and page pointer it reads, so a damaged file gives an
  `IndexOutOfRangeException`, unbounded recursion on a cycle of pages, or an endless loop on a cyclic freelist.
  Here they are all checked and reported as `SqliteError.Corrupt` (`truncatedDatabaseIsCorruptNotACrash`,
  `varintTruncatedIsCorrupt`).
- **Short overflow chains.** When an overflow chain ended before its payload, the C# returned the payload padded
  with zeros. Here that is `Corrupt`.
- **PRAGMA integrity_check.** The C# answered "ok" to `integrity_check` and `quick_check` whatever the file held.
  Here they run SQLite's checks (`integrity.cee`): the b-tree walk of sqlite3BtreeIntegrityCheck (page
  references, cell bounds and overlaps, fragmentation, rowid order, child depths, overflow chains, the freelist,
  unused pages, the header's page count) and then the row checks of pragma.c's program (NOT NULL, column types,
  CHECK, and, for integrity_check, every row's entry in every index, extra entries, UNIQUE, and WITHOUT ROWID key
  order), with SQLite's messages, order and error limit, the `N` and table-name arguments included
  (`damagedTreePages`, `damagedChainsAndHeader`, `indexesThatDisagreeWithTheirTables`,
  `rowsThatBreakTheirTablesDefinition`, `tablesComeInSqlitesHashOrder`).
- **Integer against real.** The C# compares an integer with a real by converting the integer to a double, so
  `9007199254740993` equals `9007199254740992.0`. SQLite compares them exactly, and so does this
  (`valuesCompareAsSqliteOrdersThem`).
- **Text order.** The C# orders text by UTF-16 code units; SQLite's BINARY collation orders by UTF-8 bytes, which
  differs for characters above U+FFFF. This compares bytes.
- **Names.** The C# matches table and index names with .NET's ordinal-ignore-case, which folds non-ASCII letters;
  SQLite folds ASCII only, and so does this.
- **Seeks in DESC and NOCASE indexes.** The C# equality seek compared with BINARY and assumed ascending order, so
  on an index whose first column is `DESC` it stopped at the first entry, and on a NOCASE index it missed the other
  case. One cursor now serves every seek in the index's own order (`descendingIndexColumns`, `noCaseIndex`).
- **Counting with exclusive bounds.** The C# range count treated a child page as wholly inside the range when the
  entry bounding it was equal to an exclusive bound, so `n > 7` could count entries with `n = 7` when 7 had
  duplicates across pages. The bounding entry must now satisfy the bound as written (`countsRanges`).
- **Header checks.** A reserved-space byte that leaves fewer than 480 usable bytes, and an unknown text encoding,
  are refused; the in-header page count is used only when the header says it is valid.
- **Write-ahead logs.** Until the WAL reader is ported, opening a database with a non-empty `-wal` file is an
  error rather than a silent read of the main file alone.

- **Tokens.** The C# classifies characters with .NET's Unicode tables: digits of other scripts start numbers that
  then fail to parse, and `$` ends an identifier. The tokenizer here uses SQLite's classes. Malformed tokens (a
  blob literal that is not pairs of hex digits, `0x` alone, `123abc`, a bare `:`) are errors where they stand; the
  C# passed them on (`identifiersFollowSqlite`, `refusesMalformedTokens`).
- **Operator precedence.** In the C#, `->` and `->>` bind like `&`, and COLLATE like `||`, so `a + j -> 'k'` and
  `a || b COLLATE NOCASE` group wrongly. Here both follow SQLite (`precedenceIsSqlites`).
- **Grammar the C# refused.** `a = NOT b`, `x NOT NULL`, subqueries and INSERT sources that start with VALUES or
  WITH, string-literal aliases, `OVER (w ORDER BY …)`, and empty statements between semicolons now parse.
- **Grammar the C# accepted wrongly.** `INSERT OR <any word>`, `RAISE(<any word>)`, any statement in a trigger's
  body, and column definitions after a table constraint are now syntax errors, as in SQLite.
- **Deep expressions.** An expression chained or nested past SQLite's limits is an error; in the C# it overflowed
  the stack (`deepExpressionsAreRefusedNotCrashed`).
- **Named windows.** `OVER w` stays a name in the tree, to be looked up in the WINDOW clause when the query runs.
  The C# substituted the definition while parsing, and only in parts of the select list.
- **Stored definitions.** The C# writes a view's, trigger's or table's definition to `sqlite_schema` by rendering
  the parsed statement, and its renderer drops what it does not know (WINDOW, NULLS FIRST, upserts, RETURNING,
  NATURAL, table functions), so a definition could come back from the file meaning something else. The port will
  store the statement's own text, as SQLite does; `sqlwriter.cee` renders expressions only.

- **Column definitions.** The C# reads them from token text re-split on spaces, which loses what the tokens were.
  `DEFAULT -1` was recorded as `-`; a column named `"unique"` or a constraint named like a keyword was read as that
  constraint; a quoted key column with a space in its name broke apart; a declared type came back as
  `VARCHAR ( 10 )`. The catalog here reads typed tokens (`catalogReadsTables`).
- **Index collations.** The C# gives every index column the BINARY collation. An index column now takes its own
  COLLATE, or else its table column's, as in SQLite, so an index on a NOCASE column is searched in its real order
  (`catalogReadsIndexes`).
- **Partial and expression indexes.** The C# records them as plain indexes on their named columns. Here they keep
  their WHERE and their expressions, and `coversEveryRow()` says whether an index may stand in for its table.
- **One unreadable definition.** In the C#, one entry of `sqlite_schema` that does not parse (a virtual table)
  makes the whole database unreadable. Here that table alone is listed as unsupported
  (`oneUnreadableTableDoesNotHideTheOthers`).

- **Index order on disk.** The C# writer sorts every index BINARY and ascending. An index on a NOCASE column, an
  index column with COLLATE, and the automatic index of `PRIMARY KEY (a DESC)` or `UNIQUE (a DESC)` were therefore
  written in an order SQLite does not expect, which it reports as corruption. The writer here sorts each index in
  its own order (`writesKeysInTheirOwnOrder`).
- **Indexes on WITHOUT ROWID tables.** SQLite ends such an index's entries with the primary key columns the index
  does not already have; the C# appended them all (`writesWithoutRowidTables`).
- **Orphaned overflow pages.** When the C# held an index's last record back as a divider, it had already written
  that record's overflow pages for a leaf cell it then discarded. The builder here chooses a leaf's records before
  it builds a cell.
- **What a record holds.** The rowid's alias is stored as NULL and indexed by the rowid, and a VIRTUAL generated
  column is not stored, whatever the caller put in the row (`generatedColumnsAndSuppliedEntries`).
- **Damage refused.** Two rows with one rowid, or with one key in a UNIQUE or PRIMARY KEY index, are a
  `Constraint` error; the C# wrote the file. A partial or expression index without its entries is refused; the C#
  wrote it empty beside a table with rows (`refusesWhatWouldDamageTheFile`).
- **Replacing a file.** The C# deleted the old database and then moved the new one into place. Here it is one
  atomic rename followed by a sync of the directory, and a database with a rollback journal or a write-ahead log
  beside it is not replaced, since SQLite would apply those to the new file.
- **Header fields.** The change counter, schema cookie, user version and application id are passed in, so a
  rewrite can carry them over; the C# reset them on every rewrite.

- **The journal's format.** The C# writes a journal format of its own under the name SQLite uses for its
  rollback journal. After a crash in the middle of a commit, the stock library finds a journal it cannot read,
  sets it aside and opens a database with half a commit in it. The journal here is SQLite's, checksums included,
  so `sqlite3` undoes this engine's interrupted commit and this engine undoes `sqlite3`'s
  (`sqliteUndoesThisEnginesInterruptedCommit`, `thisEngineUndoesSqlitesInterruptedCommit`).
- **A journal cut short.** The C# trusts the entry count in its journal's header, so a journal cut off while
  being written, before the database was touched, makes the database impossible to open. Playback here stops at
  the first record that is short or fails its checksum (`aJournalCutShortIsHarmless`).
- **Durability of the journal itself.** The directory is synced when the journal is made and when it is removed;
  the journal is written a record at a time rather than held in memory.
- **Reading beside a hot journal.** A database with a journal is not read as it is: the interrupted commit is
  undone first.

- **Deleting every row of a small table.** A C# batch that emptied a table whose root is a leaf wrote nothing,
  leaving the rows in the file pointing at overflow pages it had freed (`deletingEveryRowOfASmallTable`).
- **Deletes that empty subtrees.** When a delete left an interior page with one child, the C# stopped with "not
  yet supported" after it had already freed the emptied leaf. Here that page's siblings share their children out
  again, so every leaf stays at one depth whatever is deleted (`deletesThatEmptyWholeSubtrees`,
  `deletesFromTheMiddleAndTheEnds`).
- **sqlite_schema.** The C# mutator read every page as if its b-tree header were at offset 0, which is wrong for
  page 1, so it could not change `sqlite_schema` in place (`changesSqliteSchemaOnPageOne`).
- **Index pages that split.** The C# split an index page by the number of its cells, so a page of large entries
  and small ones could be split into a half that did not fit. Pages split where their bytes divide evenly, and
  entries are compared in the index's own order and decoded in the database's encoding
  (`insertsIntoAnIndexSplitItsPages`, `keepsIndexesInStepWithTheirTable`).
- **Rebuilding an index.** The C# had a second copy of the index builder for this, which sized interior pages as if
  index cells were as small as table cells. The one builder serves both here.
- **The freelist.** A freed page becomes a leaf of the first trunk while it has room, rather than a trunk of its
  own; freelist pointers are checked; the page of SQLite's lock bytes is never allocated.
- **Files the mutators cannot keep sound.** A database with pointer-map pages (auto-vacuum) or in WAL mode is
  refused for writing; the C# wrote it, leaving the pointer map or the log out of step.
- **Rolling back.** A transaction's changes can be forgotten; the C# pager could only be thrown away.

- **Where changes live.** The C# engine loads a whole table into memory the first time a statement changes it, and
  writes whole tables back at commit, so changing one row of a large table costs the table. Here changes go to the
  pages they touch, in the transaction's pager; commit journals and writes those pages only. Queries stream rows
  from cursors instead of materialising tables.
- **A failed statement inside BEGIN.** It undoes its own changes and no others, as in SQLite
  (`transactionsUndoWhatTheyShould`).
- **Index upkeep during a statement.** An index that cannot take a removal in place is rebuilt when the statement
  ends, from the rows as they then are; rebuilding it mid-statement would read rows not yet changed
  (`manyRowsAndIndexes`).

- **Definitions as written.** The catalog keeps a column's type, default and CHECK as their text in the statement
  (`VARCHAR ( 10 )`, `1 + 2`), as SQLite does; `PRAGMA table_info` and CHECK failure messages show them so. The
  C# rebuilt the text from tokens (`VARCHAR ( 10 )` became `VARCHAR(10)`, `DEFAULT -1` became `-`).
- **Pragmas.** `table_info` leaves out generated columns; `index_list` gives SQLite's order, origins and partial
  flags; `user_version` and `application_id` live in the database header (`pragmasDescribeTheSchema`).
- **ALTER TABLE.** Stored statements are edited where the names stand, as SQLite does, so definitions stay as
  written; RENAME TO renames automatic indexes and index ON clauses, and other tables' REFERENCES only while foreign
  keys are on; RENAME COLUMN follows into REFERENCES t(column) clauses; ADD COLUMN goes after the last column
  definition and refuses what SQLite refuses, with its messages (`alterTableRewritesDefinitions`). The C# stored
  its renderer's version of the whole statement.
- **Date and time values.** The C# read time values through .NET's `DateTime`: no year 0 or earlier, no
  `+HH:MM`/`Z` zones, at most three fraction digits, no time without a date, and a bare number was always a Julian
  day. The port of SQLite's date.c reads them all as SQLite does, numbers included (`dateTimeValues`).
- **Modifiers.** The C# applied 'unixepoch' and 'auto' wherever they stood, made 'floor' re-run month arithmetic,
  treated 'utc' and 'localtime' as nothing, and lacked 'julianday', '±HH:MM', '±YYYY-MM-DD', and 'subsec' outside
  datetime(). Here they apply in order with SQLite's rules (only right after the value for 'unixepoch', 'julianday',
  'auto'), and 'localtime'/'utc' are an error where they would need the time zone (`dateTimeModifiers`).
- **strftime().** An unknown specifier made the C# throw; SQLite and this give NULL. %J, %f, %s with 'subsec', %G,
  %g, %V, %u, %k, %l, %P and %e follow SQLite's printf (`strftimeSpecifiers`).
- **'now'.** The C# read the clock at each call; here it is the statement's time, the same in every call.
- **unixepoch() and timediff().** unixepoch() truncates toward zero and gives a real with 'subsec'; timediff() walks
  months as SQLite does (`timediffAndErrors`).

- **Foreign keys.** Enforced while `PRAGMA foreign_keys` is on: child rows need a parent, and CASCADE, SET NULL,
  SET DEFAULT, RESTRICT and NO ACTION apply to the children of a changed or deleted parent, through SQL so the
  children's triggers fire (`foreignKeysFollowSqlite`). Deferred keys are checked at once, and NO ACTION after each
  row rather than at the end of the statement.
- **printf() and format().** The C# had a subset of C's printf on .NET formatting. This is a port of SQLite's own
  `sqlite3_str_vappendf` (`printfIntegers`, `printfReals`, `printfRealExtremes`, `printfStrings`,
  `printfCharacters`, `printfQuoting`, `printfFlagsAndParsing`). What the C# got wrong:
  - reals were written by .NET: `1E+20` for `%g`, `∞` for infinity, its own rounding, and no 16-digit limit; here
    they go through `sqlite3FpDecode` as in SQLite (`Inf`, `%!` with 20 digits, `9e999` for infinity with `0`);
  - `%d` of a real or of text went through a double, so large integers lost digits; `%u` of a negative number
    printed a minus sign instead of the unsigned 64-bit value; `%x` and `%o` ignored the precision;
  - the `#`, `!`, `,` and space flags and `*` widths and precisions were missing, and so were `%p`, `%r`, `%z` and
    `%n`; an unknown conversion threw, where SQLite ends the output there; a lone `%` at the end was dropped;
  - `%s` precision counted UTF-16 units instead of bytes (or characters with `!`); `%c` of `''` or NULL threw
    instead of giving a NUL; `%q` and `%w` of NULL gave `''` instead of `(NULL)`;
  - `printf(NULL)`, `printf()` and an empty result were `''`; in SQLite they are NULL.

  Where this still differs from the stock library: text here is UTF-8, so where SQLite's result would not be (a
  `%.Ns` or `%.Nq` precision that cuts a character in two, a blob argument that is not UTF-8) each stray byte
  becomes U+FFFD. Results longer than SQLite's default limit of 10^9 bytes are "string or blob too big"; the macOS
  `sqlite3` shell the tests use is built with a limit of 2^31 - 1, so the tests stay at sizes where both agree.

- **Automatic index names of WITHOUT ROWID tables.** The primary key keeps its number in `sqlite_autoindex_T_N`
  though it has no index of its own (`t(a UNIQUE, b PRIMARY KEY) WITHOUT ROWID` has `sqlite_autoindex_t_1` and no
  `_2`). The C# skipped it, so the next UNIQUE got the primary key's number and sqlite3 called the file malformed
  (`withoutRowidTablesChangeLikeSqlite`).
- **WITHOUT ROWID tables** are read and written in place: rows are named by their primary key, a table index holds
  the key columns it lacks after its own, as SQLite does, and the key's columns are NOT NULL. The C# loaded them
  into memory.
- **JSON is SQLite's.** The C# JSON functions were a small JSON library of their own; `json.cee` is a port of
  SQLite's `json.c`, which goes through JSONB as SQLite does (`tests/json_tests.cee`):
  - malformed JSON is the "malformed JSON" error, where the C# returned NULL (and `json_valid(NULL)` is NULL, not
    0) (`jsonRejectsMalformedInput`);
  - a number keeps its spelling (`json('1.0')` is `1.0`; the C# wrote `1`), and an integer past 64 bits is not
    turned into a rounded real in the text (`jsonParsesAndMinifies`);
  - JSON5 input (comments, unquoted labels, single quotes, hexadecimal, `Infinity`, `NaN`, trailing commas,
    `\x` and `\v` escapes) is accepted and written as RFC 8259 JSON; the C# rejected it (`jsonAcceptsJson5`);
  - paths: `."quoted"` labels with escapes, `[#]` and `[#-N]`, and a "bad JSON path" error for a malformed path,
    which the C# ignored; `->` and `->>` take a negative integer as `[#-N]`, where the C# made `$[-1]`
    (`jsonFollowsPaths`);
  - json_set() and json_insert() create the objects and arrays along a missing path, and append to an array only
    at `[#]` or its length; the C# did nothing for a missing parent and appended for any index past the end
    (`jsonEditsValues`);
  - argument errors are SQLite's: an odd count for json_set(), json_insert() and json_replace(), an even count for
    json_object(), a label that is not text, and a blob that is not JSONB ("JSON cannot hold BLOB values"); the C#
    dropped the extra argument and stored a blob as a string (`jsonChecksArgumentCounts`);
  - the subtype rule: text a JSON function returns nests as JSON in another JSON function, so
    `json_array(json('[1]'))` is `[[1]]`; the C# made it `["[1]"]` (`jsonNestsJsonResultsBySubtype`);
  - json_error_position() reports the character where SQLite's parser stops, and json_valid() takes SQLite's
    FLAGS argument; json_pretty() and json_array_insert() exist.
- **Math functions** (`math_tests.cee`). The C# called .NET's `Math` with SQLite's names, and differed:
  - an infinite result was NULL; SQLite returns it: `exp(710)`, `pow(0, -1)` and `atanh(1)` are `Inf`;
  - arguments went through the numeric prefix of text, so `sin('1abc')` and `floor(x'33')` were numbers; SQLite
    takes text that is entirely a number and makes anything else (other text, blobs) NULL, and so does
    `sqrt()`, `mod()`, `floor()`, `ceil()` and `trunc()` here;
  - `log(B, X)` with a base in (0, 1] is NULL in SQLite (logFunc requires `ln(B) > 0`); the C# computed it, and
    took X's prefix as SQLite does only by accident;
  - `degrees(x)` was `x * 180 / pi`, rounded twice; SQLite's is `x * (180 / pi)`;
  - `asinh`, `acosh` and `atanh` were the textbook formulas, which lose every digit for large negative or small
    arguments (`asinh(-1e10)` was `ln(0)`, NULL); here they are msun's.

## Known differences from SQLite in the math functions

The `sqlite3` shell calls the platform's libm (macOS's here), and prints reals with 17 significant digits, so a
difference in the last bit shows. CeeSafe has no math library and the package may not call C, so `libm.cee`
computes them: `exp`, `ln`, `log`, `log10`, `log2`, `pow`, `sinh`, `cosh`, `tanh`, `asin`, `acos` and `atan2` in
double-double arithmetic rounded once (correctly rounded but for arguments within ~2^-100 of a tie), the
inverse hyperbolic functions by msun's formulas over those, and `sin`, `cos`, `tan` and `atan` as FreeBSD's msun
(fdlibm) computes them, with its exact reduction of large arguments (`sin(1e22)` matches). macOS's libm is
neither msun nor correctly rounded for the trigonometric functions, so on 3000 random arguments a call differs in
the last bit (never more than 2 units) this often:

| Function | Differs | Function | Differs |
|---|---|---|---|
| `exp`, `pow`, `ln`, `log10`, `log2` | 0–0.2% | `sin`, `cos` | 4–5% |
| `sinh`, `cosh`, `tanh` | 0.2–0.3% | `asin` | 5% |
| `atan2` | 1–2% | `acos` | 15% |
| `acosh`, `asinh` of large arguments | 0–0.2% | `atan` | 5% |
| `asinh` in (-1, 1) | 7% | `tan` | 40% |
| `atanh` | 10% | `sqrt`, `degrees`, `radians`, `mod` | 0 |

Where macOS is not correctly rounded, correct rounding would not match it either (its `tan` differs from the
correctly rounded value on 42% of arguments, `asin(0.5)` and `atan(0.5)` are a unit off); matching it bit for bit
would take Apple's algorithms, which are not published. The tests use arguments on which the two agree.

## Known differences from SQLite in the JSON functions

- **A scalar subquery drops the JSON subtype.** `json_array((SELECT json('[1]')))` is `[[1]]` in SQLite and
  `["[1]"]` here. This engine's values carry no subtype; JSON-function arguments are evaluated by
  `evaluateWithSubtype` (`json.cee`), which sees through CASE, coalesce, ifnull, iif, nullif, likely, unlikely,
  the scalar min and max, unary `+`, CAST, COLLATE, `->` and the JSON aggregates, but not into a subquery.
- **Unpaired surrogates.** SQLite decodes `"\ud800"` to the bytes ED A0 80, which are not UTF-8. Text values here
  are valid UTF-8, so each such byte becomes U+FFFD.
- **Window functions.** json_group_array() and json_group_object() run as window functions, but their arguments
  lose the JSON subtype on the way through the window, so a JSON argument is quoted as text.
- **Nesting depth.** The limit is 3.53.4's 1000 levels; the `sqlite3` shell the tests run (3.54.0 on macOS) was
  built with 800, so the tests stay on depths where the two agree.

- **Window functions** follow SQLite's rules where the C# made its own (`windowFunctionsMatchSqlite`,
  `windowFunctionsInContext`): rows come out in the first window's order when there is no ORDER BY; a negative
  lag()/lead() offset looks the other way; RANGE offsets need one numeric ORDER BY term and compare in its
  direction, with NULL and non-numeric keys framed by their peers; frame offsets are checked with SQLite's
  messages; DISTINCT and FILTER on non-aggregates are refused as in SQLite; window arguments in an aggregate query
  may hold aggregates (`sum(sum(v)) OVER (…)`). Frames that do not start at the partition's start are summed
  afresh for each row (no inverse step yet), so a sliding frame costs its width per row.

- **RIGHT and FULL joins** run in the nested loops: each right source's rows that matched nothing come out after
  the loops, with the earlier sources NULL; a column USING or NATURAL shares is `coalesce(left, right)` in
  unqualified names, `*` and the left table's `t.*`, as in SQLite (`rightAndFullJoinsMatchSqlite`). The C# refused
  them.

- **Result column names** are SQLite's (`resultColumnNamesMatchSqlite`): an expression's text as written, comments
  and spacing kept; a column's name as its table declares it, whatever case the query uses; the INTEGER PRIMARY
  KEY's name for `rowid`; `columnN` for VALUES. The C# wrote the expression again from its tree (`abc + 1` for
  `abc  +  1`) and used the name as the query spelled it.

- **Index seeks** use an index only where it finds every row the comparison can be true for: the index column's
  collation must be the comparison's, and the comparison's affinity must leave the stored values unchanged; the key
  is converted as the comparison converts it (`indexSeeksGiveTheSameRows`, `writesThroughIndexSeeks`). WHERE
  still runs on every row the index gives.

- **CREATE TABLE … AS SELECT** writes its statement as SQLite's createTableStmt does: columns typed `INT`,
  `TEXT`, `NUM`, `REAL` or nothing by their affinities, repeated names made unique with `:N`, names quoted where
  SQLite quotes them, and a column a line once the statement is long (`createTableAsSelectLikeSqlite`). The C#
  refused it.

- **DROP COLUMN** follows SQLite: the definition leaves the statement with its own constraints, a PRIMARY KEY or
  UNIQUE column or the last column is refused, a CHECK, generated column or index still naming it is "error in
  table/index X after drop column", and every row loses the value (`dropColumnLikeSqlite`).
- **Index cells take at least 4 bytes**, as SQLite counts them: a WITHOUT ROWID table of small keys made 3-byte
  cells, which sqlite3 calls out of range (`tinyIndexCellsTakeFourBytes`).

- **INSTEAD OF triggers** make views writable as in SQLite (`insteadOfTriggersOnViews`): the rows are the view's
  rows WHERE selects (joined with FROM for UPDATE … FROM), UPDATE OF counts, RETURNING gives NEW (OLD for DELETE),
  changes() stays 0, and DROP VIEW drops the view's triggers. A trigger body's changes count in
  total_changes(), as in SQLite; this engine had left them out.

## Known differences from SQLite in PRAGMA integrity_check

The report matches the `sqlite3` shell's row for row on the tests' damaged files, with these exceptions:

- **Reading through damage.** After the b-tree check, SQLite reads every row with its ordinary cursors, which
  follow a damaged page as far as they can: a cell pointer into the page header is read as a cell of whatever
  bytes are there, and the rows that come out of it are then checked against the indexes. This engine's cursors
  refuse such a page (`Corrupt`), and the report ends with "database disk image is malformed", which is also how
  SQLite ends when its cursor gives up (the shell then prints that as an error after the rows). The b-tree report
  that comes first is the same (`sameTreeReport` in `tests/integrity_tests.cee`). A row whose overflow chain is
  broken is read as SQLite reads it: its fields in the page are checked, and only a check that needs a field on
  the missing pages ends the report.
- **The order of tables.** SQLite checks tables in the order of its schema hash table, which depends on how
  many buckets its allocator rounds the table's array up to; `sqliteHashOrder` uses what macOS's allocator gives
  (16 buckets for the first 5 to 32 tables). With glibc the shell may list tables with errors in another order.
- **Index order.** Among a table's automatic indexes, one made for a constraint with `ON CONFLICT REPLACE` comes
  last in SQLite's list; here it keeps its place, which matters only for the order of messages.
- **Details not modelled.** "index X stores an imprecise floating-point value" (SQLite's near match of a real
  computed by an index expression) is reported as a missing row; a VIRTUAL generated column's own reads of the
  record are not counted when deciding which column types SQLite re-reads (see `HeaderCache`); a header page
  count larger than the file is an error from the pragma here, and from every statement in SQLite;
  `PRAGMA ignore_check_constraints` does not exist here, so CHECK constraints are always checked.

## Known gaps (inherited from the C# engine, refused by name rather than misparsed)

`CREATE VIRTUAL TABLE`, `EXPLAIN`, parenthesized joins
in FROM, aliases on the target of INSERT, UPDATE and DELETE, and `ORDER BY` inside an aggregate's arguments.
`ON CONFLICT` clauses on column and table constraints are read and not applied, and collations other than
BINARY, NOCASE and RTRIM are refused.
RETURNING's column names are written again from the expression's tree, not taken from the statement's text.

## Limits

- **Local time.** 'localtime', and 'utc' on a value not known to be UTC, are an error ("local time unavailable"):
  CeeSafe's library has no time zone (CEESAFE_FINDINGS.md). 'now' and date functions with it are also not refused
  in CHECK constraints, index expressions and generated columns, as SQLite refuses them.

- **One process at a time.** The engine does not take SQLite's file locks, which CeeSafe's library does not
  offer, so it must not have a database open while another process writes it. (The C# engine has the same
  limit.)

## Tests

`ceesafec test` needs the `sqlite3` shell on the path: fixtures are made with it, and answers are compared with
what it prints.
