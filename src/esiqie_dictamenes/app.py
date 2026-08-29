import flet as ft

from esiqie_dictamenes.core.context import AppContext, AppContextValue, use_app_context
from esiqie_dictamenes.core.routes import RoutePath, is_admin_route
from esiqie_dictamenes.core.services import build_services
from esiqie_dictamenes.features.alumnos.views.inscritos import InscritoSearchView
from esiqie_dictamenes.features.auth.models import Session
from esiqie_dictamenes.features.auth.view import LoginView
from esiqie_dictamenes.features.dashboard.view import DashboardView
from esiqie_dictamenes.features.dictamenes.views.buscar import DictamenSearchView
from esiqie_dictamenes.features.dictamenes.views.crear import DictamenCreateView
from esiqie_dictamenes.features.usuarios.view import CreateUserView
from esiqie_dictamenes.shared.components.app_shell import AppShell


def _private_route_redirect(
    path: str,
    session: Session | None,
) -> RoutePath | None:
    if (
        session is None
        or session.current_user is None
        or not session.current_user.is_active
    ):
        return RoutePath.LOGIN
    if is_admin_route(path) and not session.current_user.is_admin:
        return RoutePath.DASHBOARD
    return None


@ft.component
def _private_layout() -> ft.Control:
    context = use_app_context()
    redirect_target = _private_route_redirect(
        ft.context.page.route,
        context.session,
    )

    def redirect_private_route() -> None:
        if redirect_target is not None:
            ft.context.page.navigate(redirect_target)

    ft.use_effect(redirect_private_route, [redirect_target])
    if redirect_target is not None:
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
                            ft.Route(path="eliminar", component=DictamenSearchView),
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
