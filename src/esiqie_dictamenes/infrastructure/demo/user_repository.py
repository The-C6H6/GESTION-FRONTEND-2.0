from esiqie_dictamenes.features.auth.models import RegisteredUser


class DemoUserRepository:
    def __init__(self) -> None:
        self.registered_users: list[RegisteredUser] = []

    async def register(
        self, username: str, password: str, is_admin: bool
    ) -> RegisteredUser:
        user = RegisteredUser(username=username, is_admin=is_admin)
        self.registered_users.append(user)
        return user
