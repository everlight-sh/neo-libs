# Web security primitives

## Sessions

Signed HMAC-SHA256 sessions carry a subject, random CSRF token, issue time and
expiry. `web_session_create` requires a key of at least 32 bytes, fresh OS
randomness and a lifetime no greater than 30 days. Verification checks the
signature and expiry; it does not rotate keys. The cookie helper uses
`neokit_session`, HttpOnly, SameSite=Lax, Path=/ and caller-selected Secure.

Tokens are `v2.subject.csrf.issued.expiry.signature`. Tokens from earlier
versions (`v1`, with no issue time) still verify and count as issued at 0.

Revocation: `web_session_revoke(directory, subject, now)` records that every
session of `subject` issued before `now` is invalid. Call it at logout and on a
password change; a session created afterwards, even in the same millisecond,
stays valid, and the recorded time never moves backwards. The directory is
application-owned and holds one small file per revoked subject.
`web_session_read(request, key, directory)` verifies the cookie and then checks
that file; `web_session_current(session, directory)` does the same check for a
session verified elsewhere. A missing file means never revoked; an invalid
directory or any other read error fails closed.

## CSRF and passwords

`web_csrf` checks mutating requests against a configured exact Origin and the
signed session's CSRF token from a header/form. Application code must separately
authorize the subject and resource ownership.

Password encoding is salted PBKDF2-HMAC-SHA256 with a minimum of 600,000 rounds;
verification caps accepted rounds at 1,000,000.

## Rate limiting

`web_rate_limit(path, now, limit, window)` is a fixed-window counter in one
file, serialized with flock and failing closed on storage errors. Use it for an
account-wide or per-account limit.

`web_rate_limit_client(request, directory, now, limit, window)` limits each
client address separately. The address is `web_client_ip`'s: the peer, or
behind proxies listed in `NEO_TRUSTED_PROXIES` the forwarded client. IPv6
clients are counted per /64. Addresses are hashed into one of 65,536 counter
files in the directory, created as they are used, so two clients occasionally
share a counter. A sender with many addresses still gets many counters, so keep
an account-wide limit as well. `web_rate_limit_address` takes a parsed address
directly.

These primitives use Neo's standard-library crypto and OS randomness. They have
not received an independent security audit. `tests/web_foundations.neo` tests
vectors, signature tampering, expiry, revocation, CSRF, cookies and per-client
limits; the NeoKit dashboard checks actual password login, authorization and
persistence over HTTP.
