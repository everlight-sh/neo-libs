# Durable JSON documents

`document_store(path)` creates a checked handle. `document_read` returns a
`JsonResult`. `document_transaction(store,context,update)` holds a separate flock
file while invoking the pure `Fn(Context,Json)->JsonResult` update. A missing
document is passed as JSON null. Returning an error aborts the transaction.
Successful writes use fsync, atomic rename and parent-directory fsync; readers
observe a complete old or new document. A separate lock inode survives renames.

Documents are limited to 16 MiB. Keep the directory private and on a local
filesystem with the required locking/rename semantics. Application code owns
schema validation and migrations. This is not SQLite, a relational engine, an
indexed query service or a distributed store. The NeoKit dashboard HTTP tests
verify concurrent writes across two workers and persistence after restart.
