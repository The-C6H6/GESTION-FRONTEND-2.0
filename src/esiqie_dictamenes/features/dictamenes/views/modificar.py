import flet as ft

from esiqie_dictamenes.features.dictamenes.models import Dictamen


def _build_edit_form(
    *,
    record: Dictamen,
    value: str,
    busy: bool,
    on_value,
    on_save,
    on_cancel,
) -> ft.Control:
    return ft.Column(
        [
            ft.Text(
                "Modificar dictamen",
                size=22,
                weight=ft.FontWeight.BOLD,
            ),
            ft.Text("Solo la dictaminación puede modificarse."),
            ft.ResponsiveRow(
                [
                    ft.Text(f"Clave: {record.clave}", col={"sm": 12, "md": 4}),
                    ft.Text(f"Boleta: {record.boleta}", col={"sm": 12, "md": 4}),
                    ft.Text(f"Año: {record.anio}", col={"sm": 12, "md": 4}),
                    ft.Text(f"Alumno: {record.alumno}", col=12),
                    ft.Text(f"Fecha: {record.fecha.isoformat()}", col=12),
                ]
            ),
            ft.TextField(
                label="Dictaminación",
                value=value,
                multiline=True,
                min_lines=4,
                on_change=on_value,
                disabled=busy,
                key="edit-dictaminacion",
            ),
            ft.Row(
                [
                    ft.Button(
                        "Cancelar",
                        on_click=on_cancel,
                        disabled=busy,
                        key="edit-cancel",
                    ),
                    ft.Button(
                        "Guardar cambios",
                        on_click=on_save,
                        disabled=busy,
                        key="edit-submit",
                    ),
                ],
                alignment=ft.MainAxisAlignment.END,
            ),
        ],
        key="dictamen-edit-form",
    )
