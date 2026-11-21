# Native JWT and OIDC validation

`jwt_verify_rs256(token, jwks)` verifies a compact JWS against caller-supplied
public keys and returns sealed, signature-verified JSON claims. It does **not**
validate application claims; use `oidc_verify` for the ID-token profile below.
All cryptography uses Neo's native RSA/SHA-256 implementation.

The supported profile is RS256, RSA 2048–4096 bits, exponent 65537, and a required
`kid` selecting exactly one JWK. Canonical unpadded base64url, unique immediate
JSON members, header/claim/key counts, token size (32 KiB) and JWKS size (64 KiB,
32 keys) are checked. Algorithm confusion, ambiguous key IDs, keys containing a private exponent,
unsupported critical/encoding headers and token-supplied key URLs are rejected.
Optional JWK `alg`, `use` and `key_ops` must authorize RS256 signature verification.

`oidc_verify(token, jwks, policy, access_token)` checks the signature before
accepting the configured exact HTTPS issuer, subject, client audience, authorized
party, browser-bound nonce, integer `exp`/`iat` and optional `nbf`. Multiple
audiences require matching `azp`; any supplied `azp` must match the client.
Optional `at_hash` is verified against the access token. `OIDCValidation` specifies
Unix **seconds**, skew 0–300 seconds and maximum issued-token age 1–86400 seconds.
This is the authorization-code flow's token-endpoint ID token; it does not
implement implicit/hybrid flow or `c_hash` validation.

Keys and expected policy must come from trusted configuration. This library
performs no HTTP requests or discovery. Callers enforce HTTPS certificate/name
validation, deadlines and response limits when obtaining JWKS. It does not
provide key persistence, JWT signing, encrypted JWT, other algorithms, arbitrary
access-token authorization, revocation or replay storage.

The profile follows [OIDC Core token validation](https://openid.net/specs/openid-connect-core-1_0.html#IDTokenValidation)
and [JWT claims](https://www.rfc-editor.org/rfc/rfc7519.html#section-4.1).
Run `python3 tests/test_jwt.py` from the libraries root. An independent OpenSSL
peer generates real RSA signatures; negative cases cover claims, signatures,
algorithm confusion, duplicate escaped members, key selection and encoding.
The suite also drives the OAuth authorization-code → ID-token/JWKS → matching
userinfo chain. No real provider credentials were used.
