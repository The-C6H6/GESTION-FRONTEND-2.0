class RequestGate:
    def __init__(self) -> None:
        self.active = False

    def enter(self) -> bool:
        if self.active:
            return False
        self.active = True
        return True

    def leave(self) -> None:
        self.active = False
