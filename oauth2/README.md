# OAuth2 authorization code and PKCE

Pure Neo source: authorization code + PKCE S256, a 10-minute signed challenge
cookie, browser-bound state, and identity from authenticated HTTPS userinfo.
`oauth_provider` validates fixed provider/client/redirect configuration;
`oauth_begin` creates the authorization URL and cookie. `oauth_callback` verifies
state, cookie, expiry, provider/client/redirect binding and returns a sealed code
and verifier. `oauth_exchange` uses a caller-supplied `OAuthHTTP` callback for the
token POST and Bearer-authenticated userinfo GET. That callback must verify TLS
certificates and names, enforce deadlines/response bounds and avoid forwarding
credentials through redirects. NeoKit supplies a native system-trust driver.

HTTPS provider endpoints are mandatory. Callback URLs require HTTPS except
localhost/127.0.0.1 development. Client secrets are form-encoded for providers
supporting client_secret_post; HTTP Basic client authentication is not supplied.
The stable subject defaults to `sub`; `oauth_subject_claim` selects another
provider-specific identifier. Email alone is not a verified identity. Caller
code scopes accounts by configured issuer plus subject, establishes its own
session and clears the challenge cookie after use.

`oauth_oidc(provider, issuer, jwks_url)` enables the native RS256 OIDC
[ID-token validator](../jwt/README.md). The configured issuer and JWKS URL must
be HTTPS; scope must include `openid`, and the subject claim must be `sub`.
The signed state challenge supplies an unpredictable browser-bound nonce. The
token response must contain a valid ID token, and authenticated userinfo must
return the same subject. Every login fetches the fixed JWKS URL; token-supplied
URLs are never followed. This supports key rotation without a persistent cache,
but adds a network request per login. The configured issuer becomes the account
namespace. Tokens have a 30-second skew and one-hour maximum issued age.

There is no discovery, refresh-token storage/rotation, implicit/hybrid/device
flow, durable JWKS cache or provider-specific account linking.
`tests/oauth2.neo` exercises PKCE, expiry, tampering, binding, code encoding and
userinfo handling against an independent typed callback fixture. No real provider
account was used in these checks. `python3 tests/test_jwt.py` also exercises the
complete OIDC exchange with independent OpenSSL-signed tokens and failure cases.
