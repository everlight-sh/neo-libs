# Native PostgreSQL source package

`import "pkg:postgres"` after adding a locked path dependency, or import
`src/lib.neo` directly. Protocol code executes in Neo without libpq, OpenSSL,
subprocesses or another runtime.

Pass a caller-owned `HttpIO<C>` to `pg_connect(io,user,database,password,encrypted,deadline)`.
The caller opens/closes TCP or verified TLS and negotiates TLS before this call.
`encrypted=true` is an assertion by that caller, not a TLS handshake. Trust and
SCRAM-SHA-256 authentication are supported; cleartext password authentication is
permitted only for an encrypted transport. SCRAM uses ASCII passwords and
4,096–1,000,000 iterations, fresh randomness and server-proof verification.

`pg_query(connection,sql,params,deadline)` uses Parse/Bind/Describe/Execute/Sync.
Use `pg_text`, `pg_int` or `pg_null` for parameters; parameter values never become
SQL syntax. Take the returned connection for the next operation. SQL errors are
drained through ReadyForQuery so a healthy connection can be reused. Network,
malformed-frame or incomplete-result errors invalidate it. No query is replayed
automatically.

Rows are JSON objects with string or null values, preserving exact decimal and
large integer representations. Alias duplicate column names. There is one
outstanding operation per connection. Frames, columns and row output are bounded.
There is no MD5 auth, SASLprep for non-ASCII passwords, COPY, replication,
binary-column format, ORM, migration planner or cancellation protocol.

`pg_select`, `pg_insert`, `pg_update` and `pg_delete` build sealed `PGStatement`
values; execute them with `pg_execute`. Table/column identifiers are quoted and
restricted to 1–63 ASCII identifier characters. Values use `PGField`/`pg_field`
and remain separate Bind parameters. Filters combine null-safe equality with AND;
selects require a 1–10,000 row limit, and update/delete require predicates.
Inserts/updates/deletes return rows via RETURNING *. An invalid statement sends
no bytes and keeps its existing connection. This small builder has no joins,
ordering, aggregates, expression DSL or schema introspection; use parameterized
SQL directly for those cases.

`pg_pool`, `pg_pool_take` and `pg_pool_put` provide bounded pool bookkeeping.
Only healthy idle connections are accepted; transaction state cannot leak to the
next request. `pg_pool_take` removes expired entries and returns their transports
in `lease.expired`; the caller closes these, evicted and rejected transports and
owns concurrency synchronization. Thread the returned pool through every call.

`python3 tests/postgres_peer.py` builds and runs an independent Python wire peer:
SCRAM mutual proofs, rejected proof, fragmented frames, Unicode/injection-shaped
parameters, NULL, SQL error recovery and connection reuse. This is protocol-peer
validation. `tests/postgres_real.neo` additionally passes against PostgreSQL
17.11 (official 17-alpine image, SCRAM-SHA-256) from native macOS arm64 and Linux
aarch64 clients: parameterized CRUD, Unicode/injection-shaped data, SQL NULL,
exact int64, a 100 KB result, SQL-error recovery and transaction pool rejection.
These checks used a disposable local container, not production data. Build with
`neo build tests/postgres_real.neo -o build/postgres-real` and run
`build/postgres-real PORT` against a loopback server configured with test database
and user `test`, test password `pencil`, and SCRAM host authentication. TLS and
production-server deployment were not exercised by this real-server fixture.
