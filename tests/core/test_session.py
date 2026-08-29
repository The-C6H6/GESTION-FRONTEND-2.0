import pytest

from esiqie_dictamenes.core.errors import AuthorizationError, SessionExpiredError
from esiqie_dictamenes.core.session import AuthSessionStore
from esiqie_dictamenes.features.auth.models import Session
from tests.helpers import authenticated_user


def test_store_completes_rotates_and_clears_one_shared_session():
    store = AuthSessionStore()
    pending = store.begin("old-access", "old-refresh")
    user = authenticated_user(is_admin=True)

    completed = store.authenticate(user)
    store.rotate("new-access", "new-refresh")

    assert completed is pending is store.current
    assert completed.current_user is user
    assert (completed.access_token, completed.refresh_token) == (
        "new-access",
        "new-refresh",
    )

    store.clear()
    assert store.current is None
    assert store.current_user is None


def test_session_contract_and_reprs_do_not_expose_tokens_or_demo_state():
    store = AuthSessionStore()
    session = store.begin("access-secret", "refresh-secret")

    assert tuple(Session.__dataclass_fields__) == (
        "access_token",
        "refresh_token",
        "authenticated_user",
    )
    assert "access-secret" not in repr(session)
    assert "refresh-secret" not in repr(session)
    assert "access-secret" not in repr(store)
    assert "refresh-secret" not in repr(store)
    assert not hasattr(AuthSessionStore(), "is_" "demo")


def test_store_requires_an_active_admin_identity():
    store = AuthSessionStore()

    with pytest.raises(SessionExpiredError):
        store.require_admin()

    store.begin("access", "refresh")
    store.authenticate(authenticated_user(is_admin=False))

    with pytest.raises(AuthorizationError):
        store.require_admin()

    store.authenticate(authenticated_user(is_admin=True))

    assert store.require_admin() is None
