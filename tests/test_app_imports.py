def test_application_composition_imports() -> None:
    from esiqie_dictamenes.app import App
    from esiqie_dictamenes.main import main

    assert App is not None
    assert main is not None
