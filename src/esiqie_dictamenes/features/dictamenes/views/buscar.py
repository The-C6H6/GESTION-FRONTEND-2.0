import flet as ft

from esiqie_dictamenes.core.context import use_app_context
from esiqie_dictamenes.core.errors import ValidationError, to_user_message
from esiqie_dictamenes.features.dictamenes.models import DictamenFilter
from esiqie_dictamenes.shared.components.feedback import feedback
from esiqie_dictamenes.shared.components.page_header import page_header


@ft.component
def DictamenSearchView() -> ft.Control:
    context = use_app_context()
    criterion, set_criterion = ft.use_state("boleta")
    query, set_query = ft.use_state("")
    records, set_records = ft.use_state(())
    message, set_message = ft.use_state("")

    async def search() -> None:
        try:
            normalized = query.strip()
            if not normalized:
                raise ValidationError("Escribe una boleta o un año.")
            filters = (
                DictamenFilter(boleta=normalized)
                if criterion == "boleta"
                else DictamenFilter(anio=int(normalized))
            )
            result = tuple(await context.services.dictamen_controller.search(filters))
            set_records(result)
            set_message(f"{len(result)} dictamen(es) encontrado(s).")
        except ValueError:
            set_message("El año debe ser un número válido.")
            set_records(())
        except Exception as error:
            set_message(to_user_message(error))
            set_records(())

    table = ft.Container()
    if records:
        table = ft.Row(
            [
                ft.DataTable(
                    columns=[
                        ft.DataColumn(ft.Text("Clave")),
                        ft.DataColumn(ft.Text("Boleta")),
                        ft.DataColumn(ft.Text("Alumno")),
                        ft.DataColumn(ft.Text("Año")),
                        ft.DataColumn(ft.Text("Dictaminación")),
                        ft.DataColumn(ft.Text("Acción")),
                    ],
                    rows=[
                        ft.DataRow(
                            cells=[
                                ft.DataCell(ft.Text(record.clave)),
                                ft.DataCell(ft.Text(record.boleta)),
                                ft.DataCell(ft.Text(record.alumno)),
                                ft.DataCell(ft.Text(str(record.anio))),
                                ft.DataCell(ft.Text(record.dictaminacion)),
                                ft.DataCell(
                                    ft.Button(
                                        "Modificar",
                                        on_click=lambda _e, key=record.clave: ft.context.page.navigate(
                                            f"/dictamenes/{key}/editar"
                                        ),
                                    )
                                ),
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
            page_header("Buscar dictámenes", "Consulta por número de boleta o año."),
            ft.Row(
                [
                    ft.Dropdown(
                        label="Criterio",
                        value=criterion,
                        options=[
                            ft.DropdownOption(key="boleta", text="Número de boleta"),
                            ft.DropdownOption(key="anio", text="Año"),
                        ],
                        on_select=lambda e: set_criterion(e.control.value),
                        width=220,
                        key="dictamen-criterion",
                    ),
                    ft.TextField(
                        label="Valor de búsqueda",
                        value=query,
                        on_change=lambda e: set_query(e.control.value),
                        on_submit=search,
                        expand=True,
                        key="dictamen-query",
                    ),
                    ft.Button("Buscar", on_click=search, key="dictamen-search"),
                ]
            ),
            feedback(message),
            table,
        ],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )
