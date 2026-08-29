import flet as ft

from esiqie_dictamenes.features.alumnos.models import Inscrito
from esiqie_dictamenes.features.alumnos.views import inscritos
from tests.helpers import authenticated_user


def _inscrito() -> Inscrito:
    return Inscrito(
        boleta="2024320678",
        nombre="Ana López Martínez",
        carrera="Ingeniería Química Industrial",
        plan_estud=2021,
        especialidad="",
        secuencias="3IM1",
        turno="Matutino",
        genero="Femenino",
        edad=20,
        promedio=8.7,
        dictamen_vigente="Sin dictamen",
        periodo_escolar_ingreso="20241",
        periodos_cursados=5,
        semestre_nivel_inscrito=3,
        no_cursadas=0,
        reprobadas=1,
        desfasadas=0,
        periodo_en_que_reprobo=20252,
        materias_inscritas=6,
        materias_reprobadas_no_inscritas=0,
        avance=45.0,
        carga_minima=30,
        carga_media=42,
        carga_maxima=54,
        creditos_inscritos=42,
        creditos_de_reprobadas_inscritas=6,
        creditos_de_reprobadas_no_inscritas=0,
        total_de_creditos=180,
        posible_irregularidad=None,
    )


def _descendants(control: ft.Control):
    yield control
    for child in getattr(control, "controls", ()):
        yield from _descendants(child)
    content = getattr(control, "content", None)
    if isinstance(content, ft.Control):
        yield from _descendants(content)


def test_enrolled_details_keep_academic_data_but_hide_create_for_normal_user():
    result = inscritos._build_inscrito_details(
        _inscrito(),
        authenticated_user(is_admin=False),
        on_create=lambda: None,
    )
    controls = tuple(_descendants(result))
    texts = [control.value for control in controls if isinstance(control, ft.Text)]

    assert "Ana López Martínez" in texts
    assert "Boleta: 2024320678" in texts
    assert "Carrera: Ingeniería Química Industrial" in texts
    assert "Promedio: 8.7" in texts
    assert not any(
        isinstance(control, ft.Button)
        and control.key == "inscrito-create-dictamen"
        for control in controls
    )


def test_enrolled_details_offer_create_to_administrator():
    calls = []
    result = inscritos._build_inscrito_details(
        _inscrito(),
        authenticated_user(is_admin=True),
        on_create=lambda: calls.append(True),
    )
    controls = tuple(_descendants(result))
    button = next(
        control
        for control in controls
        if isinstance(control, ft.Button)
        and control.key == "inscrito-create-dictamen"
    )

    button.on_click()

    assert calls == [True]
