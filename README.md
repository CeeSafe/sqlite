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
| Scalar functions, aggregates | `Exec/Functions`, `LikeMatcher` | `functions.cee`, `aggregate.cee` | core functions done; JSON and transcendental math next |
| Date and time functions | `Exec/Functions` (date/time part) | `datetime.cee` | done: a port of SQLite's date.c; 'localtime' and 'utc' are an error where they need the time zone, which CeeSafe lacks |
| printf() and format() | `Exec/Functions` (`Printf`) | `printf.cee` | done: a port of SQLite's `sqlite3_str_vappendf`, every conversion and flag of the SQL path |
| SELECT: joins, subqueries, views, CTEs, grouping, compounds | `Exec/QueryExecutor` | `select.cee`, `run.cee` | done but RIGHT/FULL joins, window functions, table functions, index seeks (rowid seeks done) |
| INSERT, UPDATE, DELETE | `Exec/QueryExecutor` (DML), `InMemoryDatabase` | `dml.cee` | done: constraints, conflict actions, RETURNING, AUTOINCREMENT, upserts, triggers, foreign keys, UPDATE … FROM; WITHOUT ROWID tables read and written |
| CREATE and DROP of tables, indexes and views | `Exec/QueryExecutor` (DDL) | `ddl.cee` | done |
| Triggers | `Exec/QueryExecutor` (`FireTriggers`) | `triggers.cee` | BEFORE and AFTER on tables done; INSTEAD OF on views next |
| ALTER TABLE | `Exec/QueryExecutor` (`ExecuteAlterTable`) | `alter.cee` | RENAME TO, RENAME COLUMN, ADD COLUMN done; DROP COLUMN and renames that views or triggers refer to next |
| PRAGMAs, pragma_* table functions | `Exec/QueryExecutor` (`ExecutePragma`) | `pragma.cee` | schema pragmas and header fields done; integrity_check next |
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

## Known gaps (inherited from the C# engine, refused by name rather than misparsed)

`CREATE TABLE … AS SELECT`, `CREATE VIRTUAL TABLE`, `ALTER TABLE … DROP COLUMN`, `EXPLAIN`, parenthesized joins
in FROM, aliases on the target of INSERT, UPDATE and DELETE, and `ORDER BY` inside an aggregate's arguments.
`ON CONFLICT` clauses on column and table constraints are read and not applied, and collations other than
BINARY, NOCASE and RTRIM are refused.

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
