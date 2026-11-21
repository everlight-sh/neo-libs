# API and supported profiles

Import packages through a reviewed `neo.lock`, for example
`import "pkg:websocket" as ws`. Package manifests use exact versions and local
source paths. `neo pkg vendor` makes a consumer independent of those original
source paths.

## Ownership and transport

Callers retain scoped socket, TLS-session, cancellation and process owners in
an Arena. Typed transport captures carry generational `Ref<T>` values; stale
owners fail closed. Deadlines are absolute monotonic milliseconds. Resource
cleanup is checked with native before/after live-resource counts.

`HttpIO<C>` has typed `read(context, deadline)` and
`write(context, bytes, deadline)` callbacks. Standard adapters
`http_plain_transport` and `http_tls_transport` use actual TCP/TLS I/O. Callback
errors propagate; a successful short write is still an error. The bounded
connection pool does not own or silently retry side-effecting requests.

## MCP and provider streaming

`mcp_process_transport`, `mcp_new`, `mcp_initialize`, `mcp_tools_list`, and
`mcp_tools_call` implement sequential stdio RPC. Each operation returns its
updated client state and an explicit success/error result. JSON null is a valid
successful result. `mcp_take_notifications` drains retained notifications.
Remote error objects are retained separately from transport errors.

MCP frames are newline-delimited and bounded to 1 MiB. At most 64 notifications
can be retained and 256 interleaved messages processed for one response. Stderr
is drained during both blocked reads and writes. Initialization negotiates the
implemented 2025-06-18, 2025-03-26 or 2024-11-05 profiles. This does not implement
all optional MCP server capabilities.

The `providers` package normalizes Responses SSE events and builds requests,
tool outputs and continuations. Tool arguments must finish and validate before
execution; a completed response is required before a tool is marked ready.
Opaque completed items, including encrypted reasoning, survive continuation.
Limits: 32 calls, 128 KiB arguments per call, 1 MiB accumulated text. Stream
sequence and response identity checks reject corrupt/inconsistent input.
`tests/agent_path.neo` demonstrates HTTPS stream → real subprocess MCP tool →
continuation → final answer → atomic state snapshot against independent local
peers. It makes no paid/live model request.

## WebSocket

`websocket_new`, `websocket_feed`, `websocket_encode`, `websocket_request`,
`websocket_upgrade_valid` and `websocket_eof` are pure framing/handshake helpers.
The live client uses:

- `websocket_connect_io(io, host, path, headers, limit, deadline)`
- `websocket_send_io(state, opcode, payload, deadline)`
- `websocket_next_io(state, deadline)`

Each returns updated state. A receive result distinguishes `has_event`,
`closed`, and transport/protocol error. Ping is answered with a random-masked
pong; incoming close is echoed once, and clean completion requires that close
handshake. Control events remain observable. `1006` reports abnormal EOF;
`71` malformed framing/upgrade, `110` deadline and `125` cancellation follow
standard transport error conventions.

Message limits are caller-selected, 1 byte through 16 MiB. The live sender emits
complete messages, not application-generated continuation fragments. No
compression or subprotocol is negotiated. TLS trust/authentication is supplied
by the caller's `HttpIO`; plain TCP is not authenticated transport.

## Audio and RTP

`g711_decode(bytes, alaw)` and `g711_encode(pcm16, alaw)` convert signed
little-endian PCM16. The media tests exhaust μ-law encoding for all 65,536
PCM16 bit patterns and both 256-entry decode tables against values recorded
from a Go reference implementation. Matching G.711 media can pass through
without transcoding; arbitrary Opus input cannot.

RTP parse/encode preserves CSRC/extensions/payload and validates wire bounds.
`rtp_order_new/push/tick` use an eight-packet window, 40 ms missing-packet wait
and discontinuity reset beyond 128 packets. Duplicate/late/lost accounting
matches traces recorded from a Go reference implementation, including sequence
wraparound.

`opus_packet` parses all four RFC 6716 frame packing modes, CBR/VBR, padding and
frame spans. It limits a packet to 48 frames and 120 ms, and a frame to 1,275
bytes. This validates encoded packet structure only. No audio is synthesized.

## STUN and secure RTP

STUN supports short-term SHA-1 MESSAGE-INTEGRITY, CRC32 FINGERPRINT and IPv4
XOR-MAPPED-ADDRESS. Integrity/fingerprint duplicates and attributes after
MESSAGE-INTEGRITY other than a final fingerprint are rejected. Transaction IDs
are 12 bytes. Authentication requires the caller's expected transaction and
nonempty key; parsing alone does not authenticate a packet.

`srtp_new(arena, master_key, master_salt, ssrc)` returns an affine owner over
private mutable Buffer state. Keys/salt are 16/14 bytes. Use independent owners
for sending/receiving and for each SSRC. `srtp_encrypt/decrypt` and
`srtcp_encrypt/decrypt` implement AES_CM_128_HMAC_SHA1_80 with KDR=0. Key
derivation uses separate RFC 3711 labels for RTP and RTCP. The sender rejects
repeated/decreasing extended packet indices to prevent nonce reuse; a receiver
has a 64-packet replay window. Tags are authenticated before plaintext release
or replay-state commitment. Aliases through references share the same history.

SRTCP uses the encrypted E bit, a 31-bit index and separate replay history. The
compound RTCP structure is validated. These profiles do not establish keys or
peer identity: DTLS-SRTP is still missing. Do not use an unauthenticated STUN
packet or a caller-chosen key as proof of WebRTC peer authentication.

## Standard-library crypto

`p256_public`, `p256_public_valid`, `p256_ecdh`,
`ecdsa_p256_sign_sha256`, and `ecdsa_p256_verify_sha256` accept 32-byte private
scalars and uncompressed 65-byte public points. ECDSA signatures are canonical
DER; invalid/zero/out-of-order scalars and off-curve points are rejected.
Deterministic signing follows RFC 6979 SHA-256 with a bounded retry limit.
Field/order operations use sixteen 16-bit Montgomery limbs; point operations
use fixed scalar-bit iterations and mask selections. This is a source-level
design property, not an audited machine-code constant-time guarantee.

AES supports a 16-byte key, CTR and GCM with a 12-byte nonce/16-byte tag. GCM
verifies authentication before decrypting. Callers must never reuse a nonce
with the same key. The S-box uses fixed-work arithmetic rather than secret
indexed lookup tables. Payload/AAD limits are 16 MiB. SHA-1 exists solely for
legacy WebSocket/STUN/SRTP interoperability.

## Primary protocol references

- [WebSocket RFC 6455](https://www.rfc-editor.org/rfc/rfc6455)
- [MCP lifecycle 2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle)
- [Responses streaming events](https://developers.openai.com/api/reference/resources/responses/streaming-events)
- [RTP RFC 3550](https://www.rfc-editor.org/rfc/rfc3550)
- [Opus RFC 6716, packet framing only](https://www.rfc-editor.org/rfc/rfc6716#section-3)
- [STUN RFC 8489](https://www.rfc-editor.org/rfc/rfc8489) and [RFC 5769 vectors](https://www.rfc-editor.org/rfc/rfc5769)
- [SRTP RFC 3711](https://www.rfc-editor.org/rfc/rfc3711)
- [ECDSA deterministic signing RFC 6979](https://www.rfc-editor.org/rfc/rfc6979#appendix-A.2.5)
