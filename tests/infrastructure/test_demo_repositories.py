import asyncio

from esiqie_dictamenes.features.dictamenes.models import DictamenFilter, DictamenUpdate
from esiqie_dictamenes.infrastructure.demo.alumno_repository import DemoAlumnoRepository
from esiqie_dictamenes.infrastructure.demo.dictamen_repository import DemoDictamenRepository


def test_dictamen_search_preserves_multiple_records_for_one_student():
    repository = DemoDictamenRepository()

    records = asyncio.run(repository.search(DictamenFilter(boleta="2024320678")))

    assert [record.clave for record in records] == ["D-00081", "D-00132", "D-00201"]


def test_dictamen_search_filters_by_year():
    repository = DemoDictamenRepository()

    records = asyncio.run(repository.search(DictamenFilter(anio=2025)))

    assert records
    assert {record.anio for record in records} == {2025}


def test_demo_dictamen_search_page_returns_page_metadata_without_accumulating():
    repository = DemoDictamenRepository()

    page = asyncio.run(
        repository.search_page(
            DictamenFilter(boleta="2024320678"),
            skip=1,
            limit=1,
        )
    )

    assert page.total == 3
    assert page.skip == 1
    assert page.limit == 1
    assert [record.clave for record in page.items] == ["D-00132"]


def test_delete_many_removes_exactly_the_selected_keys():
    repository = DemoDictamenRepository()

    deleted = asyncio.run(repository.delete_many(("D-00081", "D-00201")))

    remaining = asyncio.run(repository.search(DictamenFilter(boleta="2024320678")))
    assert deleted == 2
    assert [record.clave for record in remaining] == ["D-00132"]


def test_update_changes_only_the_dictaminacion():
    repository = DemoDictamenRepository()

    before = asyncio.run(repository.get("D-00132"))
    after = asyncio.run(repository.update("D-00132", DictamenUpdate("Nueva causa")))

    assert after.dictaminacion == "Nueva causa"
    assert (after.clave, after.boleta, after.fecha, after.anio) == (
        before.clave,
        before.boleta,
        before.fecha,
        before.anio,
    )


def test_alumno_repository_exposes_the_required_inscrito_fields():
    repository = DemoAlumnoRepository()

    alumno = asyncio.run(repository.get_inscrito("2024320678"))

    assert alumno.edad == 21
    assert alumno.genero == "Femenino"
    assert alumno.promedio == 8.74
    assert alumno.creditos_inscritos == 42
    assert alumno.periodo_en_que_reprobo == 20242
    assert alumno.reprobadas == 2


def test_reprobados_can_be_searched_by_student_name():
    repository = DemoAlumnoRepository()

    records = asyncio.run(repository.search_reprobados(nombre="Ana"))

    assert records
    assert {record.boleta for record in records} == {"2024320678"}
