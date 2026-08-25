from esiqie_dictamenes.features.auth.models import RegisteredUser, Session


class DemoAuthRepository:
    def __init__(self) -> None:
        self.registered_users: list[RegisteredUser] = []

    async def login(self, username: str, password: str) -> Session:
        return Session(username=username, is_admin=True, is_demo=True)

    async def register(
        self, username: str, password: str, is_admin: bool
    ) -> RegisteredUser:
        user = RegisteredUser(username=username, is_admin=is_admin)
        self.registered_users.append(user)
        return user
