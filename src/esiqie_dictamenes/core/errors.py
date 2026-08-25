class AppError(Exception):
    """Base error that can be safely translated for the interface."""


class ValidationError(AppError):
    """Raised when user-provided data does not satisfy a form contract."""

    def __init__(self, message: str = "Los datos enviados no son válidos.") -> None:
        super().__init__(message)


class NotFoundError(AppError):
    """Raised when a requested demo or API resource does not exist."""

    def __init__(self, message: str = "No se encontró el recurso solicitado.") -> None:
        super().__init__(message)


class ConfigurationError(AppError):
    """Raised when required runtime configuration is absent or invalid."""


class ApiConnectionError(AppError):
    """Raised when the API cannot be reached."""

    def __init__(self) -> None:
        super().__init__("No fue posible conectar con el servicio.")


class ApiTimeoutError(AppError):
    """Raised when the API exceeds the configured timeout."""

    def __init__(self) -> None:
        super().__init__("El servicio tardó demasiado en responder.")


class AuthenticationError(AppError):
    """Raised when supplied credentials are not accepted."""

    def __init__(self) -> None:
        super().__init__("Usuario o contraseña incorrectos.")


class SessionExpiredError(AppError):
    """Raised when an authenticated API session is no longer valid."""

    def __init__(self) -> None:
        super().__init__("La sesión no es válida. Inicia sesión nuevamente.")


class AuthorizationError(AppError):
    """Raised when the authenticated identity lacks permission."""

    def __init__(self) -> None:
        super().__init__("No tienes permiso para realizar esta acción.")


class ServiceUnavailableError(AppError):
    """Raised when the API reports a temporary server failure."""

    def __init__(self) -> None:
        super().__init__("El servicio no está disponible temporalmente.")


class UnexpectedResponseError(AppError):
    """Raised when the API response does not match its contract."""

    def __init__(self) -> None:
        super().__init__("El servicio devolvió una respuesta no válida.")


def to_user_message(error: Exception) -> str:
    if isinstance(error, AppError):
        return str(error)
    return "No fue posible completar la operación. Intenta nuevamente."
