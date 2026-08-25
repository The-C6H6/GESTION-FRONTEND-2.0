import flet as ft

from esiqie_dictamenes.core.context import use_app_context
from esiqie_dictamenes.core.errors import to_user_message
from esiqie_dictamenes.features.dictamenes.models import DictamenFilter
from esiqie_dictamenes.shared.components.feedback import feedback
from esiqie_dictamenes.shared.components.page_header import page_header


@ft.component
def DictamenDeleteView() -> ft.Control:
    context = use_app_context()
    records, set_records = ft.use_state(())
    selected, set_selected = ft.use_state(frozenset())
    message, set_message = ft.use_state("")
    is_error, set_is_error = ft.use_state(False)

    async def load() -> None:
        set_records(tuple(await context.services.dictamen_controller.search(DictamenFilter())))

    ft.use_effect(load, [])

    def toggle(clave: str, checked: bool) -> None:
        updated = set(selected)
        if checked:
            updated.add(clave)
        else:
            updated.discard(clave)
        set_selected(frozenset(updated))

    async def delete() -> None:
        try:
            total = await context.services.dictamen_controller.delete_many(tuple(selected))
            set_message(f"{total} dictamen(es) eliminado(s) en modo demostración.")
            set_is_error(False)
            set_selected(frozenset())
            await load()
        except Exception as error:
            set_message(to_user_message(error))
            set_is_error(True)

    table = ft.Row(
        [
            ft.DataTable(
                columns=[
                    ft.DataColumn(ft.Text("Seleccionar")),
                    ft.DataColumn(ft.Text("Clave")),
                    ft.DataColumn(ft.Text("Boleta")),
                    ft.DataColumn(ft.Text("Alumno")),
                    ft.DataColumn(ft.Text("Año")),
                ],
                rows=[
                    ft.DataRow(
                        cells=[
                            ft.DataCell(
                                ft.Checkbox(
                                    value=record.clave in selected,
                                    on_change=lambda e, key=record.clave: toggle(
                                        key, bool(e.control.value)
                                    ),
                                )
                            ),
                            ft.DataCell(ft.Text(record.clave)),
                            ft.DataCell(ft.Text(record.boleta)),
                            ft.DataCell(ft.Text(record.alumno)),
                            ft.DataCell(ft.Text(str(record.anio))),
                        ]
                    )
                    for record in records
                ],
            )
        ],
        scroll=ft.ScrollMode.AUTO,
    )
    return ft.Column(
        [
            page_header("Eliminar dictámenes", "Selecciona uno o varios registros por su clave."),
            feedback(message, error=is_error),
            ft.Row(
                [
                    ft.Text(f"{len(selected)} seleccionado(s)"),
                    ft.Container(expand=True),
                    ft.Button("Eliminar seleccionados", on_click=delete, key="delete-selected"),
                ]
            ),
            table,
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )
