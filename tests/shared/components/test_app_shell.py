from types import SimpleNamespace

import flet as ft

from esiqie_dictamenes.core.routes import RoutePath
from esiqie_dictamenes.shared.components import app_shell
from esiqie_dictamenes.shared.components.app_shell import _navigation_items
from tests.helpers import authenticated_store, authenticated_user


def test_normal_navigation_exposes_queries_without_administrative_routes():
    items = _navigation_items(authenticated_user(is_admin=False))

    assert items == (
        ("Inicio", RoutePath.DASHBOARD),
        ("Buscar dictámenes", RoutePath.DICTAMENES),
        ("Consultar alumnos", RoutePath.NUEVO_DICTAMEN),
        ("Buscar inscrito", RoutePath.INSCRITOS),
    )


def test_administrator_navigation_retains_every_existing_route():
    items = _navigation_items(authenticated_user(is_admin=True))

    assert items == (
        ("Inicio", RoutePath.DASHBOARD),
        ("Buscar dictámenes", RoutePath.DICTAMENES),
        ("Dictaminar", RoutePath.NUEVO_DICTAMEN),
        ("Eliminar dictámenes", RoutePath.ELIMINAR_DICTAMENES),
        ("Buscar inscrito", RoutePath.INSCRITOS),
        ("Crear usuario", RoutePath.NUEVO_USUARIO),
    )


def test_header_displays_the_authenticated_identity(monkeypatch):
    session = authenticated_store(is_admin=False).current
    assert session is not None
    monkeypatch.setattr(
        app_shell,
        "use_app_context",
        lambda: SimpleNamespace(session=session, invalidate_session=lambda: None),
    )
    monkeypatch.setattr(
        app_shell,
        "_nav_button",
        lambda label, _path: ft.Text(label),
    )

    shell = app_shell.AppShell.__wrapped__(ft.Text("Contenido"))
    header = shell.controls[1].controls[0]
    username = header.content.controls[3]

    assert username.value == "consulta"
