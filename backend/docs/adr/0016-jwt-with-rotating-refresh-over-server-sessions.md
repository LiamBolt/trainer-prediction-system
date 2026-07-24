# ADR-0016 — JWT access tokens with rotating refresh, over server-side sessions

**Status:** Accepted · 2026-07-23

## Context

The frontend is a separate origin from the API. Cookie-based sessions across origins mean
`SameSite=None; Secure`, a CSRF token scheme, and a CORS configuration that must be right
in three places. The alternative is a bearer token the client sends explicitly.

## Decision

**Short-lived JWT access tokens (15 minutes) plus long-lived, rotating, single-use
refresh tokens (7 days), organised into families with reuse detection.**

Refresh tokens are stored as SHA-256 hashes. A database read cannot yield a usable token.

## Rationale

**Why not server-side sessions.** They are genuinely simpler to revoke, which is their
main advantage and not a small one. Rejected because of the cross-origin cost above, and
because a session store is another piece of infrastructure to run for a system whose
deployment is deliberately minimal.

**Why the access token is short.** A JWT cannot be revoked — that is its defining
property. Fifteen minutes bounds the damage from a stolen token without making the user
sign in constantly.

**Why revocation is nonetheless immediate.** `get_current_user` **re-reads the account
status from the database on every request**. The token's claims are trusted for identity;
the account's *state* is not. Without this, a deactivated user stays authenticated until
their access token expires — up to fifteen minutes after an administrator revoked them,
which §6.10 explicitly forbids. There is a test that deactivates an account and asserts
that a token issued seconds earlier stops working immediately.

**Why rotation with reuse detection.** Each refresh issues a new token and revokes its
predecessor within a *family*. If an already-revoked token is presented, that is a signal
that a token was stolen: either the attacker or the legitimate user is replaying one the
other has already spent. The whole family is revoked, which signs the session out
everywhere and forces a fresh authentication.

This turns theft from a silent, indefinite compromise into a detectable event that
resolves itself the next time either party refreshes.

## Consequences

**Good.** No CSRF surface — a bearer token is not sent automatically by the browser.
Revocation is immediate despite the token being unrevokable, because state is checked
rather than assumed. Token theft is detected rather than merely mitigated.

**Costs.** The client must implement a refresh flow. The frontend currently has **none** —
its axios interceptor redirects to sign-in on any 401, which with a 15-minute access
token logs the user out every 15 minutes. This is recorded as a Phase 3 task and is the
single most user-visible consequence of this decision.

The algorithm is pinned on decode. Accepting the token's own `alg` header is the
`alg: none` vulnerability, and accepting `HS256` where `RS256` was expected is the key
confusion attack. Neither is possible when the verifier states the algorithm.
