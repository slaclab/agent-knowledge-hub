"""Tests for auth.py and JWT-related config.py validators.

Test matrix covers:
- T-JWT-01 through T-JWT-25 from the implementation plan (todo/016)
- Existing Path 2 (proxy secret) tests — unchanged
- Path 1 (Vouch headers) — updated to verify 401 (Path 1 removed per ADR-P10)

JWKS approach: tests mock _get_jwks_client() to return a fake client backed by a
locally-generated RSA key pair — no network call needed.
"""
import time

import pytest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from starlette.requests import Request


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_request(headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers or [],
    }
    return Request(scope)


# ---------------------------------------------------------------------------
# RSA key pair fixtures (module-scoped — generated once per test run)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def rsa_keypair():
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_pem, public_pem


@pytest.fixture(scope="module")
def alt_rsa_keypair():
    """A second unrelated key pair — used for wrong-key signature tests."""
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    return private_pem


def _make_jwt(private_pem: str, overrides: dict | None = None) -> str:
    import jwt

    payload: dict = {
        "name": "alice",
        "iss": "https://dex-dev.slac.stanford.edu",
        "aud": "s3df",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    if overrides:
        payload.update(overrides)
    return jwt.encode(payload, private_pem, algorithm="RS256")


# ---------------------------------------------------------------------------
# JWKS mock helpers
#
# PyJWKClient.get_signing_key_from_jwt() returns a PyJWK whose .key attribute
# is passed directly to pyjwt.decode(). We mock the whole client so tests
# never hit the network.
# ---------------------------------------------------------------------------

@contextmanager
def _mock_jwks(public_pem: str):
    """Patch _get_jwks_client to return a mock backed by public_pem.

    PyJWKClient.get_signing_key_from_jwt() returns a PyJWK whose .key is a
    cryptography RSA public key object (not a PEM string). Load it properly so
    pyjwt.decode() accepts it.
    """
    from cryptography.hazmat.primitives.serialization import load_pem_public_key

    pub_key = load_pem_public_key(public_pem.encode())
    mock_client = MagicMock()
    mock_signing_key = MagicMock()
    mock_signing_key.key = pub_key
    mock_client.get_signing_key_from_jwt.return_value = mock_signing_key
    with patch("app.auth._get_jwks_client", return_value=mock_client):
        yield mock_client


@contextmanager
def _mock_jwks_unreachable():
    """Patch _get_jwks_client so the key lookup always raises (network down / unknown kid)."""
    mock_client = MagicMock()
    mock_client.get_signing_key_from_jwt.side_effect = Exception("connection refused")
    with patch("app.auth._get_jwks_client", return_value=mock_client):
        yield


# ---------------------------------------------------------------------------
# config.py — @field_validator for internal_api_secret
# ---------------------------------------------------------------------------

class TestInternalApiSecretValidator:
    def test_none_passthrough(self):
        import app.config as cfg
        result = cfg.Settings._strip_internal_api_secret(None)
        assert result is None

    def test_valid_value_preserved(self):
        import app.config as cfg
        result = cfg.Settings._strip_internal_api_secret("abc123")
        assert result == "abc123"

    def test_trailing_newline_stripped(self):
        import app.config as cfg
        result = cfg.Settings._strip_internal_api_secret("abc123\n")
        assert result == "abc123"

    def test_whitespace_only_normalised_to_none(self):
        import app.config as cfg
        result = cfg.Settings._strip_internal_api_secret("   ")
        assert result is None

    def test_empty_string_normalised_to_none(self):
        import app.config as cfg
        result = cfg.Settings._strip_internal_api_secret("")
        assert result is None

    def test_leading_and_trailing_whitespace_stripped(self):
        import app.config as cfg
        result = cfg.Settings._strip_internal_api_secret("  mysecret  ")
        assert result == "mysecret"


# ---------------------------------------------------------------------------
# config.py — @field_validator for jwt_algorithm
# ---------------------------------------------------------------------------

class TestJwtAlgorithmValidator:
    def test_rs256_accepted(self):
        import app.config as cfg
        assert cfg.Settings._validate_jwt_algorithm("RS256") == "RS256"

    def test_lowercase_normalised(self):
        import app.config as cfg
        assert cfg.Settings._validate_jwt_algorithm("rs256") == "RS256"

    def test_hs256_rejected(self):
        """Security: algorithm confusion — HS256 must be rejected at config level."""
        import app.config as cfg
        with pytest.raises(ValueError, match="jwt_algorithm must be one of"):
            cfg.Settings._validate_jwt_algorithm("HS256")

    def test_none_alg_rejected(self):
        """Security: alg:none must be rejected at config level."""
        import app.config as cfg
        with pytest.raises(ValueError):
            cfg.Settings._validate_jwt_algorithm("none")


# ---------------------------------------------------------------------------
# auth.py — _validate_slac_jwt unit tests
# ---------------------------------------------------------------------------

class TestValidateSlacJwt:
    def _fn(self):
        from app.auth import _validate_slac_jwt
        return _validate_slac_jwt

    def test_valid_token_returns_user_id(self, rsa_keypair):
        """T-JWT-01: Valid RS256 JWT -> user_id="alice"."""
        import app.config as cfg
        private_pem, public_pem = rsa_keypair
        token = _make_jwt(private_pem)
        fn = self._fn()
        with _mock_jwks(public_pem), \
             patch.object(cfg.settings, "jwt_algorithm", "RS256"), \
             patch.object(cfg.settings, "jwt_issuer", "https://dex-dev.slac.stanford.edu"), \
             patch.object(cfg.settings, "jwt_audience", "s3df"):
            result = fn(token)
        assert result == "alice"

    def test_wrong_key_raises_401(self, rsa_keypair, alt_rsa_keypair):
        """T-JWT-02: JWT signed with wrong RSA key -> 401 (JWKS returns correct public key
        but signature doesn't verify)."""
        import app.config as cfg
        _, public_pem = rsa_keypair
        token = _make_jwt(alt_rsa_keypair)  # signed with the *other* key
        fn = self._fn()
        with _mock_jwks(public_pem), \
             patch.object(cfg.settings, "jwt_algorithm", "RS256"), \
             patch.object(cfg.settings, "jwt_issuer", "https://dex-dev.slac.stanford.edu"), \
             patch.object(cfg.settings, "jwt_audience", "s3df"):
            with pytest.raises(HTTPException) as exc:
                fn(token)
        assert exc.value.status_code == 401

    def test_expired_token_raises_401_with_message(self, rsa_keypair):
        """T-JWT-03: Expired JWT -> 401 with actionable 's3df login' message."""
        import app.config as cfg
        private_pem, public_pem = rsa_keypair
        token = _make_jwt(private_pem, overrides={"exp": int(time.time()) - 3600})
        fn = self._fn()
        with _mock_jwks(public_pem), \
             patch.object(cfg.settings, "jwt_algorithm", "RS256"), \
             patch.object(cfg.settings, "jwt_issuer", "https://dex-dev.slac.stanford.edu"), \
             patch.object(cfg.settings, "jwt_audience", "s3df"):
            with pytest.raises(HTTPException) as exc:
                fn(token)
        assert exc.value.status_code == 401
        assert "s3df login" in exc.value.detail

    def test_wrong_issuer_raises_401(self, rsa_keypair):
        """T-JWT-04: Wrong iss -> 401."""
        import app.config as cfg
        private_pem, public_pem = rsa_keypair
        token = _make_jwt(private_pem, overrides={"iss": "https://evil.example.com"})
        fn = self._fn()
        with _mock_jwks(public_pem), \
             patch.object(cfg.settings, "jwt_algorithm", "RS256"), \
             patch.object(cfg.settings, "jwt_issuer", "https://dex-dev.slac.stanford.edu"), \
             patch.object(cfg.settings, "jwt_audience", "s3df"):
            with pytest.raises(HTTPException) as exc:
                fn(token)
        assert exc.value.status_code == 401

    def test_jwks_unreachable_raises_401(self, rsa_keypair):
        """T-JWT-06 (replaced): JWKS endpoint unreachable -> 401 (not 500)."""
        import app.config as cfg
        private_pem, _ = rsa_keypair
        token = _make_jwt(private_pem)
        fn = self._fn()
        with _mock_jwks_unreachable():
            with pytest.raises(HTTPException) as exc:
                fn(token)
        assert exc.value.status_code == 401

    def test_missing_name_claim_raises_401(self, rsa_keypair):
        """T-JWT-14: Missing name claim -> 401 (MissingRequiredClaimError)."""
        import app.config as cfg
        import jwt

        private_pem, public_pem = rsa_keypair
        payload = {
            "iss": "https://dex-dev.slac.stanford.edu",
            "aud": "s3df",
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(payload, private_pem, algorithm="RS256")
        fn = self._fn()
        with _mock_jwks(public_pem), \
             patch.object(cfg.settings, "jwt_algorithm", "RS256"), \
             patch.object(cfg.settings, "jwt_issuer", "https://dex-dev.slac.stanford.edu"), \
             patch.object(cfg.settings, "jwt_audience", "s3df"):
            with pytest.raises(HTTPException) as exc:
                fn(token)
        assert exc.value.status_code == 401

    def test_empty_name_raises_401(self, rsa_keypair):
        """T-JWT-15: name="" -> 401."""
        import app.config as cfg
        private_pem, public_pem = rsa_keypair
        token = _make_jwt(private_pem, overrides={"name": ""})
        fn = self._fn()
        with _mock_jwks(public_pem), \
             patch.object(cfg.settings, "jwt_algorithm", "RS256"), \
             patch.object(cfg.settings, "jwt_issuer", "https://dex-dev.slac.stanford.edu"), \
             patch.object(cfg.settings, "jwt_audience", "s3df"):
            with pytest.raises(HTTPException) as exc:
                fn(token)
        assert exc.value.status_code == 401
        assert "name" in exc.value.detail

    def test_numeric_name_raises_401(self, rsa_keypair):
        """T-JWT-16: name=123 (non-string) -> 401."""
        import app.config as cfg
        private_pem, public_pem = rsa_keypair
        token = _make_jwt(private_pem, overrides={"name": 123})
        fn = self._fn()
        with _mock_jwks(public_pem), \
             patch.object(cfg.settings, "jwt_algorithm", "RS256"), \
             patch.object(cfg.settings, "jwt_issuer", "https://dex-dev.slac.stanford.edu"), \
             patch.object(cfg.settings, "jwt_audience", "s3df"):
            with pytest.raises(HTTPException) as exc:
                fn(token)
        assert exc.value.status_code == 401

    def test_wrong_audience_raises_401(self, rsa_keypair):
        """T-JWT-25: Wrong aud claim -> 401."""
        import app.config as cfg
        private_pem, public_pem = rsa_keypair
        token = _make_jwt(private_pem, overrides={"aud": "other-app"})
        fn = self._fn()
        with _mock_jwks(public_pem), \
             patch.object(cfg.settings, "jwt_algorithm", "RS256"), \
             patch.object(cfg.settings, "jwt_issuer", "https://dex-dev.slac.stanford.edu"), \
             patch.object(cfg.settings, "jwt_audience", "s3df"):
            with pytest.raises(HTTPException) as exc:
                fn(token)
        assert exc.value.status_code == 401

    def test_nbf_in_future_raises_401(self, rsa_keypair):
        """T-JWT-24: nbf in future -> 401."""
        import app.config as cfg
        private_pem, public_pem = rsa_keypair
        token = _make_jwt(private_pem, overrides={"nbf": int(time.time()) + 9999})
        fn = self._fn()
        with _mock_jwks(public_pem), \
             patch.object(cfg.settings, "jwt_algorithm", "RS256"), \
             patch.object(cfg.settings, "jwt_issuer", "https://dex-dev.slac.stanford.edu"), \
             patch.object(cfg.settings, "jwt_audience", "s3df"):
            with pytest.raises(HTTPException) as exc:
                fn(token)
        assert exc.value.status_code == 401

    def test_malformed_token_raises_401(self, rsa_keypair):
        """T-JWT-12: Malformed token (abc.def) -> get_signing_key_from_jwt raises -> 401."""
        import app.config as cfg
        _, public_pem = rsa_keypair
        fn = self._fn()
        # get_signing_key_from_jwt raises DecodeError on malformed tokens
        with _mock_jwks_unreachable():
            with pytest.raises(HTTPException) as exc:
                fn("abc.def")
        assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# auth.py — get_current_user paths
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    def _auth(self):
        from app.auth import get_current_user
        return get_current_user

    # Path 1 (Vouch headers) — REMOVED per ADR-P10; must return 401 ------------

    def test_vouch_idp_claims_name_returns_401(self):
        """T-JWT-20 / AC-13: Spoofed X-Vouch-Idp-Claims-Name -> 401 (Path 1 removed)."""
        import app.config as cfg
        get_current_user = self._auth()
        with patch.object(cfg.settings, "internal_api_secret", None), \
             patch.object(cfg.settings, "admin_users", ""), \
             _mock_jwks_unreachable():
            req = make_request([(b"x-vouch-idp-claims-name", b"bob@slac.stanford.edu")])
            with pytest.raises(HTTPException) as exc:
                get_current_user(req)
            assert exc.value.status_code == 401

    def test_vouch_user_header_returns_401(self):
        """Path 1 X-Vouch-User also removed — must return 401."""
        import app.config as cfg
        get_current_user = self._auth()
        with patch.object(cfg.settings, "internal_api_secret", None), \
             patch.object(cfg.settings, "admin_users", ""), \
             _mock_jwks_unreachable():
            req = make_request([(b"x-vouch-user", b"dave")])
            with pytest.raises(HTTPException) as exc:
                get_current_user(req)
            assert exc.value.status_code == 401

    # Path 2 — internal secret (unchanged) -------------------------------------

    def test_correct_secret_and_forwarded_user(self):
        import app.config as cfg
        get_current_user = self._auth()
        with patch.object(cfg.settings, "internal_api_secret", "mysecret"), \
             patch.object(cfg.settings, "admin_users", ""):
            req = make_request([
                (b"x-internal-secret", b"mysecret"),
                (b"x-forwarded-user", b"eve"),
            ])
            user = get_current_user(req)
            assert user.user_id == "eve"

    def test_wrong_secret_raises_401(self):
        import app.config as cfg
        get_current_user = self._auth()
        with patch.object(cfg.settings, "internal_api_secret", "mysecret"), \
             patch.object(cfg.settings, "admin_users", ""), \
             _mock_jwks_unreachable():
            req = make_request([
                (b"x-internal-secret", b"wrongsecret"),
                (b"x-forwarded-user", b"eve"),
            ])
            with pytest.raises(HTTPException) as exc:
                get_current_user(req)
            assert exc.value.status_code == 401

    def test_empty_secret_header_raises_401(self):
        import app.config as cfg
        get_current_user = self._auth()
        with patch.object(cfg.settings, "internal_api_secret", "mysecret"), \
             patch.object(cfg.settings, "admin_users", ""), \
             _mock_jwks_unreachable():
            req = make_request([
                (b"x-internal-secret", b""),
                (b"x-forwarded-user", b"frank"),
            ])
            with pytest.raises(HTTPException) as exc:
                get_current_user(req)
            assert exc.value.status_code == 401

    def test_secret_none_disables_path2(self):
        import app.config as cfg
        get_current_user = self._auth()
        with patch.object(cfg.settings, "internal_api_secret", None), \
             patch.object(cfg.settings, "admin_users", ""), \
             _mock_jwks_unreachable():
            req = make_request([
                (b"x-internal-secret", b"anything"),
                (b"x-forwarded-user", b"grace"),
            ])
            with pytest.raises(HTTPException) as exc:
                get_current_user(req)
            assert exc.value.status_code == 401

    def test_no_auth_headers_raises_401(self):
        """T-JWT-05: No Authorization header -> 401."""
        import app.config as cfg
        get_current_user = self._auth()
        with patch.object(cfg.settings, "internal_api_secret", None):
            with pytest.raises(HTTPException) as exc:
                get_current_user(make_request())
            assert exc.value.status_code == 401

    def test_path2_no_forwarded_user_falls_through_to_401(self):
        import app.config as cfg
        get_current_user = self._auth()
        with patch.object(cfg.settings, "internal_api_secret", "mysecret"), \
             patch.object(cfg.settings, "admin_users", ""), \
             _mock_jwks_unreachable():
            req = make_request([(b"x-internal-secret", b"mysecret")])
            with pytest.raises(HTTPException) as exc:
                get_current_user(req)
            assert exc.value.status_code == 401

    def test_admin_flag_via_path2(self):
        import app.config as cfg
        get_current_user = self._auth()
        with patch.object(cfg.settings, "internal_api_secret", "mysecret"), \
             patch.object(cfg.settings, "admin_users", "svc-account"):
            req = make_request([
                (b"x-internal-secret", b"mysecret"),
                (b"x-forwarded-user", b"svc-account"),
            ])
            user = get_current_user(req)
            assert user.is_admin is True

    # Path 3 — Bearer JWT -------------------------------------------------------

    def test_valid_bearer_jwt_returns_user(self, rsa_keypair):
        """T-JWT-01 / AC-1: Valid RS256 JWT -> User(user_id="alice")."""
        import app.config as cfg
        private_pem, public_pem = rsa_keypair
        token = _make_jwt(private_pem)
        get_current_user = self._auth()
        with patch.object(cfg.settings, "internal_api_secret", None), \
             patch.object(cfg.settings, "jwt_algorithm", "RS256"), \
             patch.object(cfg.settings, "jwt_issuer", "https://dex-dev.slac.stanford.edu"), \
             patch.object(cfg.settings, "jwt_audience", "s3df"), \
             patch.object(cfg.settings, "admin_users", ""), \
             _mock_jwks(public_pem):
            req = make_request([(b"authorization", f"Bearer {token}".encode())])
            user = get_current_user(req)
        assert user.user_id == "alice"

    def test_admin_via_bearer_jwt(self, rsa_keypair):
        """T-JWT-08 / AC-8: Valid JWT for user in admin_users -> is_admin=True."""
        import app.config as cfg
        private_pem, public_pem = rsa_keypair
        token = _make_jwt(private_pem)
        get_current_user = self._auth()
        with patch.object(cfg.settings, "internal_api_secret", None), \
             patch.object(cfg.settings, "jwt_algorithm", "RS256"), \
             patch.object(cfg.settings, "jwt_issuer", "https://dex-dev.slac.stanford.edu"), \
             patch.object(cfg.settings, "jwt_audience", "s3df"), \
             patch.object(cfg.settings, "admin_users", "alice"), \
             _mock_jwks(public_pem):
            req = make_request([(b"authorization", f"Bearer {token}".encode())])
            user = get_current_user(req)
        assert user.is_admin is True

    def test_path2_wins_over_bearer(self, rsa_keypair):
        """T-JWT-21: Internal secret + Bearer -> Path 2 wins (checked first)."""
        import app.config as cfg
        private_pem, public_pem = rsa_keypair
        token = _make_jwt(private_pem)
        get_current_user = self._auth()
        with patch.object(cfg.settings, "internal_api_secret", "mysecret"), \
             patch.object(cfg.settings, "jwt_algorithm", "RS256"), \
             patch.object(cfg.settings, "jwt_issuer", "https://dex-dev.slac.stanford.edu"), \
             patch.object(cfg.settings, "jwt_audience", "s3df"), \
             patch.object(cfg.settings, "admin_users", ""), \
             _mock_jwks(public_pem):
            req = make_request([
                (b"x-internal-secret", b"mysecret"),
                (b"x-forwarded-user", b"proxy-user"),
                (b"authorization", f"Bearer {token}".encode()),
            ])
            user = get_current_user(req)
        assert user.user_id == "proxy-user"

    def test_bearer_empty_token_falls_through_to_401(self):
        """T-JWT-11: 'Bearer ' (empty token after strip) -> 401, no JWKS call made."""
        import app.config as cfg
        get_current_user = self._auth()
        with patch.object(cfg.settings, "internal_api_secret", None):
            req = make_request([(b"authorization", b"Bearer ")])
            with pytest.raises(HTTPException) as exc:
                get_current_user(req)
            assert exc.value.status_code == 401

    def test_basic_auth_header_ignored(self):
        """T-JWT-13: 'Basic ...' (non-Bearer) -> skipped, 401."""
        import app.config as cfg
        get_current_user = self._auth()
        with patch.object(cfg.settings, "internal_api_secret", None):
            req = make_request([(b"authorization", b"Basic dXNlcjpwYXNz")])
            with pytest.raises(HTTPException) as exc:
                get_current_user(req)
            assert exc.value.status_code == 401

    def test_bearer_token_with_trailing_newline(self, rsa_keypair):
        """Token from ~/.s3df-access-token may have a trailing newline — strip() handles it."""
        import app.config as cfg
        private_pem, public_pem = rsa_keypair
        token = _make_jwt(private_pem)
        get_current_user = self._auth()
        with patch.object(cfg.settings, "internal_api_secret", None), \
             patch.object(cfg.settings, "jwt_algorithm", "RS256"), \
             patch.object(cfg.settings, "jwt_issuer", "https://dex-dev.slac.stanford.edu"), \
             patch.object(cfg.settings, "jwt_audience", "s3df"), \
             patch.object(cfg.settings, "admin_users", ""), \
             _mock_jwks(public_pem):
            req = make_request([(b"authorization", f"Bearer {token}\n".encode())])
            user = get_current_user(req)
        assert user.user_id == "alice"

    # get_optional_user — bad Bearer should return None (T-JWT-22) --------------

    def test_get_optional_user_bad_bearer_returns_none(self, rsa_keypair):
        """T-JWT-22: get_optional_user + bad Bearer -> None (not exception)."""
        import app.config as cfg
        from app.auth import get_optional_user
        with patch.object(cfg.settings, "internal_api_secret", None), \
             _mock_jwks_unreachable():
            req = make_request([(b"authorization", b"Bearer notavalidtoken")])
            result = get_optional_user(req)
        assert result is None


# ---------------------------------------------------------------------------
# auth.py — require_admin dependency
# ---------------------------------------------------------------------------

class TestRequireAdmin:
    def _dep(self):
        from app.auth import require_admin
        return require_admin

    def test_admin_user_passes_through(self):
        from app.auth import User
        require_admin = self._dep()
        user = User(user_id="alice", is_admin=True)
        result = require_admin(user)
        assert result is user

    def test_non_admin_raises_403(self):
        from app.auth import User
        require_admin = self._dep()
        user = User(user_id="bob", is_admin=False)
        with pytest.raises(HTTPException) as exc:
            require_admin(user)
        assert exc.value.status_code == 403
