from dataclasses import dataclass


@dataclass(frozen=True)
class Session:
    username: str
    is_admin: bool
    is_demo: bool = False


@dataclass(frozen=True)
class RegisteredUser:
    username: str
    is_admin: bool
