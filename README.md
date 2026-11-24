# sqlite

A SQLite engine in CeeSafe: the on-disk file format, read and written byte-compatibly with the stock library,
and (in progress) SQL on top of it. No C, no `unsafe`, no dependency on `libsqlite3`. It is a port of the
pure-managed C# engine `CosmoNova.Engine.Sqlite` from CosmoStack.

## Status

| Part | C# source | Here | State |
|---|---|---|---|
| Varints, records, values | `Engine/Format` | `varint.cee`, `record.cee`, `value.cee` | done: TEXT keeps any bytes (`ByteString`), as SQLite's does; a UTF-16 database's text is written, ordered and seen as bytes in its encoding (`textenc.cee`) |
| Database header, pager, freelist count | `Storage/DatabaseHeader`, `Pager`, `FreelistReader` | `header.cee`, `pager.cee` | done, reading through a write-ahead log |
| Table b-tree reader | `Btree/BTreeReader` | `btree.cee` | done |
| Index b-tree reader | `Btree/IndexBTreeReader` | `index.cee` | done, except the integer batch-count fast paths, which belong with the executor |
| Value ordering, collations | `Exec/ValueComparer` | `compare.cee` | done |
| Schema and tables by name | `SqliteDatabaseReader` | `reader.cee` | done |
| Tokenizer, parser, AST | `Engine/Sql` | `tokenizer.cee`, `parser.cee`, `ast.cee` | done: SQL text of any bytes (`sqltext.cee`), as SQLite takes it |
| SQL writer | `Sql/SqlWriter` | `sqlwriter.cee` | expressions only, by design (see below) |
| Schema catalog, affinity | `Engine/Schema`, `Exec/Affinity` | `schema.cee` | done |
| Database writer, b-tree builder | `Storage/DatabaseWriter`, `BTreeBuilder`, `PageStore` | `writer.cee`, `builder.cee` | done: files pass `PRAGMA integrity_check` in `sqlite3` |
| Rollback journal, commit of a page image | `Storage/JournaledFile` | `journal.cee` | done: either engine undoes the other's interrupted commit |
| Writable pager, b-tree mutators | `Storage/WritablePager`, `BTreeMutator`, `IndexMutator`, `IndexRebuilder` | `pagerw.cee`, `mutate.cee` | done |
| Numbers as text, text as numbers | `Exec/SqlValueOps` | `numeric.cee` | done: SQLite's own conversion routines, ported |
| Value operations, comparison affinity | `Exec/SqlValueOps`, `ValueComparer` | `valueops.cee`, `compare.cee` | done |
| Expressions: compiler and evaluator | `Exec/ExpressionEvaluator`, `Binding`, `ParameterBinder` | `expr.cee`, `compile.cee` | done |
| Scalar functions, aggregates | `Exec/Functions`, `LikeMatcher` | `functions.cee`, `aggregate.cee` | done, with every math function (the platform's libm, as `sqlite3`) |
| Date and time functions | `Exec/Functions` (date/time part) | `datetime.cee` | done: a port of SQLite's date.c, 'localtime' and 'utc' included |
| printf() and format() | `Exec/Functions` (`Printf`) | `printf.cee` | done: a port of SQLite's `sqlite3_str_vappendf`, every conversion and flag of the SQL path |
| JSON functions | `Exec/Json`, `Functions` (JSON1) | `json.cee`, `json_each.cee` | done: SQLite 3.53.4's JSON functions, `->`, `->>`, the aggregates, JSON5 input, JSONB blobs as input, the `jsonb_*` functions (their JSONB byte for byte as sqlite3's) and the table-valued `json_each`, `json_tree`, `jsonb_each` and `jsonb_tree` (every column, `id` as SQLite's JSONB offsets, arguments from earlier FROM items) |
| SELECT: joins, subqueries, views, CTEs, grouping, compounds | `Exec/QueryExecutor` | `select.cee`, `run.cee` | done, with RIGHT and FULL joins, rowid and index seeks, and the table-valued functions (`pragma_*`, `json_each`, `json_tree`, `jsonb_each`, `jsonb_tree`) |
| Planner | `Exec/QueryPlanner` | `plan.cee` | done for single-table access: `=`, IS, IN (lists and subqueries) and ranges on plain, partial and expression indexes and on the rowid, for SELECT, UPDATE and DELETE; covering reads and covering scans; ORDER BY from an index or the rowid, forwards or backwards, with LIMIT stopping early; SQLite's costs, from sqlite_stat1 after ANALYZE. Not done: the OR optimization (MULTI-INDEX OR), skip-scans, automatic indexes, join reordering, NULLS FIRST/LAST from an index (they sort) |
| Window functions | `Exec/WindowEvaluator` | `window.cee` | done: every built-in window function, aggregates over frames, ROWS/RANGE/GROUPS, EXCLUDE, named windows |
| INSERT, UPDATE, DELETE | `Exec/QueryExecutor` (DML), `InMemoryDatabase` | `dml.cee` | done: constraints, conflict actions, RETURNING, AUTOINCREMENT, upserts, triggers, foreign keys, UPDATE … FROM; WITHOUT ROWID tables read and written |
| CREATE and DROP of tables, indexes and views | `Exec/QueryExecutor` (DDL) | `ddl.cee` | done |
| Triggers | `Exec/QueryExecutor` (`FireTriggers`) | `triggers.cee` | BEFORE and AFTER on tables, INSTEAD OF on views done |
| ALTER TABLE | `Exec/QueryExecutor` (`ExecuteAlterTable`) | `alter.cee` | RENAME TO, RENAME COLUMN, ADD COLUMN, DROP COLUMN done, with views and triggers following renames |
| PRAGMAs, pragma_* table functions | `Exec/QueryExecutor` (`ExecutePragma`) | `pragma.cee`, `integrity.cee` | schema pragmas, header fields, integrity_check and quick_check done |
| Connection, transactions | `SqliteConnection`, `EngineGlue` | `session.cee` | done: statements commit on their own outside BEGIN, and a failed statement undoes only itself inside it; SAVEPOINT, RELEASE, ROLLBACK TO; OR FAIL and OR ROLLBACK; SQLite's file locks (SHARED, RESERVED, PENDING, EXCLUSIVE), hot journals rolled back, `busy_timeout`, BEGIN IMMEDIATE and EXCLUSIVE, `data_version` |
| VACUUM, ANALYZE, REINDEX | (refused by the C#) | `vacuum.cee`, `analyze.cee` | done, with VACUUM INTO |
| TEMP tables, ATTACH | (refused by the C#) | `session.cee` (databases), `select.cee` (names) | done: TEMP tables, views, indexes and triggers (on any database's tables), ATTACH and DETACH, schema-qualified names, SQLite's search order, `database_list` |
| WAL | `Storage/Wal*`, `Shm*` | `wal.cee`, `walindex.cee`, `pagerw.cee`, `pragma.cee` | done: logs read (either checksum byte order) and written with SQLite's salts and checksums, damaged tails ignored as SQLite ignores them, `journal_mode` WAL and DELETE, `wal_checkpoint` (all four modes, waiting for readers as SQLite's do), `wal_autocheckpoint`; the `-shm` wal-index shared with other connections and sqlite3 as wal.c and os_unix.c share it (header copies, hash tables, read marks, checkpoint information, the `-shm` locks and DMS, recovery), so readers run beside a writer; the last connection to close checkpoints the log and removes it and the `-shm`; a `-shm` that cannot be written mapped read-only or replaced by an index in memory (readonly_shm); POSIX only (see Limits) |
| Connection, command, transaction | `SqliteConnection`, `SqliteCommand`, `SqliteTransaction`, `EngineGlue` | `api.cee`, `params.cee` | done: `Connection` with `execute`, `query`, `scalar`, `executeScript`, `begin`/`commit`/`rollback` and `transaction(work)`; `Connection.openReadOnly` (SQLITE_OPEN_READONLY), and files that can only be read opened for reading; `Params` bound by SQLite's rules; results materialised (see below) |
| Connection pool | `SqliteConnectionPool`, `SharedStore` | `pool.cee` | done: shareable across threads (`Arc<ConnectionPool>`), connections kept apart by the file locks, rolled back on return, a full pool waited for up to the busy timeout; no `:memory:` |
| Scripts | `SqliteScript` | `script.cee` | done: `splitScript`/`splitStatements` end statements where sqlite3_complete does |
| PostgreSQL wire front end, daemon, CLI | `CosmoNova.Engine.Sqlite.PgWire`, `CosmoSqliteD`, `.Cli` | `pgwire/`, `daemon/`, `cli/` (packages of their own) | done: a sqlite3-like shell (prompts at a terminal, list, csv, line and column modes, `.headers`, `.tables`, `.schema`, `.read`, `.bail`, sqlite3's error messages and exit status), and a PostgreSQL protocol 3.0 server (simple and extended query, binary formats, portal suspension, cleartext password or trust) with a pool per database; see "Front ends" |

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
- **Text of any bytes.** The C# holds TEXT as a .NET string, so bytes that are not UTF-8 (`CAST(x'ff' AS TEXT)`,
  a record another program wrote, JSON's `"\ud800"`, which SQLite decodes to ED A0 80, `char(0xd800)`) became
  U+FFFD as soon as they were read. SQLite keeps a text's bytes, and so does this: `SqliteValue.Text` holds a
  `ByteString`. The functions read the bytes by SQLite's rules rather than a strict decoder's: unicode(), LIKE,
  GLOB and unhex() by READ_UTF8 (a byte below 0xC0 is a character of its own, a byte from 0xC0 takes every
  continuation byte after it, and an overlong form or a surrogate reads as U+FFFD, while U+FFFE and U+FFFF are
  characters, as in SQLite 3.54.1, where Apple's sqlite3 3.54.0 reads them as U+FFFD too); length()
  and substr() by 3.54's tag-20260418-01 (a stray continuation byte takes the ones after it); instr() by its own
  stepping; trim() by matching each character of its set as bytes; upper(), lower(), replace(), quote(), `||`,
  group_concat(), printf() and strftime() keep the other bytes as they are; char() writes a surrogate as ED A0 80;
  text in a UTF-16 database is translated as sqlite3VdbeMemTranslate does (a lone surrogate kept as three bytes).
  The tests compare answers byte for byte (`textKeepsItsBytes`, `textFunctionsReadBytesAsSqliteDoes`,
  `textFormatsKeepBytes`, `jsonKeepsSqlitesBytes`, `textFromRecordsIsKept`, `utf16TextIsTranslatedAsSqliteDoes`).
- **SQL text of any bytes.** The C# took SQL as a .NET string, so a statement, the names and definitions in
  `sqlite_schema` and every error message were UTF-16, and bytes that are not UTF-8 became U+FFFD. SQLite takes a
  statement as bytes: a string literal keeps every byte (`SELECT hex('<ff>')` is `FF`), a name may hold any byte
  above 0x7F, and names, definitions, result column names and messages carry them on. So does this: the API takes
  `ByteStringView` (`Connection.executeBytes`, `queryBytes`, `scalarBytes`, `executeScriptBytes`,
  `Params.bindBytes`, `Session.queryBytes`; the `StringView` forms are conveniences over them),
  `QueryResult.columns` are `ByteString`s, and `SqliteError.message()` is a `ByteStringView` (`messageText()` for
  a `String`, U+FFFD for bytes that are not UTF-8). Inside, SQL text stays a `String`, in which each byte of a
  sequence that is not UTF-8 stands as one code point of U+10FF80..U+10FFFF (a real one of those is escaped the
  same way, so the mapping is one to one; `src/sqltext.cee`). Names therefore compare as their bytes, folding
  ASCII case only; a name or definition leaves as its bytes wherever it becomes a value (a literal, sqlite_schema's
  columns, a pragma's rows, sqlite_stat1) or a message, and a RAISE message keeps its value's bytes
  (`stringLiteralsKeepTheirBytes`, `namesKeepTheirBytes`, `schemasSqliteWroteWithBytesRoundTrip`,
  `connectionsTakeSqlOfAnyBytes`). A file name for ATTACH or VACUUM INTO that is not UTF-8 is refused with
  SQLite's "unable to open database: …", as macOS's file system makes sqlite3 refuse it
  (`fileNamesThatAreNotUtf8AreRefused`); on Linux SQLite would make such a file.
- **UTF-16 databases.** The C# translated a UTF-16 database's text to .NET strings on reading, but wrote text
  into its records as UTF-8 (so sqlite3 then read `wörld` as `썷状摬`), kept its indexes in UTF-8 order, and showed
  UTF-8 wherever text met bytes. SQLite holds text in the database's encoding, and that shows; here text is held as
  UTF-8 and translated where SQLite would see the encoding (`src/textenc.cee`):
  - records hold text in UTF-16, translated as sqlite3VdbeMemTranslate does (READ_UTF8: bytes that are not UTF-8
    and overlong forms become U+FFFD, U+FFFE and U+FFFF stay), sqlite_schema's names and SQL included;
  - BINARY compares the encoding's bytes: in UTF-16LE `'Ā' < 'a'` (00 01 against 61 00), and in UTF-16BE a
    character above U+FFFF sorts before U+E000..U+FFFF; so do indexes (seeks in sqlite3's, entries written here),
    ORDER BY, GROUP BY, comparisons, min() and max(), window orders and compound ORDER BY. NOCASE and RTRIM exist
    in UTF-8 only in SQLite, so they compare the translation, as before;
  - text becomes a blob as the encoding's bytes: CAST(text AS BLOB), CAST of a number AS BLOB, hex() of text (of
    a number it stays UTF-8, as SQLite's sqlite3_value_blob gives), octet_length() of text and of numbers; so
    `length(CAST(t AS BLOB))`, substr() and instr() of such blobs count UTF-16 bytes;
  - a blob is read as text in the encoding: CAST(blob AS TEXT) (and AS a number), `||`, group_concat(), and every
    function that reads text (upper(), trim(), replace(), unicode(), LIKE, printf('%s'), …); length(), quote(),
    substr(), typeof() and the functions that pass a value on keep the blob, and instr() of two blobs compares
    bytes;
  - ATTACH of a database in another encoding is refused, as in SQLite.
  (`utf16TextMeetsBytesAsInSqlite`, `utf16DatabasesAreWrittenInTheirEncoding`, on UTF-16le and UTF-16be fixtures
  made by sqlite3.) What still differs, because the engine holds text as UTF-8: SQLite never translates text it
  read from a record, so an odd last byte and a high surrogate followed by a unit that is not its pair keep their
  bytes there (hex() shows them, and an UPDATE of another column writes them back), where here they are dropped or
  paired on reading; a lone surrogate read from a record is kept (ED A0 80 here, and written back as D800), but
  text made in UTF-8 with such bytes (`char(0xd800)`) is written as the surrogate where SQLite writes U+FFFD;
  `x'00' || 'a'` concatenates bytes in SQLite (and drops an odd byte) where here each side is translated first;
  arithmetic on a blob (`x'3100' + 1`) reads its bytes as UTF-8. A new database is always UTF-8 here (PRAGMA
  encoding cannot set it), so a TEMP or newly attached database of a UTF-16 session is UTF-8 where SQLite would
  make it UTF-16; VACUUM of a UTF-16 database is still refused (sqlite3 on macOS reserves 12 bytes per page in the
  files it makes, which VACUUM here refuses anyway, so it cannot be tested).
- **Names in messages and definitions.** A name the shell's tests met while checking the above: a CREATE TABLE,
  VIEW or TRIGGER of a name in use says `table "t" already exists` with the name as written (SQLite's `%T`); a CHECK
  constraint's failure names it by its CONSTRAINT name, else by its text dequoted as sqlite3Dequote does
  (`CHECK ("b" <> 'x')` is `b`), where the C# always gave the whole text; RENAME COLUMN writes the new name in
  double quotes everywhere when the statement quoted it, and wherever the old one was quoted, as renameEditSql does,
  where the C# wrote it bare whenever it could (`renamedColumnsAreQuotedAsSqliteQuotesThem`). A name whose first
  seven bytes end inside a character (`"abcdefé"`) no longer stops the engine with a panic when it is checked for
  the `sqlite_` prefix.
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
- **The write-ahead log's recovery.** When the log ends in frames of a transaction that did not commit, the C#
  let such a frame replace the committed frame of the same page in its map and then dropped the page, reading it
  as it was before both transactions. Here only committed frames enter the index
  (`anUnfinishedTransactionHidesNoCommittedPage`). A frame naming page 0 ends the log, and a log of an unknown
  format version is refused, as in SQLite; the database's size is the last commit frame's, not page 1's field.
- **The write-ahead log's salts.** The C# wrote salts 1 and 1 in every log, and wrote page 1 with every commit.
  A new log here has random salts and a restarted one the next salt-1 and a new salt-2, as SQLite does, so no
  frame of an old log can pass for one of the new; page 1 goes into the log only when a commit changes it, so
  `PRAGMA wal_checkpoint` counts the frames SQLite counts (`walPragmasAnswerAsSqlites`).
- **Checkpoints.** The C# copied every page of the database back from its cache at each checkpoint, and always
  emptied the log. Here a checkpoint copies only the frames not yet copied; PASSIVE, FULL and RESTART leave the
  log for the next commit to start again, and TRUNCATE empties it (`sqliteReadsTheLogThisEngineWrites`). The C#
  also wrote a `-shm` wal-index of its own, covering 4062 frames at most (its first block); here the index is
  SQLite's, with as many 32 KiB blocks as the log needs, and shared: sqlite3 reads a log of more than 4062 frames
  through the hash tables this engine wrote, and the reverse (`shmIndexBlocksAreSharedBothWays`).
- **The wal-index.** The C#'s `-shm` was its own: SQLite could not take it as it was, and it took no `-shm` locks.
  Here wal.c's protocol is followed (walindex.cee): readers take read marks and run beside the writer, a commit
  publishes the header's two copies after its frames are indexed, checkpoints stop at readers' marks, and the
  first connection (the DMS lock) rebuilds the index from the log. sqlite3 reads beside this engine's writer
  through the `-shm` this engine wrote, which it could not rebuild then (`shmSqliteReadsBesideThisEnginesWriter`),
  and the reverse (`shmThisEngineReadsBesideSqlitesWriter`). Nothing in the `-shm` is trusted: a header that is
  torn, fails its checksum, or names frames the log does not hold is rebuilt from the log; a frame the hash
  tables name must carry the page's number and the log's salts; hash chains are bounded; else `Corrupt`
  (`shmDamagedIndexIsRebuiltOrCorrupt`).

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
- **Files the mutators cannot keep sound.** A database with pointer-map pages (auto-vacuum) is refused for
  writing; the C# wrote it, leaving the pointer map out of step. A database in WAL mode is written through its
  log by the same pager as any other (`appendsToALogSqliteLeft`).
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
  written; RENAME TO renames automatic indexes, index ON clauses and other tables' REFERENCES; RENAME COLUMN
  follows into REFERENCES t(column) clauses; ADD COLUMN goes after the last column definition and refuses what
  SQLite refuses, with its messages (`alterTableRewritesDefinitions`). Views and triggers follow both renames as
  in SQLite's default, `PRAGMA legacy_alter_table = OFF`: the table's name wherever it stands as a table or
  qualifies a column, the column's name where it means that table's column (`renamesReachViewsAndTriggers`). The
  macOS sqlite3 shell is built with legacy_alter_table on, which this engine also supports. The C# stored its
  renderer's version of the whole statement and left views and triggers naming the old names.
- **Date and time values.** The C# read time values through .NET's `DateTime`: no year 0 or earlier, no
  `+HH:MM`/`Z` zones, at most three fraction digits, no time without a date, and a bare number was always a Julian
  day. The port of SQLite's date.c reads them all as SQLite does, numbers included (`dateTimeValues`). A time of
  24:00:00 is the next day's midnight before any modifier sees it, and hour 24 with other minutes or seconds is no
  time, as in SQLite 3.54.1 (Apple's sqlite3 3.54.0 keeps 24:00:00 as it is and takes 24:30).
- **Modifiers.** The C# applied 'unixepoch' and 'auto' wherever they stood, made 'floor' re-run month arithmetic,
  treated 'utc' and 'localtime' as nothing, and lacked 'julianday', '±HH:MM', '±YYYY-MM-DD', and 'subsec' outside
  datetime(). Here they apply in order with SQLite's rules (only right after the value for 'unixepoch', 'julianday',
  'auto'), and 'localtime'/'utc' read the system's time zone as SQLite's toLocaltime does, equivalent years
  outside 1970–2037 included (`dateTimeModifiers`, `localTimeAsTheShellHasIt`, checked under eight TZ values).
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
  - `printf(NULL)` and `printf()` were `''`; in SQLite they are NULL. An empty result is `''` in SQLite 3.54.1
    (Apple's 3.54.0 gives NULL), and here (`printfFlagsAndParsing`).

  Bytes that are not UTF-8 (a `%.Ns` precision that cuts a character in two, a text or blob argument that is not
  UTF-8) are kept as SQLite keeps them (`textFormatsKeepBytes`). Where this still differs from the stock library:
  results longer than SQLite's default limit of 10^9 bytes are "string or blob too big"; the macOS
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
    FLAGS argument; json_pretty() and json_array_insert() exist;
  - the jsonb_* functions, jsonb_group_array() and jsonb_group_object() return SQLite's JSONB, including the
    headers SQLite widens in place when an edit shrinks a value (jsonBlobOverwrite); the C# had none
    (`jsonbFunctionsReturnJsonb`, `jsonbMatchesSqliteOnRandomInput`);
  - json_each(), json_tree(), jsonb_each() and jsonb_tree() exist, with SQLite's columns and its `id`s (offsets
    in the JSONB), a root path, and arguments that name the tables before them (`jsonEachWalksContainers`,
    `jsonEachJoinsTables`); the `value` of an array or object nests as JSON (`jsonEachValueHasJsonSubtype`);
  - a JSONB blob with a damaged element header makes json_each() and json_tree() report "malformed JSON", where
    sqlite3 loops for ever on the element (`jsonEachStopsOnDamagedJsonb`).
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
- **The shell** (`cli/tests/shell_tests.cee`, each compared with the `sqlite3` shell):
  - statements end where sqlite3_complete ends them; the C# ended one at the first `;` outside quotes, so it ran a
    trigger's body a statement at a time (`statementsAsSqlite3CompleteSplitsThem`);
  - each SQL argument runs on its own, and the first that fails ends the run; the C# joined the arguments with
    spaces into one text, so `"SELECT 1" "SELECT 2"` was a syntax error (`argumentsRunInOrder`,
    `anArgumentThatFailsEndsTheRun`);
  - errors are sqlite3's ("Parse error near line 2: …", "Error in 2nd command line argument: …"), a statement that
    cannot be prepared ends the text it is in, and any error makes the exit status 1; the C# printed "Error: …"
    and always exited 0 (`errorsInInput`, `bailReadAndExit`);
  - a blob prints its bytes, and control characters print as `^X`, as in sqlite3; the C# printed blobs in hex
    (`listModeAndHeaders`);
  - `.schema` lists `sqlite_sequence` and adds a view's columns as sqlite3 does; `.tables` sets the names in
    columns; a dot-command is recognised only at a line's first character (the C# trimmed the line first); column
    mode right-aligns numbers and centres headings; csv and line modes exist (`tablesAndSchema`, `columnMode`,
    `csvMode`, `lineMode`, `dotCommandErrors`).
- **The PostgreSQL wire front end** (`pgwire/tests/wire_tests.cee`):
  - a result column's type comes from all of its values; the C# took the first row's, and announced bigint for a
    column whose later rows were text (`columnTypesComeFromEveryRow`);
  - rows of a statement executed without Describe are sent, as PostgreSQL sends them; the C# dropped them, so
    `INSERT … RETURNING` through the extended protocol returned nothing (`extendedQueryProtocol`);
  - Execute's row limit suspends the portal (PortalSuspended) and the next Execute resumes it; the C# ignored the
    limit (`executeWithARowLimitSuspendsThePortal`);
  - `$n` parameters are bound by name, so `$2 … $1` binds each to its own value (SQLite numbers `$2` first); a
    bytea parameter is a blob (the C# made it the text of its hex digits); a wrong parameter count is PostgreSQL's
    08P01 error (`extendedQueryProtocol`, `extendedErrorsSkipToSync`);
  - each constraint has its SQLSTATE (23505, 23502, 23514, 23503); the C# called every constraint failure 23505
    (`transactionsShowInReadyForQuery`);
  - Parse of a statement name in use, or Bind of a portal name in use, is an error (42P05, 42P03), as in
    PostgreSQL; the C# replaced it (`extendedErrorsSkipToSync`);
  - a malformed message (a length past its end, a length word under 4, an unknown type) ends the session with
    FATAL 08P01; the C# indexed past the payload (`malformedMessagesEndTheSession`);
  - a startup packet asking for protocol 3.x (x > 0) or `_pq_.` options gets NegotiateProtocolVersion; the C#
    refused it (`newerProtocolVersionsAreNegotiated`);
  - CommandComplete tags are PostgreSQL's (`CREATE TABLE`, `DROP VIEW`, `INSERT 0 n` after `WITH … INSERT`); the
    C# gave the first word (`simpleQueries`);
  - databases are served from a pool per file (`ConnectionPool`), so clients of one database see each other's
    commits and never each other's open transactions (`clientsShareTheDatabaseFile`).
- **Window functions** follow SQLite's rules where the C# made its own (`windowFunctionsMatchSqlite`,
  `windowFunctionsInContext`): rows come out in the first window's order when there is no ORDER BY; a negative
  lag()/lead() offset looks the other way; RANGE offsets need one numeric ORDER BY term and compare in its
  direction, with NULL and non-numeric keys framed by their peers; frame offsets are checked with SQLite's
  messages; DISTINCT and FILTER on non-aggregates are refused as in SQLite; window arguments in an aggregate query
  may hold aggregates (`sum(sum(v)) OVER (…)`). Frames that do not start at the partition's start are summed
  afresh for each row (no inverse step yet), so a sliding frame costs its width per row.
- **RIGHT and FULL joins** run in the nested loops: each right source's rows that matched nothing come out after
  the loops, with the earlier sources NULL; a column USING or NATURAL shares is `coalesce(left, right)` in
  unqualified names and `*`, while `t.*` and `t.column` are the table's own, as in SQLite 3.54.1 (Apple's 3.54.0
  coalesces in the left table's `t.*` too; `rightAndFullJoinsMatchSqlite`). The C# refused
  them.
- **Result column names** are SQLite's (`resultColumnNamesMatchSqlite`): an expression's text as written, comments
  and spacing kept; a column's name as its table declares it, whatever case the query uses; the INTEGER PRIMARY
  KEY's name for `rowid`; `columnN` for VALUES. The C# wrote the expression again from its tree (`abc + 1` for
  `abc  +  1`) and used the name as the query spelled it.
- **Index seeks** use an index only where it finds every row the comparison can be true for: the index column's
  collation must be the comparison's, and the comparison's affinity must leave the stored values unchanged; the key
  is converted as the comparison converts it (`indexSeeksGiveTheSameRows`, `writesThroughIndexSeeks`). WHERE
  still runs on every row the index gives.
- **Partial indexes** are used when the query implies the index's WHERE by SQLite's rule (sqlite3ExprImpliesExpr):
  each of its AND-terms is a term of WHERE (of ON alone for a LEFT JOIN table), one side of an OR that is, or
  `x IS NOT NULL` where a term is false for a NULL x (`partialIndexesWhenTheQueryImpliesThem`). The C# skipped
  every partial index.
- **Expression indexes** take a term on the same expression, compared as compiled (operators, values, columns,
  affinities, collations), the expression's affinity standing for the column's: none, but a CAST's
  (`expressionIndexesMatchCompiledExpressions`). The C# skipped them, and also skipped an index whose COLLATE
  differs from its column's, which this uses for comparisons in that collation.
- **IN (SELECT …) and the rowid**: `x IN (SELECT …)` with a subquery that does not depend on the row runs it once
  and seeks each distinct value; `rowid IN (…)`, `rowid IN (SELECT …)` and rowid ranges read the table between
  rowids, a real between two integers, text or a blob above every number, as SQLite compares them
  (`subqueryAndRowidSeeks`). The C# had only rowid ranges.
- **Covering reads**: when the index entry holds every column the query reads of the table, rows are made from the
  entries (a REAL column's integers read as reals, as from the record) without reading the table; a covering
  index narrower than the table (SQLite's width estimate from the declared types) is scanned instead of the
  table, as SQLite does, so `SELECT b FROM t` comes in `b`'s order as in sqlite3 (`coveringReadsAndIndexOrder`).
- **ORDER BY from an index** only when the order is provably the same: the index's collations, the default NULLS
  placement (NULLS FIRST/LAST otherwise are sorted), every term matched after the columns `=` fixes, all forwards
  or all backwards, for the first table of a SELECT without aggregates, windows or RIGHT JOIN; a rowid after the
  index columns orders the rest only when the table is the query's only one. Backwards walks use the index (or
  the table's b-tree, by rowid) backwards, and LIMIT then stops early (`coveringReadsAndIndexOrder`).
- **Choosing a path** follows SQLite's cost model (whereLoopAddBtree, whereRangeScanEst, whereSortingCost) in
  LogEst: the table scan, the rowid, then the newest index first, the first of equal cost winning; a path that
  needs a sort pays for it, so a range on one end gives way to a scan in ORDER BY's order. With sqlite_stat1 (after
  ANALYZE) the estimates are the statistics' (`statisticsChooseBetweenIndexes`): a column with two values loses to
  a range on a column of many. The C# read sqlite_stat1 too, to choose among its seeks.
- **ORDER BY sorts are stable**, as SQLite's sorter is: rows with equal keys keep the order they came in. The sort
  was an introsort (CeeSafe's `sortBy` is not stable), so ties came out in an arbitrary order.
- **A LEFT JOIN table's rowid** is not sought from an IS in WHERE: `t.id IS NULL` there found no row, so every
  row came out NULL-extended instead of only those without a match (`subqueryAndRowidSeeks`).
- **Indexes a statement left stale** (a removal not done in place, rebuilt when it ends) are not read by its
  triggers' seeks.
- **CREATE TABLE … AS SELECT** writes its statement as SQLite's createTableStmt does: columns typed `INT`,
  `TEXT`, `NUM`, `REAL` or nothing by their affinities, repeated names made unique with `:N`, names quoted where
  SQLite quotes them, and a column a line once the statement is long (`createTableAsSelectLikeSqlite`). The C#
  refused it.
- **DROP COLUMN** follows SQLite: the definition leaves the statement with its own constraints, a PRIMARY KEY or
  UNIQUE column or the last column is refused, a CHECK, generated column or index still naming it is "error in
  table/index X after drop column", and every row loses the value (`dropColumnLikeSqlite`).
- **Parameters are numbered as SQLite numbers them** (`parametersAreNumberedAsSqliteNumbersThem`,
  `parameterValuesBindAsSqliteBindsThem`). The parser numbers each parameter where it is written, as
  sqlite3ExprAssignVarNumber does: `?` takes the largest number so far plus one, `?NNN` is NNN (1 to 32766), and a
  name keeps the number it first got. The C# bound parameters by walking parts of the tree: a `?` after `?2` took
  value 1 instead of 3, a named parameter had no number (so `?1` could not refer to `:a`), and parameters in CTEs
  or RETURNING were not found. Before this change the port numbered them as the compiler met them, so in
  `SELECT :a FROM t WHERE x < :b` the WHERE clause took the first value, and in `UPDATE … FROM` two compilers
  numbered from 1 each.
- **Binding.** `:a`, `@a` and `$a` are three parameters, and `:a` and `:A` two, as in SQLite; the C# looked names up
  ignoring case and with their prefix stripped, so binding `:a` also bound `@a` and `$A`. A name given without a
  prefix binds every prefix of it (`Params.bind("a", v)`), as Microsoft.Data.Sqlite does. A parameter given no
  value is NULL, as in SQLite; the C# threw "missing value for parameter" or an index exception. A value no
  statement has a place for is an error, as sqlite3_bind_* gives SQLITE_RANGE.
- **Scripts** end their statements where SQLite does: by sqlite3_complete's machine over tokens, so a trigger body
  ends at `; END ;` and not at a CASE's `END;`, a comment before CREATE TRIGGER does not hide it, and statements of
  comments alone are dropped. The C# split by regular expressions and got all three wrong
  (`scriptsSplitWhereSqliteEndsStatements`). A script stops at its first error, and the statements before it keep
  their effect, as with sqlite3_exec (`aScriptStopsAtItsFirstError`).
- **Closing inside a transaction rolls back.** The C# flushed its shared in-memory database to the file when the
  last connection to it closed, whether or not a transaction was open, so `BEGIN; INSERT …; Close()` committed the
  insert; its `SqliteTransaction` did nothing when disposed without `Commit`. Here `close()`, dropping a
  connection, and `transaction(work)` when `work` fails all roll back (`closingInsideATransactionRollsBack`,
  `transactionsCommitOrRollBack`).
- **Connections kept apart.** The C# connections to one file shared one in-memory database: statements were
  serialised, transactions were not, so a connection saw another's uncommitted rows, and a pooled connection given
  back inside a transaction went to the next caller with the transaction open. For `:memory:` the pool handed
  every caller the same connection at once. Here every connection is kept apart from the others, in this process
  or another, by SQLite's file locks (below); a connection given back to a pool inside a transaction is rolled
  back first; and a connection reads the file afresh when another committed since its last transaction
  (`poolConnectionsComeBackRolledBack`, `threadsShareAPool`, `connectionsSeeEachOthersCommits`).
- **File locks.** The C# took none, so it could not share a file with another process, sqlite3 included. Here the
  writable pager takes os_unix.c's locks on the bytes from 0x40000000 (PENDING, RESERVED, the 510-byte SHARED
  range), which sqlite3 sees: a statement takes SHARED on every database (in WAL mode, held for as long as the connection has it
  open, with the `-shm` locks for each transaction) and,
  if it writes, RESERVED on its own as it begins; a commit takes PENDING and EXCLUSIVE, waiting for readers to
  leave; the locks go when the transaction ends. BEGIN IMMEDIATE and BEGIN EXCLUSIVE take RESERVED and EXCLUSIVE
  at once. A reader inside a transaction keeps writers from committing, so it sees one snapshot. Before reading, a
  hot journal (one with its header synced while no writer holds RESERVED) is rolled back under EXCLUSIVE; a
  journal whose writer still holds RESERVED is left alone. A connection forgets its pages when the file's header
  or the log changed since it last held a lock, as SQLite checks its change counter, and PRAGMA data_version
  counts such changes as sqlite3 does (`locksSqliteHoldingExclusiveMakesThisEngineWait`,
  `locksThisEngineHoldingLocksMakesSqliteWait`, `locksAReaderInATransactionSeesAStableSnapshot`,
  `locksConcurrentWritersNeverLoseACommit`, `locksHotJournalsAreRolledBackAndLiveOnesLeftAlone`,
  `locksAJournalWhoseWriterHoldsReservedIsNotHot`, `locksTwoSessionsInOneProcessAreKeptApart`,
  `locksDataVersionCountsOtherConnectionsCommits`; in WAL mode the `shm*` tests). Before CeeSafe had file
  locks this port passed a gate between a pool's connections and could not keep apart connections opened on
  their own; both workarounds are gone.
- **Busy.** A connection that meets another's lock retries as sqliteDefaultBusyCallback does (sleeps of 1, 2, 5,
  … 100 ms) until its busy timeout (`PRAGMA busy_timeout`, `setBusyTimeout`; 5000 ms in a pool, 0 for a lone
  connection, as in SQLite), then fails with `SqliteError.Busy`, "database is locked". As in SQLite, a connection
  that already reads in a transaction and then wants to write while another holds RESERVED fails at once, since
  waiting would deadlock with that writer waiting for it to leave; a COMMIT that cannot get EXCLUSIVE leaves the
  transaction open, to be tried again; a statement outside BEGIN whose commit cannot is rolled back. A checkout
  with every connection of the pool out waits for one to come back, up to the same timeout (`recvTimeout`, no
  longer a polling loop that spun a core).
- **`:memory:` is a database of the connection's own**, as in SQLite, not a file of that name: here a private file
  removed when the connection closes (the C# shared one in-memory database among every `:memory:` connection);
  `file:` URIs are refused.
- **Index cells take at least 4 bytes**, as SQLite counts them: a WITHOUT ROWID table of small keys made 3-byte
  cells, which sqlite3 calls out of range (`tinyIndexCellsTakeFourBytes`).
- **INSTEAD OF triggers** make views writable as in SQLite (`insteadOfTriggersOnViews`): the rows are the view's
  rows WHERE selects (joined with FROM for UPDATE … FROM), UPDATE OF counts, RETURNING gives NEW (OLD for DELETE),
  changes() stays 0, and DROP VIEW drops the view's triggers. A trigger body's changes count in
  total_changes(), as in SQLite; this engine had left them out.
- **Target aliases, RETURNING names, ordered aggregates** (`targetAliasesAndReturningNames`,
  `returningColumnNamesMatchSqlite`, `orderedAggregatesMatchSqlite`): `UPDATE t AS x`, `DELETE FROM t AS x` and
  `INSERT INTO t AS x … DO UPDATE` name the row by the alias in SET, WHERE and DO UPDATE (RETURNING keeps the
  table's name, as in SQLite); RETURNING's columns are named from the statement's text; `group_concat(x ORDER BY
  y)` and the JSON aggregates take their rows in order, the other aggregates accept and ignore ORDER BY, and a
  non-aggregate is "ORDER BY may not be used with non-aggregate f()". The C# refused all three.
- **ON CONFLICT on constraints** applies as in SQLite (`constraintConflictClausesApply`): a statement's OR action
  overrides it; IGNORE and REPLACE on NOT NULL, PRIMARY KEY and UNIQUE work, REPLACE constraints are resolved after
  the others, and two constraints that share an index with different actions are "conflicting ON CONFLICT clauses
  specified". The C# read the clauses and ignored them.
- **SAVEPOINT, RELEASE and ROLLBACK TO** nest as in SQLite (`savepointsNestAsInSqlite`): a SAVEPOINT outside a
  transaction begins one, which releasing it commits; ROLLBACK TO keeps the savepoint and closes those inside it;
  names repeat, the innermost answering. The pager keeps a stack of undo levels, the running statement's on top.
  The C# refused savepoints.
- **ANALYZE and REINDEX** (`analyzeAndReindexLikeSqlite`): ANALYZE writes sqlite_stat1 as SQLite does, row for
  row (index columns under their collations, partial indexes over their rows, a WITHOUT ROWID key under the
  table's name, nothing for an empty table); REINDEX rebuilds every index. The planner reads the statistics
  (see "The planner" below). The C# refused both.
- **VACUUM** (`vacuumPacksTheFile`) builds every b-tree again into packed pages within one transaction, records
  as they are stored, header settings kept, freelist empty; the file comes out the size sqlite3's VACUUM gives.
  VACUUM INTO writes the packed image to a new file
  (`vacuumIntoWritesACopy`), refusing an existing file that is not empty and a non-text name as SQLite 3.54.1 does (Apple's 3.54.0
  refuses an empty one too). Refused: VACUUM inside
  a transaction (as in SQLite), UTF-16 databases and pages with reserved
  bytes. The C# refused VACUUM.
- **OR FAIL and OR ROLLBACK** (`failAndRollbackActions`), from a statement, a constraint's ON CONFLICT or a
  trigger's RAISE: FAIL keeps the rows the statement changed before the failing one (indexes it left to rebuild
  are rebuilt then), ROLLBACK ends the whole transaction. changes() counts the rows FAIL kept, as in SQLite.

- **TEMP and ATTACH** (`tempTablesAndAttachedDatabases`): names resolve as in SQLite (TEMP, then main, then the
  attached databases in order, or the schema written), `sqlite_temp_schema` and `aux.sqlite_schema` read each
  database's schema, a TEMP trigger may be on another database's table, a view or trigger outside TEMP sees only
  its own database's tables, and a transaction spans every database. The C# refused both.

- **The planner across databases:** each table is planned with its own database's indexes, but the statistics
  ANALYZE wrote are read from the active database only.

- **GROUP BY's groups** come out as SQLite gives them (`groupsComeOutAsSqliteGivesThem`): in the order of their
  GROUP BY values, or in an index's order when the table is read through an index on those columns; a column
  outside the aggregates takes the group's first row (or the row of its one min() or max()). This engine had
  listed groups as it met them and taken the last row.

- **Row values in IN** (`rowValuesInInMatchSqlite`): `(a, b) IN (SELECT x, y …)` and `IN ((x, y), …)` compare
  element by element with each pair's affinity and collation, NULL elements making a row unknown; a subquery of
  the wrong width is "sub-select returns N columns - expected M", an item of the wrong width "IN(...) element has
  N terms - expected M", as in SQLite.

## The math functions

The math functions call the platform's libm through CeeSafe's float methods (ceesafec 0.95.0, ADR 0218), as the
`sqlite3` shell does, so their results are the shell's bit for bit (`mathFunctionsAgreeWithTheShellOnManyArguments`
compares 1,600 calls printed with `%!.17g`). Before 0.95.0 the port carried `libm.cee`, a port of FreeBSD msun in
double-double arithmetic, which differed from macOS's libm in the last bit on up to 40% of `tan`'s arguments.

## Known differences from SQLite in the JSON functions

- **A scalar subquery drops the JSON subtype.** `json_array((SELECT json('[1]')))` is `[[1]]` in SQLite and
  `["[1]"]` here. This engine's values carry no subtype; JSON-function arguments are evaluated by
  `evaluateWithSubtype` (`json.cee`), which sees through CASE, coalesce, ifnull, iif, nullif, likely, unlikely,
  the scalar min and max, unary `+`, CAST, COLLATE, `->`, the JSON aggregates and json_each's `value`, but not
  into a subquery (`SELECT json_array(x.value) FROM (SELECT value FROM json_each('[[1]]')) x` quotes it).
- **Window functions.** json_group_array() and json_group_object() run as window functions, but their arguments
  lose the JSON subtype on the way through the window, so a JSON argument is quoted as text.
- **json_each() and json_tree() compute every column of a row.** SQLite reads only the columns a query uses, so
  over a damaged JSONB blob `SELECT key FROM json_each(…)` can succeed in SQLite where this engine reports
  "malformed JSON" from the `value` column.
- **The arguments of json_each() and json_tree() come from the parentheses.** A json_each source has no rowid
  (SQLite numbers its rows from 0), a constraint on its hidden `json` or `root` column in WHERE does not stand
  for the argument, and an argument may name only the FROM items before it: SQLite's planner also accepts
  `FROM json_each(t.doc), t`, which here is "no such column".
- **Nesting depth.** The limit is 3.53.4's 1000 levels; the `sqlite3` shell the tests run (3.54.0 on macOS) was
  built with 800, so the tests stay on depths where the two agree.

## The API

`api.cee`, `params.cee`, `script.cee` and `pool.cee` are the public surface, in place of the C#'s ADO.NET classes:

```
var connection = Connection.open("app.db")?;               // makes an empty database if there is none
connection.executeScript("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)")?;
var params = Params.create();
params.bind(":name", SqliteValue.text("ada")?)?;           // or add(v) for ?, set(n, v) for ?n
let changed = connection.execute("INSERT INTO t(name) VALUES (:name)", borrow params)?;
let none = Params.create();
let rows = connection.query("SELECT id, name FROM t", borrow none)?;   // a QueryResult
let n = connection.scalar("SELECT count(*) FROM t", borrow none)?;   // null when there is no row
let id = connection.transaction<i64>(work)?;              // commits when work returns Ok, else rolls back
connection.close()?;                                       // rolls back a transaction left open

let pool = Arc<ConnectionPool>.create(ConnectionPool.open("app.db", 4)?)?;
var lease = pool.get().checkout()?;                        // goes back, rolled back if need be, when dropped
lease.get().execute(…)?;
```

Choices where the C# concept does not fit CeeSafe:

- **Errors** are `Result<T, SqliteError>`; `SqliteError.Busy` is new, for "database is locked", and
  `SqliteError.ReadOnly` for "attempt to write a readonly database" (SQLITE_READONLY).
- **Read-only connections.** `Connection.openReadOnly(path)` opens as SQLITE_OPEN_READONLY (`sqlite3 -readonly`):
  the file must exist, statements that would write are refused, BEGIN IMMEDIATE and EXCLUSIVE are read
  transactions, TEMP tables are the connection's own. `Connection.open` opens a file it may not write so too, as
  unixOpen falls back to reading.
- **Lifetimes.** There is no IDisposable: a `Connection` closes when it is dropped (rolling back), and `close()`
  says whether that rollback worked. A `PooledConnection` gives its connection back when dropped.
  `transaction(work)` takes a function rather than handing out a transaction object, so a transaction cannot
  outlive its scope or be forgotten open.
- **No async methods.** The engine is in-process and synchronous; the C#'s async methods ran synchronously too.
  Tasks can use a pool from a worker thread.
- **SQL text and messages are bytes**, as SQLite's are: `executeBytes`, `queryBytes`, `scalarBytes` and
  `executeScriptBytes` take a `ByteStringView`, and `execute`, `query`, `scalar` and `executeScript` a `StringView`;
  `QueryResult.columns` are `ByteString`s, and `SqliteError.message()` is a `ByteStringView` (`messageText()` gives
  a `String`).
- **Text** is `SqliteValue.Text(ByteString)`: SQLite's TEXT may hold any bytes, and they are kept as they are.
  `SqliteValue.text(view)` and `SqliteValue.textOfBytes(bytes)` make one; `value.textView()` gives a TEXT value
  as a `StringView` when it is UTF-8 (null otherwise), and `toText()` any value's text as SQLite gives it.
- **Parameters** are a `Params` value passed with each call, not a command object's mutable collection, and there
  is no `SqliteCommand`: a command was only text, parameters and a connection.
- **Results are materialised.** `query` returns every row. The executor's SELECT (`runSelect`) builds its rows as
  a vector, so a streaming reader here would only walk that vector; the C# reader did the same over its list.
  Streaming needs the executor to yield rows, a larger change than this API.
- **Several statements in one text.** `execute`, `query` and `scalar` run every statement of their text, binding
  to each the parameters it has (Microsoft.Data.Sqlite's rule); `query`'s result is the last statement's, and
  `execute` counts every INSERT, UPDATE and DELETE.
- **The pool and threads.** CeeSafe checks `Send` and `Share`: a `ConnectionPool` is `Share`, so threads share it
  through `Arc`, and a `Connection` is `Send`, so a checked-out one may move between threads but is used by one
  at a time. A pool's connections, connections opened on their own and other processes are all kept apart by
  SQLite's file locks, which belong to each connection's open file (open-file-description locks), so two
  connections of one process exclude each other as two processes do; a pool only holds idle connections and
  bounds how many there are. Settings a borrower changes with PRAGMA (foreign_keys, busy_timeout) stay with the
  connection for the next borrower, as in other pools.
- **Configuration.** There is no connection string; a path is given. `:memory:` and the empty name give a
  private database of the connection's own (a file removed when it closes); a pool refuses them, and `file:` URIs
  are refused.

## Front ends

Three packages beside the library, each depending on it by path, each built and tested in its own directory
(`ceesafec build`, `ceesafec test`). The library gained one public method for them, `SqliteValue.toText()` (the
text SQLite gives a value, as a `ByteString` of any bytes, `src/frontend.cee`). The shell prints a text's bytes as
they are, as sqlite3 does; the wire server sends UTF-8 (see below).

### The shell (`cli/`)

```
cd cli && ceesafec build
out/sqlite_shell app.db "SELECT * FROM t"            # each argument a text of SQL or a dot-command
out/sqlite_shell -csv -header app.db < script.sql    # or statements and dot-commands from standard input
out/sqlite_shell app.db                              # at a terminal: a banner, then prompts
```

It behaves as sqlite.org's `sqlite3` shell 3.54.1 for what it has: options `-header`, `-noheader`, `-list`,
`-csv`, `-line`, `-column`, `-bail`; dot-commands `.headers on|off|always`, `.mode list|csv|line|column`,
`.tables`, `.schema`, `.read`, `.bail`, `.quit`, `.exit N`, `.help`; output byte for byte as sqlite3 prints it,
errors as sqlite3 words them, and exit status 1 after an error. As in 3.54.1, an error leaves the rest of its
argument or line, whether the statement failed as it was prepared or as it ran, and `.schema` writes a view's `;`
before the comment that names its columns; Apple's sqlite3 3.54.0 differs in these and in `.headers`' usage, and
the tests compare with sqlite.org's output there when they run against it (`APPLE_DIFFERS` in
`cli/tests/shell_tests.cee`). When standard input is a terminal (`Console.isTerminal`) and no argument gives SQL,
it is interactive as sqlite3 is: it prints the banner, prompts with `sqlite> ` and, while a statement is unfinished,
`   ...> `, goes on after errors even under `.bail`, and ends the line at Ctrl+D; otherwise it reads standard input
as a script. The tests run the same arguments and input through both shells on copies of one database and compare
everything printed, then check the file with `PRAGMA integrity_check`; `tests/terminal.py` does the same for
sessions typed into both at a pseudo-terminal, with sqlite.org's line editor off (`-cmdline-edit off`: it asks
the terminal where its cursor is and redraws lines, where Apple's sqlite3 and this shell read the terminal's lines).
Differences:

- no caret line under a statement's error ("^--- error here"): the engine does not report where in the text an
  error is; and the engine does not say whether a statement failed when it was prepared or when it ran, so "Parse
  error" or "Error" is chosen by the kind of error (`isPrepareError`);
- without a file, sqlite3 opens an in-memory database; the engine has none, so the shell uses a temporary file,
  removed at the end;
- at a terminal: the prompts are the classic ones, which sqlite3 3.54 shows when `SQLITE_PS1` and `SQLITE_PS2`
  say so (its own default is a coloured prompt naming the database; the tests set them); sqlite3 then defaults to
  box mode, which this shell does not have, so it stays in list mode; the banner gives the engine's version
  without a date, and without a file it does not suggest `.open`; there is no line editing or history;
- none of sqlite3's other dot-commands and options (`.import`, `.dump`, `.open`, `.separator`, box and table
  modes, …);
- `.tables` with more names than fit on one line sets them in columns of sqlite3's widths but does not fold the
  line at 60 characters as sqlite3 3.54 does.
- input is read as UTF-8 text (`Console.readLine`), and error messages are written as UTF-8 (U+FFFD for a byte
  of a name or RAISE message that is not), where sqlite3 reads and writes bytes; results are written as their
  bytes, as sqlite3 writes them.

### The PostgreSQL wire server (`pgwire/`) and the daemon (`daemon/`)

```
cd daemon && ceesafec build
SQLITED_PASSWORD=a-long-secret out/sqlited --bind 127.0.0.1:5432 --data ./data
psql "host=127.0.0.1 port=5432 user=me dbname=shop"   # ./data/shop/main.db, made on first use
out/sqlited --trust                                   # no password: every client is let in
```

`pgwire` is the library (`PgServer`, `serve(server, listener)`): protocol 3.0, with SSLRequest and GSSENCRequest
answered 'N', NegotiateProtocolVersion for later minor versions, cleartext password authentication (or trust),
the simple query protocol, the extended one (Parse, Bind, Describe, Execute with row limits, Close, Sync, Flush),
text and binary formats, ErrorResponse with SQLSTATEs, and ReadyForQuery's transaction status. Each client has a
thread and a connection from its database's `ConnectionPool` for its whole session; `serve` keeps the clients'
threads and joins each that has finished when the next client comes (`isFinished`), so it holds only those of
connected clients and counts them against the limit (`setLimits`), and once its listener is shut down it waits for
the clients still connected, joins their threads and returns how many clients it served. `daemon` is the C#'s
CosmoSqliteD: a bind address, a data directory with one directory a database (the C#'s layout), a password from
`SQLITED_PASSWORD` (it refuses to start without one unless `--trust`), and a clean stop on Ctrl+C or SIGTERM: it
stops accepting, waits up to five seconds for `serve` to return, and exits.
The tests drive the server over TCP with a raw client, and with `psql` when it is installed. Differences from
PostgreSQL:

- the SQL is SQLite's. Outside BEGIN each statement is its own transaction (PostgreSQL runs a multi-statement
  simple query, and an extended-protocol batch up to Sync, as one), and an error inside BEGIN undoes its
  statement only, so the status stays 'T' and is never 'E';
- PostgreSQL's `START TRANSACTION`, `BEGIN ISOLATION LEVEL …`, `COMMIT AND CHAIN`, `ABORT` become SQLite's
  BEGIN, COMMIT and ROLLBACK, and `SET`, `RESET` and `DISCARD` succeed and do nothing; there is no `pg_catalog`,
  so `psql`'s `\d` and drivers' metadata queries fail;
- text is sent as UTF-8, as client_encoding UTF8 promises: a TEXT value whose bytes are not UTF-8 (SQLite allows
  them) is sent with U+FFFD for each maximal ill-formed subpart, where PostgreSQL could not have stored it at
  all; `CAST(x AS BLOB)` sends the exact bytes as bytea. Parameters that are not UTF-8 are refused with 22021,
  as PostgreSQL refuses them;
- result types are bigint, double precision, bytea or text, decided from a column's values (SQLite's columns have
  no fixed type); a column of a prepared statement described before it runs is text; a parameter of no stated
  type is text, and SQLite's affinity converts it;
- a portal runs when it is first described or executed, and keeps its rows for later Executes: a portal described
  and never executed has still run. Describe of a prepared `INSERT … RETURNING` or PRAGMA finds its columns by
  running it inside a savepoint that is rolled back, which works inside the client's own transaction too;
- no cancel requests (statements run to the end), no COPY, no function calls, no notices, no SSL (put a TLS
  proxy in front), and cleartext passwords only (no MD5 or SCRAM).

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

`CREATE VIRTUAL TABLE`, `EXPLAIN`, and a parenthesized join
that a RIGHT or FULL join takes as a whole, or that is joined by NATURAL or USING. A group of inner joins is read
as its joins in line (`parenthesizedJoinsMatchSqlite`), and `a LEFT JOIN (b … c) ON cond` makes all of the
group's tables NULL when no row of the whole group meets cond (`leftJoinsOfGroupsMatchSqlite`).
Collations other than BINARY, NOCASE and RTRIM are refused.

## Limits

- **TEMP and attached databases.** TEMP is a file of its own in `$TMPDIR`, removed when the session closes (one
  never closed leaves it behind); so is a private database (`ATTACH ''`). A transaction that changes several
  databases commits them one after the other, each atomically with its own journal but not all together: SQLite's
  super-journal is not written. VACUUM, ANALYZE and REINDEX work on main only.

- **Non-deterministic date functions.** 'now', 'localtime' and 'utc' are not refused in CHECK constraints, index
  expressions and generated columns, as SQLite refuses them.

- **Sharing a file.** In rollback-journal mode the engine takes SQLite's locks as os_unix.c does, so it shares a
  database with sqlite3 and other processes (and its own connections) as SQLite connections share one; the RESERVED
  byte is tested for a hot journal without taking it (`File.testLock`, F_GETLK), so no other connection's lock
  attempt is turned away by the test (`locksTheHotJournalCheckTakesNoLock`). What differs: locks are converted in
  place (shared to exclusive on the SHARED range, atomically), which POSIX allows and Windows' `LockFileEx` does
  not, so on Windows the engine does not yet follow os_win.c's scheme; a file system without byte-range locks (some
  network mounts) is not detected.
- **WAL mode.** The wal-index is shared as wal.c and os_unix.c share it (walindex.cee), with fcntl locks on the
  `-shm`'s bytes, so readers run beside a writer, this engine's and sqlite3's alike (`shm*` tests); the DMS byte is
  tested with `F_GETLK` as unixLockSharedMemory tests it. A `-shm` or log this process may not write is opened for
  reading, as SQLite's readonly_shm: while a connection that can write holds the DMS byte the index is mapped for
  reading (PROT_READ) and read marks it set are used, else the index is rebuilt from the log in the connection's
  memory and checked at each transaction as walBeginShmUnreliable checks it (`readOnly*` tests, against sqlite3
  on chmod'ed files and `sqlite3 -readonly`). What differs: a new log's salts are
  always the old header's salt-1 plus one and a new salt-2 (or random), where SQLite reuses the index's salts after
  a restart (either way no old frame can pass for a new one); the index is in the host's byte order, as SQLite's,
  and every host CeeSafe builds for is little-endian; another process that shortens the `-shm` while this engine
  maps it ends the program with SIGBUS, as it would SQLite (ADR 0235 keeps it a signal: SQLite shortens the file only
  under the DMS byte's exclusive lock, which no connection mapping it allows). The locking is POSIX-only: on Windows
  (os_win.c's scheme is not ported) WAL mode is refused with `Unsupported`, in a build for
  Windows (`cfg("target.windows")`). The read-only `DatabaseReader` takes no locks: it reads the log as it finds it, rebuilding its own
  index of the frames.
- **Read-only databases.** An empty file that can only be read is refused with "attempt to write a readonly
  database", where SQLite reads it as an empty database. Leaving WAL mode on a database that can only be read is
  refused with the same message, where sqlite3 answers "disk I/O error" (the write lock it tries on a file open for
  reading fails with EBADF) or, while another connection holds the file, "database is locked". `file:` URIs, and
  with them `?mode=ro` and `?readonly_shm=1`, are not taken: `Connection.openReadOnly` is SQLITE_OPEN_READONLY, and
  a `-shm` is read-only when this process may not write it.
- **Journal modes.** WAL and DELETE only: TRUNCATE, PERSIST, MEMORY and OFF are taken as DELETE, and
  `PRAGMA journal_mode` then answers `delete`. Leaving WAL mode writes the header's format numbers 1 and 1 and
  removes the log, as SQLite does.

## Tests

`ceesafec test` needs the `sqlite3` shell on the path: fixtures are made with it, and answers are compared with
what it prints. The front ends have their own: `ceesafec test` in `cli/`, `pgwire/` and `daemon/` (`pgwire`'s
`psqlTalksToTheServer` runs `psql` when it is installed and is skipped otherwise; `cli`'s `atATerminalAsSqlite3`
builds the shell and runs `tests/terminal.py` when `python3` is installed).

The planner's timing probe (`tests/planner_probe_tests.cee`) times each kind of seek, covering read and index
order against the same query with the index defeated (`+column`) on a 20,000-row table:
`SQLITE_PLANNER_PROBE=1 ceesafec test --filter plannerTimingProbe --show-output`. On the development machine,
for 50 runs (20 for the scans and orders): a partial index 4 ms against 375 ms, an expression index 4 against 880,
`a IN (SELECT …)` 94 against 1,763, `rowid IN (SELECT …)` 5 against 1,709, a rowid range 6 against 295, a covering
seek 3 against 316 (and a covering range seek 29 ms against 118 for the same seek with lookups, 20 runs), a
covering scan of an index 227 against the table's 565, `ORDER BY c LIMIT 10` (and DESC, and
`ORDER BY id DESC`) under 1 against about 320, `WHERE a = 3 ORDER BY c` 3 against 489; `flag = 1 AND c > 19990`
takes 307 ms through `flag`'s index without statistics (as SQLite would choose) and 2 ms after ANALYZE.
