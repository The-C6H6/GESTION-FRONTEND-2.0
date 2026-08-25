import flet as ft

from esiqie_dictamenes.core.context import AppContext, AppContextValue, use_app_context
from esiqie_dictamenes.core.routes import RoutePath
from esiqie_dictamenes.core.services import build_services
from esiqie_dictamenes.features.alumnos.views.inscritos import InscritoSearchView
from esiqie_dictamenes.features.auth.view import LoginView
from esiqie_dictamenes.features.dashboard.view import DashboardView
from esiqie_dictamenes.features.dictamenes.views.buscar import DictamenSearchView
from esiqie_dictamenes.features.dictamenes.views.crear import DictamenCreateView
from esiqie_dictamenes.features.dictamenes.views.eliminar import DictamenDeleteView
from esiqie_dictamenes.features.dictamenes.views.modificar import DictamenEditView
from esiqie_dictamenes.features.usuarios.view import CreateUserView
from esiqie_dictamenes.shared.components.app_shell import AppShell


@ft.component
def _private_layout() -> ft.Control:
    context = use_app_context()

    def redirect_to_login() -> None:
        if context.session is None:
            ft.context.page.navigate(RoutePath.LOGIN)

    ft.use_effect(redirect_to_login, [context.session])
    if context.session is None:
        return ft.Container(
            content=ft.ProgressRing(),
            alignment=ft.Alignment.CENTER,
            expand=True,
        )
    return AppShell(ft.use_route_outlet())


@ft.component
def _not_found_view() -> ft.Control:
    return ft.Container(
        content=ft.Column(
            [
                ft.Text("404", size=52, weight=ft.FontWeight.BOLD),
                ft.Text("La página solicitada no existe."),
                ft.Button(
                    "Volver al inicio",
                    on_click=lambda: ft.context.page.navigate(RoutePath.DASHBOARD),
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        alignment=ft.Alignment.CENTER,
        expand=True,
    )


@ft.component
def _app_router() -> ft.Control:
    return ft.Router(
        routes=[
            ft.Route(path="login", component=LoginView),
            ft.Route(
                component=_private_layout,
                children=[
                    ft.Route(index=True, component=DashboardView),
                    ft.Route(
                        path="dictamenes",
                        children=[
                            ft.Route(index=True, component=DictamenSearchView),
                            ft.Route(path="nuevo", component=DictamenCreateView),
                            ft.Route(path="eliminar", component=DictamenDeleteView),
                            ft.Route(path=":clave/editar", component=DictamenEditView),
                        ],
                    ),
                    ft.Route(path="inscritos", component=InscritoSearchView),
                    ft.Route(path="usuarios/nuevo", component=CreateUserView),
                ],
            ),
        ],
        not_found=_not_found_view,
    )


@ft.component
def App() -> ft.Control:
    session, set_session = ft.use_state(None)
    services, _ = ft.use_state(build_services)
    context = AppContextValue(
        services=services,
        session=session,
        set_session=set_session,
    )
    return AppContext(context, _app_router)
