from esiqie_dictamenes.core.errors import ValidationError, to_user_message


def test_known_errors_keep_their_user_facing_message():
    assert to_user_message(ValidationError("Dato inválido.")) == "Dato inválido."


def test_unknown_errors_do_not_expose_technical_details():
    message = to_user_message(RuntimeError("HTTP 500 at /api/private"))

    assert "500" not in message
    assert "/api" not in message
