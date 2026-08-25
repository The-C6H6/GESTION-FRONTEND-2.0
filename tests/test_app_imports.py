def test_application_composition_imports() -> None:
    from esiqie_dictamenes.app import App
    from esiqie_dictamenes.main import main

    assert App is not None
    assert main is not None


def test_private_header_distinguishes_api_and_demo_sessions() -> None:
    from esiqie_dictamenes.features.auth.models import Session
    from esiqie_dictamenes.shared.components.app_shell import session_status_label

    assert session_status_label(Session("demo", True, is_demo=True)) == (
        "Modo demostración"
    )
    assert session_status_label(Session("api", False, is_demo=False)) == (
        "Acceso API · módulos restantes en demostración"
    )
