"""Application configuration.

Typed settings loaded from the environment via ``pydantic-settings``. A missing or
malformed value crashes the process at import time rather than surfacing as a 500
three hours later.

The database URL is assembled from parts rather than accepted whole, so a password
containing URI-reserved characters (``@``, ``:``, ``/``, ``#``) is percent-encoded
correctly instead of silently truncating the host. This is not hypothetical: it is
the first thing that went wrong during Phase 1 setup.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal
from urllib.parse import quote, urlsplit, urlunsplit

from pydantic import (
    AliasChoices,
    Field,
    PostgresDsn,
    ValidationInfo,
    computed_field,
    field_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Hosts that are local and therefore do not need — and cannot offer — TLS.
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "host.docker.internal", ""})

#: Query keys understood by libpq/psql but not by asyncpg. Present in the connection
#: strings that hosted Postgres providers hand out (Supabase, Neon, Render). asyncpg
#: raises on an unknown keyword, so they are stripped and TLS is configured explicitly
#: through :func:`app.db.session.build_engine` instead.
_LIBPQ_ONLY_QUERY_KEYS = frozenset(
    {"sslmode", "channel_binding", "pgbouncer", "options", "sslrootcert", "target_session_attrs"}
)


def _clean_query(query: str) -> str:
    """Drop libpq-only parameters from a DSN query string.

    Args:
        query: The raw ``key=value&…`` query.

    Returns:
        The query with :data:`_LIBPQ_ONLY_QUERY_KEYS` removed.
    """
    kept = [
        pair
        for pair in query.split("&")
        if pair and pair.split("=", 1)[0].lower() not in _LIBPQ_ONLY_QUERY_KEYS
    ]
    return "&".join(kept)


def _normalise_dsn(url: str, *, driver: str) -> str:
    """Re-scheme a connection string and strip parameters asyncpg cannot accept.

    A ``DATABASE_URL`` from a hosted provider arrives as ``postgres://`` or
    ``postgresql://`` and often carries ``?sslmode=require``. This rewrites the scheme
    to the requested SQLAlchemy driver and removes the libpq-only query keys, so the
    same variable works whether it came from Supabase, Render, or a hand-written string.

    Args:
        url: The provider's connection string.
        driver: ``"postgresql+asyncpg"`` for the app, ``"postgresql"`` for psql/tools.

    Returns:
        A normalised DSN.
    """
    parts = urlsplit(url)
    return urlunsplit((driver, parts.netloc, parts.path, _clean_query(parts.query), ""))


class Settings(BaseSettings):
    """Environment-backed application settings.

    Attributes:
        postgres_host: Database host. ``localhost`` on the developer's machine,
            ``host.docker.internal`` from inside the backend container (§3.3).
        argon2_*: Password-hashing parameters. The seed script hashes the four demo
            accounts with exactly these values, so Phase 2's verifier must read them
            from here. Hard-coding different parameters in Phase 2 would make every
            seeded account fail to authenticate.
        seed_random_seed: The deterministic seed for ``random.Random`` (§7.1).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "tps_db"
    postgres_user: str = "tps_app"
    postgres_password: str = "change_me_now"

    #: A whole connection string, which **overrides** the five ``POSTGRES_*`` parts when
    #: present. This is how a managed platform supplies the database — Render and Supabase
    #: both hand out a single ``DATABASE_URL``. Left unset locally, so the developer's
    #: ``POSTGRES_HOST=localhost`` path is completely unaffected (§ deployment).
    database_url_override: str | None = Field(default=None, validation_alias="DATABASE_URL")

    #: TLS to the database. ``None`` means "decide from the host": on for anything that
    #: is not localhost, off for local development. A managed database always requires it.
    db_ssl: bool | None = None
    #: Skip certificate verification. A last resort for a provider whose chain the system
    #: trust store does not carry; leave off unless a verified connection actually fails.
    db_ssl_insecure: bool = False

    app_timezone: str = "Africa/Kampala"

    argon2_time_cost: int = 3
    argon2_memory_cost: int = 65536
    argon2_parallelism: int = 4
    argon2_hash_length: int = 32
    argon2_salt_length: int = 16

    seed_random_seed: int = 20260722

    # --- Application ----------------------------------------------------
    environment: Literal["development", "staging", "production"] = "development"
    app_version: str = "1.0.0"
    #: Reads ``GIT_COMMIT`` or Render's auto-injected ``RENDER_GIT_COMMIT`` — whichever
    #: is set — so ``/version`` reports the deployed revision without extra wiring.
    git_commit: str = Field(
        default="unknown", validation_alias=AliasChoices("GIT_COMMIT", "RENDER_GIT_COMMIT")
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # --- JWT (B5) --------------------------------------------------------
    jwt_secret_key: str = Field(
        default="",
        description="HS256 signing key. Generate with `openssl rand -hex 32`. Never ship a default.",
    )
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    jwt_issuer: str = "tps.upf.go.ug"
    jwt_audience: str = "tps-api"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # --- CORS ------------------------------------------------------------
    cors_origins: str = Field(
        default="http://localhost:5173",
        description="Comma-separated allowlist. Never '*' — allow_credentials forbids it.",
    )

    # --- Rate limiting ---------------------------------------------------
    rate_limit_login: str = "10/minute"
    rate_limit_simulate: str = "30/minute"

    # --- Prediction engine ----------------------------------------------
    prediction_slow_warning_ms: int = Field(
        default=3000,
        description="Log a WARNING above this. NFR-01's ceiling is 10s; warn long before breaching.",
    )
    prediction_timeout_ms: int = Field(
        default=10_000,
        description=(
            "NFR-01's stated ceiling. Used as the threshold line on the System Health "
            "chart and to count breaches — a budget nothing measures is a wish."
        ),
    )

    # SQLAlchemy pool tuning (§7.6).
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_pre_ping: bool = True
    db_pool_recycle: int = 1800
    db_echo: bool = Field(default=False, description="Log every statement. Development only.")

    @field_validator("jwt_secret_key")
    @classmethod
    def _reject_weak_secret(cls, value: str, info: ValidationInfo) -> str:
        """Refuse to boot without a real signing key outside development.

        A missing or placeholder JWT secret is not a configuration inconvenience — it
        means every token in the system is forgeable. Failing at startup is the only
        safe behaviour; the alternative is a service that looks healthy and is not.

        Raises:
            ValueError: If the key is absent or too short.
        """
        environment = info.data.get("environment", "development")
        if len(value) < 32:
            if environment == "development":
                # Development gets a deterministic key so `docker compose up` works
                # before the human has read the README, but it is derived, obvious in
                # logs, and useless anywhere else.
                return "development-only-insecure-key-do-not-use-in-production-0000"
            raise ValueError(
                "JWT_SECRET_KEY must be at least 32 characters outside development. "
                "Generate one with: openssl rand -hex 32"
            )
        return value

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cors_origin_list(self) -> list[str]:
        """The CORS allowlist as a list.

        Returns:
            Trimmed, non-empty origins.
        """
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def is_production(self) -> bool:
        """True when running in production, which tightens error rendering."""
        return self.environment == "production"

    @property
    def effective_db_host(self) -> str:
        """The host the app will actually connect to, override or parts.

        Returns:
            The hostname, used to decide whether TLS is needed.
        """
        if self.database_url_override:
            return (urlsplit(self.database_url_override).hostname or "").lower()
        return self.postgres_host.lower()

    @property
    def use_db_ssl(self) -> bool:
        """Whether to open the database connection over TLS.

        Explicit ``db_ssl`` wins; otherwise TLS is on for any non-local host. A managed
        database (Supabase, Render) requires it, and a local one neither needs nor
        offers it.

        Returns:
            True to negotiate TLS.
        """
        if self.db_ssl is not None:
            return self.db_ssl
        return self.effective_db_host not in _LOCAL_HOSTS

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        """Async SQLAlchemy DSN for asyncpg.

        When ``DATABASE_URL`` is set it is normalised and used; otherwise the DSN is
        assembled from the five ``POSTGRES_*`` parts with the credentials
        percent-encoded.

        Returns:
            A ``postgresql+asyncpg://`` URL.
        """
        if self.database_url_override:
            return _normalise_dsn(self.database_url_override, driver="postgresql+asyncpg")
        user = quote(self.postgres_user, safe="")
        password = quote(self.postgres_password, safe="")
        return (
            f"postgresql+asyncpg://{user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sync_database_url(self) -> str:
        """Synchronous psycopg-style DSN.

        Alembic's async template does not need this, but ``psql`` invocations and
        the data-dictionary generator print it for humans to copy.

        Returns:
            A ``postgresql://`` URL.
        """
        if self.database_url_override:
            return _normalise_dsn(self.database_url_override, driver="postgresql")
        user = quote(self.postgres_user, safe="")
        password = quote(self.postgres_password, safe="")
        return (
            f"postgresql://{user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def dsn(self) -> PostgresDsn:
        """The DSN as a validated Pydantic type, so a malformed host fails at boot."""
        return PostgresDsn(self.sync_database_url)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton.

    Cached because reading and validating the environment on every access is waste,
    and because a single instance makes the values trivially injectable in tests.

    Returns:
        The validated :class:`Settings` instance.
    """
    return Settings()
