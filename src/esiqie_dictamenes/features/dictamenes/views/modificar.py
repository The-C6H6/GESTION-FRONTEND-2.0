import flet as ft

from esiqie_dictamenes.core.context import use_app_context
from esiqie_dictamenes.core.errors import to_user_message
from esiqie_dictamenes.shared.components.feedback import feedback
from esiqie_dictamenes.shared.components.page_header import page_header


@ft.component
def DictamenEditView() -> ft.Control:
    context = use_app_context()
    clave = ft.use_route_params().get("clave", "")
    record, set_record = ft.use_state(None)
    value, set_value = ft.use_state("")
    message, set_message = ft.use_state("")
    is_error, set_is_error = ft.use_state(False)

    async def load() -> None:
        try:
            loaded = await context.services.dictamen_controller.get(clave)
            set_record(loaded)
            set_value(loaded.dictaminacion)
        except Exception as error:
            set_message(to_user_message(error))
            set_is_error(True)

    ft.use_effect(load, [clave])

    async def save() -> None:
        try:
            result = await context.services.dictamen_controller.update_and_generate(clave, value)
            set_record(result.dictamen)
            set_message(f"Cambios guardados. PDF {result.document.filename} simulado automáticamente.")
            set_is_error(False)
        except Exception as error:
            set_message(to_user_message(error))
            set_is_error(True)

    metadata = ft.ProgressRing()
    if record:
        metadata = ft.Row(
            [
                ft.Text(f"Boleta: {record.boleta}", weight=ft.FontWeight.BOLD),
                ft.Text(f"Año: {record.anio}", weight=ft.FontWeight.BOLD),
                ft.Text(f"Clave: {record.clave}", weight=ft.FontWeight.BOLD),
            ]
        )
    return ft.Column(
        [
            page_header("Modificar dictamen", "Solo la dictaminación puede modificarse."),
            metadata,
            feedback(message, error=is_error),
            ft.TextField(
                label="Dictaminación",
                value=value,
                multiline=True,
                min_lines=4,
                on_change=lambda e: set_value(e.control.value),
                key="edit-dictaminacion",
            ),
            ft.Row(
                [ft.Button("Guardar y generar PDF", on_click=save, key="edit-submit")],
                alignment=ft.MainAxisAlignment.END,
            ),
        ],
        scroll=ft.ScrollMode.AUTO,
    )
