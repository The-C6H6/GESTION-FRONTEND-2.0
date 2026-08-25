class AuthTokenStore:
    def __init__(self) -> None:
        self._access_token: str | None = None
        self._refresh_token: str | None = None

    @property
    def access_token(self) -> str | None:
        return self._access_token

    @property
    def has_tokens(self) -> bool:
        return self._access_token is not None or self._refresh_token is not None

    def replace(self, access_token: str, refresh_token: str) -> None:
        self._access_token = access_token
        self._refresh_token = refresh_token

    def clear(self) -> None:
        self._access_token = None
        self._refresh_token = None

    def __repr__(self) -> str:
        return f"AuthTokenStore(has_tokens={self.has_tokens})"
