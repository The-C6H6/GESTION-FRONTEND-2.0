from dataclasses import dataclass, field


@dataclass(frozen=True)
class AuthenticatedUser:
    id: int
    username: str
    is_active: bool
    is_admin: bool


@dataclass
class Session:
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    authenticated_user: AuthenticatedUser | None = None

    @property
    def current_user(self) -> AuthenticatedUser | None:
        return self.authenticated_user


@dataclass(frozen=True)
class RegisteredUser:
    username: str
    is_admin: bool
