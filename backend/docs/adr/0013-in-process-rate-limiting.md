# ADR-0013 — In-process rate limiting, and its stated limitation

**Status:** Accepted · 2026-07-23

## Context

Two endpoints need throttling:

- `POST /auth/login` — the only unauthenticated endpoint that accepts a guess. FR-01's
  five-attempt lockout protects one *account*; an attacker spraying one password across
  many usernames never trips a per-account counter, because every attempt is the first
  failure for a different account.
- `POST /predictions/simulate` — the Weight Studio's sliders. The frontend debounces
  them, but a debounce is a client-side courtesy and this endpoint runs the engine over
  the whole trainer pool.

## Decision

`slowapi` with **in-process** counters, keyed on the client address, with the limits in
settings (`10/minute` and `30/minute`).

The key prefers the left-most entry of `X-Forwarded-For` and falls back to the socket
address. Behind a reverse proxy the socket address is the *proxy's*, so without this
every user in a district shares one counter and the first burst locks out the lot.

`X-Forwarded-For` is client-controllable. That is acceptable **here** and would not be
for authorisation: the worst case is an attacker minting a fresh bucket per forged
address, which is no worse than having no limit — while ignoring the header entirely
breaks the system for legitimate users on day one.

## Consequences

**The limitation, stated plainly.** State lives in the process. With one API container
that is correct. **With several replicas, each holds its own counter and the effective
limit multiplies by the number of replicas** — three containers means an effective
30/minute, not 10.

This is a deliberate, documented trade rather than an oversight. The fix is a shared
Redis backend (`slowapi` supports one by configuration alone), and adding Redis to the
deployment for this alone, before horizontal scaling is actually needed, is the larger
mistake: an additional service to run, monitor, secure, and back up, for a system whose
measured load is one district's traffic.

**The trigger to revisit is deployment shape, not traffic volume.** The moment a second
API replica is introduced, this must change with it.

**Testing.** The suite disables the limiter globally — several hundred sign-ins from one
address in under a minute would otherwise trip it and make unrelated tests fail with
429s that look like authorisation bugs. `tests/integration/test_rate_limiting.py`
re-enables it deliberately and proves it fires, returns the RFC 9457 problem shape, and
keys correctly behind a proxy. Disabling in the fixture rather than lowering the limit in
configuration keeps the production value exactly as shipped.
