# ADR-0017 — The API in Docker, PostgreSQL on the host

**Status:** Accepted · 2026-07-23

## Context

Phase 1 installed PostgreSQL 18.4 natively on the host, deliberately: the database
outlives the application, holds the data that matters, and is the thing a system
administrator will manage with the tools they already know. The API is stateless and
disposable, which is exactly what a container is good at.

So the deployment is **mixed**, and the two halves have to find each other.

## Decision

The API runs in a container. It reaches the host's PostgreSQL through
`host.docker.internal`, mapped in `docker-compose.yml` with:

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

`host-gateway` is a Docker-provided alias that resolves to the host from inside the
container. On Linux this line is **required** — `host.docker.internal` exists by default
only on Docker Desktop for macOS and Windows.

Three host-side settings must match, and all three are documented in `README.md`:

1. `listen_addresses` in `postgresql.conf` must include the Docker bridge address
   (`172.17.0.1`), not only `localhost`.
2. `pg_hba.conf` must permit `scram-sha-256` from the Docker subnet (`172.16.0.0/12`).
3. The host firewall must allow 5432 from that subnet.

## Consequences

**Good.** The database is managed with ordinary host tooling — `pg_dump`, the packaged
service, the administrator's existing backup routine. The API redeploys without touching
data. There is no database container whose volume can be destroyed by
`docker compose down -v`, which is a real and common way to lose a development database.

**Costs.** Three host-side settings that a fresh machine will not have. Each has a
distinctive failure: no `listen_addresses` gives *connection refused*; no `pg_hba.conf`
entry gives *no pg_hba.conf entry for host*; no `extra_hosts` gives *could not translate
host name*. All three are in the README's troubleshooting section with the exact symptom,
because the symptom is what someone searches for.

`POSTGRES_HOST` differs between the two ways of running the API — `localhost` on the host,
`host.docker.internal` in the container — which is why it is an environment variable with
no default that works in both.

**Rejected alternative: PostgreSQL in a container too.** Simpler to start and a single
`docker compose up`. Rejected because it makes the database's lifecycle a property of the
application's deployment, which for a system of record is the wrong way round.
