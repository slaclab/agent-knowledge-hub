import pytest
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request


def make_request(headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers or [],
    }
    return Request(scope)


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
# auth.py — get_current_user paths
# ---------------------------------------------------------------------------

class TestGetCurrentUser:
    def _auth(self):
        from app.auth import get_current_user
        return get_current_user

    def test_dev_mode_returns_dev_user(self):
        import app.config as cfg
        get_current_user = self._auth()
        with patch.object(cfg.settings, "auth_mode", "dev"), \
             patch.object(cfg.settings, "dev_user", "alice"), \
             patch.object(cfg.settings, "admin_users", ""):
            user = get_current_user(make_request())
            assert user.user_id == "alice"
            assert user.is_admin is False

    def test_dev_mode_no_dev_user_raises_500(self):
        import app.config as cfg
        get_current_user = self._auth()
        with patch.object(cfg.settings, "auth_mode", "dev"), \
             patch.object(cfg.settings, "dev_user", None):
            with pytest.raises(HTTPException) as exc:
                get_current_user(make_request())
            assert exc.value.status_code == 500

    def test_dev_mode_admin_flag(self):
        import app.config as cfg
        get_current_user = self._auth()
        with patch.object(cfg.settings, "auth_mode", "dev"), \
             patch.object(cfg.settings, "dev_user", "carol"), \
             patch.object(cfg.settings, "admin_users", "carol"):
            user = get_current_user(make_request())
            assert user.is_admin is True

    # Path 1 — Vouch headers
    def test_vouch_idp_claims_name(self):
        import app.config as cfg
        get_current_user = self._auth()
        with patch.object(cfg.settings, "auth_mode", "vouchproxy"), \
             patch.object(cfg.settings, "internal_api_secret", None), \
             patch.object(cfg.settings, "admin_users", ""):
            req = make_request([(b"x-vouch-idp-claims-name", b"bob@slac.stanford.edu")])
            user = get_current_user(req)
            assert user.user_id == "bob@slac.stanford.edu"

    def test_vouch_user_fallback(self):
        import app.config as cfg
        get_current_user = self._auth()
        with patch.object(cfg.settings, "auth_mode", "vouchproxy"), \
             patch.object(cfg.settings, "internal_api_secret", None), \
             patch.object(cfg.settings, "admin_users", ""):
            req = make_request([(b"x-vouch-user", b"dave")])
            user = get_current_user(req)
            assert user.user_id == "dave"

    # Path 2 — internal secret
    def test_correct_secret_and_forwarded_user(self):
        import app.config as cfg
        get_current_user = self._auth()
        with patch.object(cfg.settings, "auth_mode", "vouchproxy"), \
             patch.object(cfg.settings, "internal_api_secret", "mysecret"), \
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
        with patch.object(cfg.settings, "auth_mode", "vouchproxy"), \
             patch.object(cfg.settings, "internal_api_secret", "mysecret"), \
             patch.object(cfg.settings, "admin_users", ""):
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
        with patch.object(cfg.settings, "auth_mode", "vouchproxy"), \
             patch.object(cfg.settings, "internal_api_secret", "mysecret"), \
             patch.object(cfg.settings, "admin_users", ""):
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
        with patch.object(cfg.settings, "auth_mode", "vouchproxy"), \
             patch.object(cfg.settings, "internal_api_secret", None), \
             patch.object(cfg.settings, "admin_users", ""):
            req = make_request([
                (b"x-internal-secret", b"anything"),
                (b"x-forwarded-user", b"grace"),
            ])
            with pytest.raises(HTTPException) as exc:
                get_current_user(req)
            assert exc.value.status_code == 401

    def test_no_auth_headers_raises_401(self):
        import app.config as cfg
        get_current_user = self._auth()
        with patch.object(cfg.settings, "auth_mode", "vouchproxy"), \
             patch.object(cfg.settings, "internal_api_secret", None):
            with pytest.raises(HTTPException) as exc:
                get_current_user(make_request())
            assert exc.value.status_code == 401

    def test_path2_no_forwarded_user_falls_through_to_401(self):
        import app.config as cfg
        get_current_user = self._auth()
        with patch.object(cfg.settings, "auth_mode", "vouchproxy"), \
             patch.object(cfg.settings, "internal_api_secret", "mysecret"), \
             patch.object(cfg.settings, "admin_users", ""):
            # Correct secret but no X-Forwarded-User and no Vouch headers
            req = make_request([(b"x-internal-secret", b"mysecret")])
            with pytest.raises(HTTPException) as exc:
                get_current_user(req)
            assert exc.value.status_code == 401

    def test_path1_wins_over_path2_when_both_present(self):
        """Vouch header takes priority even when X-Internal-Secret is also present."""
        import app.config as cfg
        get_current_user = self._auth()
        with patch.object(cfg.settings, "auth_mode", "vouchproxy"), \
             patch.object(cfg.settings, "internal_api_secret", "mysecret"), \
             patch.object(cfg.settings, "admin_users", ""):
            req = make_request([
                (b"x-vouch-idp-claims-name", b"vouch-user@example.com"),
                (b"x-internal-secret", b"mysecret"),
                (b"x-forwarded-user", b"proxy-user"),
            ])
            user = get_current_user(req)
            assert user.user_id == "vouch-user@example.com"

    def test_admin_flag_via_vouch_path(self):
        import app.config as cfg
        get_current_user = self._auth()
        with patch.object(cfg.settings, "auth_mode", "vouchproxy"), \
             patch.object(cfg.settings, "internal_api_secret", None), \
             patch.object(cfg.settings, "admin_users", "admin@example.com"):
            req = make_request([(b"x-vouch-idp-claims-name", b"admin@example.com")])
            user = get_current_user(req)
            assert user.is_admin is True

    def test_admin_flag_via_path2(self):
        import app.config as cfg
        get_current_user = self._auth()
        with patch.object(cfg.settings, "auth_mode", "vouchproxy"), \
             patch.object(cfg.settings, "internal_api_secret", "mysecret"), \
             patch.object(cfg.settings, "admin_users", "svc-account"):
            req = make_request([
                (b"x-internal-secret", b"mysecret"),
                (b"x-forwarded-user", b"svc-account"),
            ])
            user = get_current_user(req)
            assert user.is_admin is True


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
