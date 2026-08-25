import flet as ft


def eligible_subjects_table(items, empty_message: str | None = None) -> ft.Control:
    if not items:
        return ft.Text(
            empty_message
            or "No hay materias que cumplan la regla 19 ≤ diferencia < 29."
        )
    return ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Materia")),
            ft.DataColumn(ft.Text("Periodo reprobado")),
            ft.DataColumn(ft.Text("Diferencia")),
            ft.DataColumn(ft.Text("PDF")),
        ],
        rows=[
            ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(item.materia)),
                    ft.DataCell(ft.Text(str(item.periodo_reprobada))),
                    ft.DataCell(ft.Text(str(item.diferencia))),
                    ft.DataCell(ft.Text("Incluida")),
                ]
            )
            for item in items
        ],
    )
