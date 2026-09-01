from datetime import date
from typing import Callable

import flet as ft

from esiqie_dictamenes.features.dictamenes.models import Dictamen
from esiqie_dictamenes.features.dictamenes.pdf import format_session_date


def _build_edit_form(
    *,
    record: Dictamen,
    value: str,
    busy: bool,
    on_value,
    on_save,
    on_cancel,
    director: str | None = None,
    fecha_sesion: date | None = None,
    on_director: Callable | None = None,
    on_date: Callable | None = None,
) -> ft.Control:
    controls: list[ft.Control] = [
        ft.Text(
            "Modificar dictamen",
            size=22,
            weight=ft.FontWeight.BOLD,
        ),
        ft.Text(
            "Solo la dictaminaci\u00f3n modifica el registro; "
            "director y fecha se usan para el PDF."
        ),
        ft.ResponsiveRow(
            [
                ft.Text(f"Clave: {record.clave}", col={"sm": 12, "md": 4}),
                ft.Text(f"Boleta: {record.boleta}", col={"sm": 12, "md": 4}),
                ft.Text(f"A\u00f1o: {record.anio}", col={"sm": 12, "md": 4}),
                ft.Text(f"Alumno: {record.alumno}", col=12),
                ft.Text(f"Fecha: {record.fecha.isoformat()}", col=12),
            ]
        ),
    ]
    if director is not None:
        controls.append(
            ft.TextField(
                label="Nombre del director",
                value=director,
                on_change=on_director,
                disabled=busy,
                key="edit-director",
            )
        )
    if fecha_sesion is not None:
        controls.append(
            ft.Row(
                [
                    ft.TextField(
                        label="Fecha de sesi\u00f3n",
                        value=format_session_date(fecha_sesion),
                        read_only=True,
                        disabled=busy,
                        expand=True,
                        key="edit-session-date",
                    ),
                    ft.Button(
                        "Elegir fecha",
                        icon=ft.Icons.CALENDAR_MONTH,
                        on_click=on_date,
                        disabled=busy,
                        key="edit-session-date-open",
                    ),
                ]
            )
        )
    controls.extend(
        [
            ft.TextField(
                label="Dictaminaci\u00f3n",
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
        ]
    )
    return ft.Column(controls, key="dictamen-edit-form")
