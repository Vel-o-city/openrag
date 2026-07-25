import pytest
from fastapi import HTTPException

from app.api.admin import _require_admin


def test_require_admin_accepts_correct_bearer_token(monkeypatch):
    from app.api import admin

    monkeypatch.setattr(admin.settings, "admin_token", "s3cret")
    _require_admin("Bearer s3cret")  # does not raise


def test_require_admin_rejects_missing_header(monkeypatch):
    from app.api import admin

    monkeypatch.setattr(admin.settings, "admin_token", "s3cret")
    with pytest.raises(HTTPException) as exc_info:
        _require_admin(None)
    assert exc_info.value.status_code == 401


def test_require_admin_rejects_wrong_token(monkeypatch):
    from app.api import admin

    monkeypatch.setattr(admin.settings, "admin_token", "s3cret")
    with pytest.raises(HTTPException) as exc_info:
        _require_admin("Bearer wrong-token")
    assert exc_info.value.status_code == 401


def test_require_admin_rejects_missing_bearer_prefix(monkeypatch):
    from app.api import admin

    monkeypatch.setattr(admin.settings, "admin_token", "s3cret")
    with pytest.raises(HTTPException):
        _require_admin("s3cret")
