import pytest

from esiqie_dictamenes.core.errors import (
    ApiConnectionError,
    ApiTimeoutError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ServiceUnavailableError,
    UnexpectedResponseError,
    ValidationError,
    to_user_message,
)


def test_known_errors_keep_their_user_facing_message():
    assert to_user_message(ValidationError("Dato inválido.")) == "Dato inválido."


def test_unknown_errors_do_not_expose_technical_details():
    message = to_user_message(RuntimeError("HTTP 500 at /api/private"))

    assert "500" not in message
    assert "/api" not in message


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (ApiConnectionError(), "No fue posible conectar con el servicio."),
        (ApiTimeoutError(), "El servicio tardó demasiado en responder."),
        (AuthenticationError(), "Usuario o contraseña incorrectos."),
        (AuthorizationError(), "No tienes permiso para realizar esta acción."),
        (NotFoundError(), "No se encontró el recurso solicitado."),
        (ValidationError(), "Los datos enviados no son válidos."),
        (
            ServiceUnavailableError(),
            "El servicio no está disponible temporalmente.",
        ),
        (
            UnexpectedResponseError(),
            "El servicio devolvió una respuesta no válida.",
        ),
    ],
)
def test_api_errors_have_safe_user_messages(error, message):
    assert to_user_message(error) == message
    assert not any(code in message for code in ("401", "403", "404", "422", "500"))
