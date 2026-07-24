"""Password hashing and JWT issue/verify.

Two responsibilities, both of which fail silently and catastrophically if got wrong:

1. **Argon2id** password hashing with **exactly** Phase 1's seed parameters (B6). The
   parameters come from settings rather than being written inline, because if they
   diverge from the seed's, every demo account fails to authenticate with a message
   indistinguishable from a wrong password.
2. **JWT** issue and verification. The algorithm is taken from configuration and
   asserted on decode — the token's own ``alg`` header is **never** trusted to select
   the verification method, which is the classic JWT forgery.
"""

from __future__ import annotations

import datetime
import hashlib
import secrets
import uuid
from typing import Any, Final, Literal

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from jose import JWTError, jwt

from app.core.config import Settings, get_settings
from app.core.exceptions import UnauthorisedError

TokenType = Literal["access", "refresh"]

#: Claim carrying the token kind, so an access token cannot be presented at the
#: refresh endpoint and vice versa.
TOKEN_TYPE_CLAIM: Final = "typ"


def _hasher(settings: Settings) -> PasswordHasher:
    """Build the Argon2id hasher from configuration.

    Args:
        settings: Application settings.

    Returns:
        A hasher whose parameters match the seed's exactly (B6).
    """
    return PasswordHasher(
        time_cost=settings.argon2_time_cost,
        memory_cost=settings.argon2_memory_cost,
        parallelism=settings.argon2_parallelism,
        hash_len=settings.argon2_hash_length,
        salt_len=settings.argon2_salt_length,
    )


def hash_password(password: str, settings: Settings | None = None) -> str:
    """Hash a password with Argon2id.

    Argon2id over bcrypt: it is memory-hard, so an attacker's GPU advantage is far
    smaller, and it has no 72-byte silent truncation. See ADR-0013.

    Args:
        password: The plaintext password.
        settings: Optional settings override.

    Returns:
        The encoded hash, including its parameters and salt.
    """
    return _hasher(settings or get_settings()).hash(password)


def verify_password(password: str, encoded_hash: str, settings: Settings | None = None) -> bool:
    """Verify a password against an Argon2id hash.

    Returns ``False`` rather than raising on mismatch, so callers cannot accidentally
    distinguish "wrong password" from "no such user" in their control flow — that
    distinction is what makes a login endpoint a user-enumeration oracle.

    Args:
        password: The candidate plaintext.
        encoded_hash: The stored hash.
        settings: Optional settings override.

    Returns:
        True if the password matches.
    """
    try:
        return _hasher(settings or get_settings()).verify(encoded_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(encoded_hash: str, settings: Settings | None = None) -> bool:
    """Whether a stored hash was made with weaker parameters than current policy.

    Lets the cost be raised over time: on the next successful sign-in the hash is
    silently upgraded, without forcing a password reset on anybody.

    Args:
        encoded_hash: The stored hash.
        settings: Optional settings override.

    Returns:
        True if the hash should be recomputed.
    """
    try:
        return _hasher(settings or get_settings()).check_needs_rehash(encoded_hash)
    except InvalidHashError:
        return True


# --- Refresh tokens --------------------------------------------------------


def generate_refresh_token() -> str:
    """Generate a cryptographically random opaque refresh token.

    Opaque rather than a JWT: a refresh token's whole purpose is to be revocable, and
    revocation requires a database lookup regardless, so signing buys nothing and
    would only tempt a reader into trusting its claims without that lookup.

    Returns:
        A URL-safe random string.
    """
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """Hash a refresh token for storage.

    SHA-256, not Argon2. The input is 384 bits of entropy from a CSPRNG, so there is
    no dictionary to attack and no need for a slow KDF — and the refresh path would
    otherwise pay Argon2's 250 ms on every rotation. A leaked database still yields no
    usable session, which is the property that matters.

    Args:
        token: The plaintext token.

    Returns:
        Lowercase hex digest.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_token_family() -> uuid.UUID:
    """Return a new rotation family identifier.

    Every token descended from one sign-in shares a family. Presenting an already
    rotated token means it was captured, so the entire family is revoked (B5).
    """
    return uuid.uuid4()


# --- JWT -------------------------------------------------------------------


def create_access_token(
    *,
    user_id: int,
    username: str,
    role: str,
    trainer_id: int | None,
    now: datetime.datetime,
    settings: Settings | None = None,
) -> tuple[str, datetime.datetime]:
    """Issue a short-lived access token.

    ``role`` and ``trainer_id`` are embedded so ordinary authorisation needs no
    database round trip. The cost is that a role change does not take effect until the
    token expires — at most fifteen minutes, which §6.10 requires the API to state
    plainly rather than paper over.

    Args:
        user_id: Subject.
        username: For log correlation and audit context.
        role: The user's role name at issue time.
        trainer_id: Linked trainer id, or None for non-trainer accounts.
        now: Injected clock reading.
        settings: Optional settings override.

    Returns:
        The encoded token and its expiry.
    """
    config = settings or get_settings()
    expires_at = now + datetime.timedelta(minutes=config.access_token_expire_minutes)
    claims: dict[str, Any] = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "trainerId": trainer_id,
        TOKEN_TYPE_CLAIM: "access",
        "iss": config.jwt_issuer,
        "aud": config.jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": uuid.uuid4().hex,
    }
    token = jwt.encode(claims, config.jwt_secret_key, algorithm=config.jwt_algorithm)
    return token, expires_at


def decode_access_token(token: str, settings: Settings | None = None) -> dict[str, Any]:
    """Decode and validate an access token.

    Validates the signature, expiry, issuer, and audience, and pins the algorithm to
    the configured one. Accepting the token's own ``alg`` header would let an attacker
    present ``alg: none`` — or downgrade an RS256 deployment to HS256 with the public
    key as the shared secret.

    Args:
        token: The encoded token.
        settings: Optional settings override.

    Returns:
        The validated claims.

    Raises:
        UnauthorisedError: If the token is invalid, expired, or not an access token.
    """
    config = settings or get_settings()
    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            config.jwt_secret_key,
            algorithms=[config.jwt_algorithm],
            issuer=config.jwt_issuer,
            audience=config.jwt_audience,
        )
    except JWTError as exc:
        raise UnauthorisedError("Your session is not valid. Please sign in again.") from exc

    if claims.get(TOKEN_TYPE_CLAIM) != "access":
        raise UnauthorisedError("Your session is not valid. Please sign in again.")
    return claims


def generate_temporary_password() -> str:
    """Generate a temporary password for a newly created or reset account.

    Returned to the administrator exactly once, in the response body, and never
    logged (§6.10). Mixed case, digits, and a symbol so it satisfies any downstream
    policy without the administrator having to think about it.

    Returns:
        A random 14-character password.
    """
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    body = "".join(secrets.choice(alphabet) for _ in range(12))
    return f"{body}@{secrets.choice('23456789')}"
