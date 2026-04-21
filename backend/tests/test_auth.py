import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

import os


def make_client(auth_mode="dev", dev_user="testuser", admin_users=""):
    os.environ["AUTH_MODE"] = auth_mode
    os.environ["DEV_USER"] = dev_user
    os.environ["ADMIN_USERS"] = admin_users
    # Re-import to pick up patched env
    import importlib
    import app.config as cfg_mod
    importlib.reload(cfg_mod)
    import app.auth as auth_mod
    importlib.reload(auth_mod)
    return auth_mod


@pytest.mark.asyncio
async def test_get_current_user_dev_mode():
    from unittest.mock import patch
    import app.config as cfg
    with patch.object(cfg.settings, "auth_mode", "dev"), \
         patch.object(cfg.settings, "dev_user", "alice"), \
         patch.object(cfg.settings, "admin_users", ""):
        from starlette.testclient import TestClient
        from starlette.requests import Request
        from app.auth import get_current_user
        # Create a minimal mock request
        scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
        request = Request(scope)
        user = get_current_user(request)
        assert user.user_id == "alice"
        assert user.is_admin is False


@pytest.mark.asyncio
async def test_get_current_user_vouchproxy():
    import app.config as cfg
    with patch.object(cfg.settings, "auth_mode", "vouchproxy"), \
         patch.object(cfg.settings, "admin_users", ""):
        from starlette.requests import Request
        from app.auth import get_current_user
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"x-forwarded-user", b"bob")],
        }
        request = Request(scope)
        user = get_current_user(request)
        assert user.user_id == "bob"


@pytest.mark.asyncio
async def test_get_current_user_no_header_raises():
    import app.config as cfg
    from fastapi import HTTPException
    with patch.object(cfg.settings, "auth_mode", "vouchproxy"):
        from starlette.requests import Request
        from app.auth import get_current_user
        scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
        request = Request(scope)
        with pytest.raises(HTTPException) as exc:
            get_current_user(request)
        assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_admin_flag():
    import app.config as cfg
    with patch.object(cfg.settings, "auth_mode", "dev"), \
         patch.object(cfg.settings, "dev_user", "carol"), \
         patch.object(cfg.settings, "admin_users", "carol"):
        from starlette.requests import Request
        from app.auth import get_current_user
        scope = {"type": "http", "method": "GET", "path": "/", "headers": []}
        request = Request(scope)
        user = get_current_user(request)
        assert user.is_admin is True
