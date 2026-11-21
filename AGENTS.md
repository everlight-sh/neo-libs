# Optional Neo libraries

Keep domain protocols here as separately versioned source packages. They must
compile into standalone C-free Linux executables; do not call native codecs,
OpenSSL, libc, shell wrappers or language subprocesses to implement a protocol.
Python, Go, OpenSSL and browser tools may be independent test peers only.

State exact supported protocol profiles and remaining limitations; never label
an empty package, mock or partial codec full protocol support.

Language, compiler and standard-library changes belong in the Neo repository,
not here.

Consumers lock packages by content: any change to a package's `.neo` sources or
`neo.toml` changes its hash. After such a change, run `neo pkg lock` in each
dependent that keeps its own `neo.lock` (`mcp` for `jsonrpc`, `srtp` for `rtp`)
and then at the repository root, and review the resulting lock diff.
