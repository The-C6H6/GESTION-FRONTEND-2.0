import flet as ft


def eligible_subjects_table(items) -> ft.Control:
    if not items:
        return ft.Container()
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
