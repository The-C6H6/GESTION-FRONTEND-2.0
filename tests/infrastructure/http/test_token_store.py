from esiqie_dictamenes.infrastructure.http.token_store import AuthTokenStore


def test_token_store_replaces_and_clears_tokens():
    store = AuthTokenStore()
    store.replace("access-secret", "refresh-secret")

    assert store.access_token == "access-secret"
    assert store.has_tokens is True

    store.clear()

    assert store.access_token is None
    assert store.has_tokens is False


def test_token_store_replaces_an_existing_session():
    store = AuthTokenStore()
    store.replace("old-access", "old-refresh")

    store.replace("new-access", "new-refresh")

    assert store.access_token == "new-access"


def test_token_store_repr_does_not_expose_secrets():
    store = AuthTokenStore()
    store.replace("access-secret", "refresh-secret")

    representation = repr(store)

    assert "access-secret" not in representation
    assert "refresh-secret" not in representation
    assert "has_tokens=True" in representation
