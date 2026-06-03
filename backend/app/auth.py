from __future__ import annotations

import hmac
import logging
from dataclasses import dataclass

import jwt as pyjwt
from jwt import PyJWKClient
from jwt.exceptions import ExpiredSignatureError, PyJWTError

from fastapi import HTTPException, Request, status

from app.config import settings

logger = logging.getLogger(__name__)

# Module-level JWKS client — lazy-initialised on first Bearer request.
# Keys are cached in memory; PyJWKClient re-fetches automatically when it
# encounters a kid it doesn't recognise (i.e. after a Dex key rotation).
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(settings.jwt_jwks_uri, cache_keys=True)
    return _jwks_client


@dataclass
class User:
    user_id: str
    is_admin: bool = False


def _validate_slac_jwt(token: str) -> str:
    """Validate a SLAC RS256 JWT via JWKS and return the ``name`` claim as user_id.

    The signing key is fetched from ``settings.jwt_jwks_uri`` on first use and
    cached in memory. If Dex rotates its signing key, PyJWKClient re-fetches
    automatically when it encounters an unknown ``kid``.

    Raises:
        HTTPException(401): bad signature, expired, wrong issuer/audience,
            missing/invalid ``name`` claim, or JWKS fetch failure.
    """
    try:
        client = _get_jwks_client()
        signing_key = client.get_signing_key_from_jwt(token)
    except Exception as exc:
        # Covers: PyJWKClientConnectionError, PyJWKSetError, DecodeError (malformed token)
        logger.warning("JWKS key fetch / token decode failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    try:
        payload = pyjwt.decode(
            token,
            signing_key.key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["exp", "iss", "name"]},
        )
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired. Re-run 's3df login' to refresh your session.",
        )
    except PyJWTError as exc:
        logger.debug("JWT validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT missing valid 'name' claim",
        )
    return name.strip()


def get_current_user(request: Request) -> User:
    """FastAPI dependency — extracts identity from Bearer JWT or Next.js proxy secret."""
    # DEBUG: log all incoming headers (mask secrets)
    safe_headers = {
        k: ("[REDACTED]" if k.lower() in ("x-internal-secret", "authorization") else v)
        for k, v in request.headers.items()
    }
    logger.debug("AUTH get_current_user headers: %s", safe_headers)

    # Path 1 (VouchProxy headers) is intentionally removed — see ADR-P10.

    # Path 2: Next.js proxy — requires matching internal secret
    # X-Forwarded-User is only trusted after the secret check passes.
    # If internal_api_secret is not configured (None), this path is disabled entirely.
    if settings.internal_api_secret is not None:
        incoming_secret = request.headers.get("X-Internal-Secret", "")
        secret_match = hmac.compare_digest(incoming_secret, settings.internal_api_secret)
        forwarded_user = request.headers.get("X-Forwarded-User", "")
        logger.debug(
            "AUTH path2 check: secret_present=%s secret_match=%s forwarded_user=%r",
            bool(incoming_secret),
            secret_match,
            forwarded_user,
        )
        if secret_match:
            if forwarded_user:
                logger.debug("AUTH path=2 (internal secret) user=%s", forwarded_user)
                return User(
                    user_id=forwarded_user,
                    is_admin=forwarded_user in settings.admin_user_set,
                )
            else:
                logger.warning(
                    "AUTH path2 secret matched but X-Forwarded-User is empty — "
                    "frontend did not inject the user header. Received headers: %s",
                    {k: v for k, v in request.headers.items()
                     if k.lower().startswith("x-")},
                )
    else:
        logger.debug("AUTH path2 disabled: internal_api_secret not configured")

    # Path 3: Bearer JWT — CLI tools with a SLAC-issued token from ~/.s3df-access-token
    auth_header = request.headers.get("Authorization", "")
    logger.debug("AUTH path3 check: auth_header_present=%s", bool(auth_header))
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()  # len("Bearer ") == 7; strip whitespace/newlines
        if token:
            logger.debug("AUTH path=3 (Bearer JWT) attempting validation")
            user_id = _validate_slac_jwt(token)
            return User(user_id=user_id, is_admin=user_id in settings.admin_user_set)

    logger.warning(
        "AUTH no path matched — returning 401. "
        "internal_api_secret_configured=%s incoming_secret_present=%s "
        "x_forwarded_user=%r auth_header_present=%s",
        settings.internal_api_secret is not None,
        bool(request.headers.get("X-Internal-Secret", "")),
        request.headers.get("X-Forwarded-User", ""),
        bool(request.headers.get("Authorization", "")),
    )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )


def get_optional_user(request: Request) -> User | None:
    """FastAPI dependency — returns User if authenticated, None otherwise."""
    try:
        return get_current_user(request)
    except HTTPException:
        return None


def require_admin(user: User) -> User:
    """FastAPI dependency — requires the caller to have admin rights."""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
