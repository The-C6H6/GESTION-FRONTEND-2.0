class AppError(Exception):
    """Base error that can be safely translated for the interface."""


class ValidationError(AppError):
    """Raised when user-provided data does not satisfy a form contract."""


class NotFoundError(AppError):
    """Raised when a requested demo or API resource does not exist."""


def to_user_message(error: Exception) -> str:
    if isinstance(error, AppError):
        return str(error)
    return "No fue posible completar la operación. Intenta nuevamente."
