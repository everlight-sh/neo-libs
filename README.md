# Neo libraries

Optional source packages for the Neo programming language: protocol, media and
web libraries written in Neo. Protocol implementations live here; the language,
ownership model, buffers, reactor, TLS, crypto and OS I/O come from the Neo
compiler and its standard library.

Each top-level directory with a `neo.toml` is one package. The packages are
plain source: there is no registry, no runtime package loader and no native
protocol dependency.

## Status

Every package implements the profile stated in the table below, and none of
them claims more than its row says. Every package except `document-store` has
a test program under `tests/`; `document-store` has none in this repository.

- Usable on their own within the stated profile: `jsonrpc`, `mcp` (stdio),
  `websocket` (client), `html`, `dom`, `jwt`, `oauth2`, `postgres`,
  `web-security`, `web-cache` and `document-store`.
- Narrow building blocks: `http-client` (pool bookkeeping only), `http-server`
  (streaming writer and SSE only), `providers` (one provider's text/tool
  profile), and the media and transport-security primitives `audio`, `rtp`,
  `opus-packet`, `stun` and `srtp`.

The media packages do not add up to a realtime voice stack. Opus packet parsing
is not an Opus audio codec, and STUN plus SRTP is not a WebRTC implementation.
The executable [readiness check](tests/readiness.py) deliberately fails
`--require full` while these gaps remain.

The cryptographic and security-sensitive code here and in the standard library
is experimental and has not had an independent security audit.

## Packages

All packages are independently versioned source packages, currently `0.1.0`.

| Package | Implemented profile | Main limitations |
|---|---|---|
| `jsonrpc` | JSON-RPC 2.0 envelopes, typed results/errors, duplicate-key rejection | No batch client |
| `mcp` | Sequential stdio initialization, tools/list pagination, tools/call, notifications, ping, deadlines and cancellation | No Streamable HTTP transport or concurrent request multiplexer |
| `providers` | OpenAI Responses text/tool SSE, typed HTTP driver, continuation preserving opaque reasoning/output items | No other providers, no realtime session adapters |
| `websocket` | Client upgrade, live TCP/TLS transport callbacks, masking, fragmentation, control frames, automatic pong/close, bounded messages | No compression, subprotocol negotiation, server upgrade/session API or reconnect policy |
| `http-client` | Origin-keyed bounded HTTP/1.1 keep-alive pool bookkeeping | Caller owns actual sockets, deadlines and eviction cleanup |
| `http-server` | Chunked HTTP/1.1 streaming writer and SSE encoding/flush | No routing or authentication API |
| [`web-security`](web-security/README.md) | Signed sessions with per-user revocation, CSRF, PBKDF2 passwords, file-locked rate limiting per account or client address | Application owns authorization and secret management |
| [`web-cache`](web-cache/README.md) | Atomic TTL/tagged file cache with a fixed slot count, value cap and expiry sweep; bounded revalidation queue | No distributed coordination |
| [`document-store`](document-store/README.md) | File-locked pure JSON transactions, fsync and atomic replacement | Local 16 MiB documents, no indexes or relational queries |
| [`postgres`](postgres/README.md) | Native v3 wire, SCRAM-SHA-256, parameterized text queries and pool bookkeeping | Caller-owned verified TCP/TLS; no ORM, COPY or binary formats; real PostgreSQL 17.11 checked locally |
| [`jwt`](jwt/README.md) | Native RS256/JWKS signature and OIDC code-flow ID-token validation | RSA 2048–4096/e65537 only; no signing, discovery or encrypted JWT |
| [`oauth2`](oauth2/README.md) | Authorization code, PKCE S256, browser/provider-bound state, optional OIDC ID token plus matching userinfo | No discovery, refresh-token lifecycle or real-provider validation yet |
| `audio` | PCM16 and G.711 μ-law/A-law, duration/rate and voiced-sample checks | No Opus PCM conversion or resampling engine |
| `rtp` | RTP framing and a bounded reorder/loss policy, checked against traces recorded from a Go reference implementation | One source per queue; authenticate before admitting packets |
| `opus-packet` | RFC 6716 TOC/frame packing validation and sample counts | **No PCM encoder/decoder, SILK/CELT, PLC or FEC** |
| `stun` | Binding request, short-term integrity, fingerprint, IPv4 XOR mapped address | No ICE agent, consent/restart or TURN relay |
| `srtp` | AES_CM_128_HMAC_SHA1_80 SRTP/SRTCP, KDR=0, one SSRC/direction, replay protection | No DTLS key establishment, MKI or header encryption |
| `html` | WHATWG tokenizer: tags, attributes, comments, doctypes, processing instructions, script data escapes, RCDATA/RAWTEXT/PLAINTEXT, CDATA in foreign content, the full named-reference table; 6,703/6,703 html5lib-tests tokenizer cases that start in the data state | Other initial states are driven by the tree builder, not tested standalone; parse errors are not reported |
| `dom` | DOM node store; WHATWG tree construction (all insertion modes, adoption agency, foster parenting, SVG/MathML, templates, fragments, customizable `<select>`): 1,947/1,958 html5lib tree-construction tests from web-platform-tests; CSS selectors (Selectors 4 subset) with querySelector/All and matches, checked against soupsieve; attribute and text mutation | No `<selectedcontent>` mirroring, declarative shadow roots, :has() or pseudo-elements; scripted tests need a JS engine |

See [API/profile notes](docs/API.md) and the [readiness matrix](docs/readiness.json).

## Using a package

Packages are consumed as path dependencies. A consumer names the package
directory and an exact version in its own `neo.toml`:

```toml
[package]
name="my-app"
version="0.1.0"
entry="src/main.neo"
[dependencies]
websocket={path="../neo-libs/websocket",version="0.1.0"}
```

and imports it by that dependency name, for example
`import "pkg:websocket" as ws`.

`neo pkg lock` writes `neo.lock`, which records each dependency's name, version,
path and the SHA-256 of its Neo sources and manifest. Dependencies are therefore
locked by content: `neo pkg verify` fails when a dependency's source no longer
matches the lock. Review and commit `neo.lock`. `neo pkg vendor` copies the
locked sources into the consumer so that it no longer needs the original paths.

Some packages depend on others (`mcp` on `jsonrpc`, `srtp` on `rtp`, `dom` on
`html`, `oauth2` on `jwt`). After changing a package's source, run
`neo pkg lock` in each dependent that keeps its own `neo.lock` (`mcp` for
`jsonrpc`, `srtp` for `rtp`) and then at the repository root.

## Standard-library foundations

The packages rely on these parts of the Neo standard library: a bounded
multi-descriptor reactor, scoped TCP listeners and UDP sockets,
cancellation-aware network I/O, process stdin half-close, private mutable
buffers, response headers and reusable HTTP framing. The reactor uses kernel
poll and explicit state machines; this is not an M:N async scheduler.

Crypto used by the packages is Neo SHA-1/HMAC-SHA1 for legacy protocol
compatibility, AES-128/CTR/GCM, SHA-384/512, P-256 ECDH/ECDSA with RFC 6979
signing and P-384 ECDSA verification. TLS 1.3 negotiates AES-128-GCM or
ChaCha20-Poly1305 with X25519, or P-256 after a HelloRetryRequest. It verifies
RSA-PSS or ECDSA (P-256, P-384) CertificateVerify, and certificate chains signed
with SHA-256, SHA-384 or SHA-512, including mixed RSA/EC issuers. Trust anchors
are explicit; `tls_system_roots` loads the system bundle. These implementations
are experimental and have not had an independent security audit.

## Build and test

With `neo` (0.2.4 or later) on `PATH`, from this directory:

```sh
neo pkg verify
python3 -m unittest discover -s tests -p 'test_*.py'
python3 tests/readiness.py
```

`NEO` selects another compiler binary. No Neo source checkout is needed; run
the language suite from a Neo checkout with `neo test`. Independent
test peers additionally require OpenSSL and libopus; these are test tools
and are never linked into or called by the Neo library implementations.

Some tests need optional inputs and are skipped without them:

- The html5lib conformance runs need `HTML5LIB_TESTS` (an html5lib-tests
  checkout) and `TREE_CONSTRUCTION_TESTS` (the web-platform-tests
  `html/syntax/parsing/resources` directory). The selector checks need
  beautifulsoup4, soupsieve and html5lib.
- The Opus packet framing test needs libopus.

The G.711 and RTP reorder expectations in `tests/fixtures/` were recorded from
a Go reference implementation that is not part of this repository; the tests
compare against the checked-in values. `srtp` is tested here against the
RFC 3711 key-derivation vectors and for sender nonce-reuse rejection only:
this repository has no interoperability test for SRTP/SRTCP packet protection,
decryption or replay handling.

A few Neo test programs are built and run individually rather than through
`unittest`: `tests/oauth2.neo`, `tests/web_foundations.neo`,
`tests/postgres_real.neo` and the wire peer `tests/postgres_peer.py`. The
package READMEs describe them.

Set `NEO_TARGET=aarch64-unknown-linux-gnu` inside a native Linux ARM64 tools
environment. Build outputs are separated by target. Set
`NEO_TARGET=x86_64-unknown-linux-gnu QEMU_RESERVED_VA=4G` for the recorded
x86-64 correctness checks under the VM's binfmt QEMU interpreter. An explicit
`NEO_RUNNER=qemu-x86_64` also works where that tool is installed in the test
container. Emulator results are not native performance data. The reservation
avoids the intermittent failures observed with automatic guest address placement;
no Neo source change was used to obtain the passing emulated results.

The packaging test vendors eleven of the libraries, deletes their original
source dependencies, then builds and runs a locked consumer. No registry service
is required. The application still needs the Neo compiler's standard library at
build time.

## Standalone scope

Linux executables use direct kernel calls, with no C source runtime, libc,
shared libraries, ELF interpreter or imported functions. Tests audit ELF headers
and undefined symbols and run selected executables in an empty chroot containing
only the executable. Kernel networking and random generation remain OS services.

On macOS, Apple's loader still requires a `libSystem` load command even though
these binaries import no C functions. The strict **no shared-library dependency**
claim is therefore Linux-specific. Python, LLVM, OpenSSL/libopus test tools,
certificates, DNS configuration and provider services are not bundled runtimes.
A deliberately configured external MCP tool is application functionality, not
an outsourced implementation of a Neo protocol.

## Evidence and remaining work

[Verification](docs/VERIFICATION.md) records completed tests and the Linux ELF
and empty-root audit.

A realtime voice stack would still need: a real pure-Neo Opus encoder and
decoder; DTLS handshake/authentication/exporter; complete ICE/TURN/SDP and
SCTP/data channels; WebRTC orchestration and browser/provider interoperability;
full-duplex pacing, backpressure, interruption/recovery. Also missing are an
HTTP transport for MCP and broader provider coverage. Wider TLS/PKIX/network
interoperability and security review also remain. Existing tests establish the
supported profiles and nothing beyond them.

## Licence

MIT. See [LICENSE](LICENSE); each package directory carries the same file.
