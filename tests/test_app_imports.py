def test_application_composition_imports() -> None:
    from esiqie_dictamenes.app import App
    from esiqie_dictamenes.main import main

    assert App is not None
    assert main is not None


def test_private_header_reports_one_real_authenticated_session_status() -> None:
    from esiqie_dictamenes.shared.components.app_shell import session_status_label
    from tests.helpers import authenticated_store

    session = authenticated_store().current
    assert session is not None

    assert session_status_label(session) == (
        "Acceso API · módulos restantes en demostración"
    )
    assert not hasattr(session, "is_" "demo")
