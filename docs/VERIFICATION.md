# Verification — 2026-10-25

These results cover the profiles in this repository as they stood on that
date, when it held eleven packages. They do not establish an Opus audio codec,
a WebRTC implementation or a full realtime voice stack. The explicit
`python3 tests/readiness.py --require full` gate correctly returns exit 2.

| Check | Native macOS ARM64 | Native Linux ARM64 |
|---|---:|---:|
| Compiler/language unit tests | 101 passed | 101 passed |
| Language native cases | 36 passed | 36 passed |
| Complete language integration suite | Passed | Passed |
| Optional-library test suite | 40 passed | 40 passed |
| Separate offline-vendored consumer test | 1 passed | 1 passed |
| New executables audited for ELF interpreter/shared libraries/imports | — | 12 passed |
| Empty root containing only executable | — | 5 passed |

The language integration suite includes cryptographic vectors, P-256 arithmetic,
ECDH/ECDSA, independent TLS, network/cancellation, compiler/tooling, HTTP/SSR,
map/append/JSON and storage/application regressions. No unsafe
`--allow-unproven` compilation was used.

The library suite includes an actual native HTTPS → fragmented Responses SSE →
subprocess MCP call → continuation → final answer → atomic snapshot path. Local
independent Python TLS/MCP peers are test fixtures. No live provider credentials,
paid requests or production deployments are involved.

Media tests compare all 65,536 PCM16 μ-law encode inputs, both 256-entry G.711
decode tables and RTP reorder traces with values recorded from a Go reference
implementation that is not part of this repository. Opus packet framing uses
383 deterministic inputs (7 selected, 256 TOC variants and 120 random packets)
against independent libopus. This does not test PCM Opus encoding/decoding,
which is missing. In this run the SRTP/SRTCP tests interoperated with Pion SRTP
(`github.com/pion/srtp/v3`); those three differential tests are no longer part
of this repository, whose SRTP tests now cover RFC 3711 key derivation and
sender nonce-reuse rejection only.
P-256 uses exact RFC6979 vectors, independent Python integer arithmetic and
bidirectional Go ECDH/ECDSA checks. AES uses NIST vectors and Go differential
GCM cases, including no plaintext release after tag corruption.

The locked packaging test vendors all eleven source libraries, deletes the
original dependency source folders and then builds/runs the consumer. Its Neo
binary has no function imports.

The Linux ELF audit covers agent-path, codecs, providers, MCP, reactor,
network, media, STUN, UDP, SRTP/SRTCP, WebSocket and standalone crypto binaries.
Each has no `INTERP`, `NEEDED` or undefined symbols. Binary-only chroot cases
cover UDP, WebSocket SHA-1 handshake, G.711, AES/P-256 and a self-executing
reactor/process-half-close test.

Additional x86-64 Linux correctness checks passed under the VM's QEMU binfmt
interpreter: media 6 tests, SRTP/SRTCP 5 tests and P-256 RFC6979/ECDH/ECDSA
interop. `QEMU_RESERVED_VA=4G` was required to avoid intermittent failures seen
with automatic guest address placement. No Neo code change was made to obtain
these results. They are emulated checks, not native x86-64 performance results.

macOS still has Apple's required `libSystem` loader dependency with no imported
C functions. The strict no-shared-library runtime statement applies to Linux.

Machine-readable evidence: [verification.json](verification.json) and the
[ELF and empty-root audit](dependency-audit-linux-arm64.json).
Detailed test/build logs are not published; their hashes are retained in the
verification file.

Reproduce the language suite from a Neo checkout with `neo test`. From this
repository, run `python3 -m unittest discover -s tests -p 'test_*.py'`. On
native Linux ARM64, set `NEO_TARGET=aarch64-unknown-linux-gnu` and run
`python3 tests/audit_linux.py` as root in a disposable test container after the
library suite. The root permission is for chroot isolation, not a production
install.
