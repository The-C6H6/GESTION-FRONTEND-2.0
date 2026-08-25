from datetime import date, datetime

import flet as ft

from esiqie_dictamenes.features.dictamenes.views import crear


def test_session_picker_only_allows_calendar_selection():
    selected = date(2026, 12, 11)

    picker = crear._build_session_date_picker(
        selected,
        on_change=lambda _event: None,
        on_dismiss=lambda _event: None,
    )

    assert isinstance(picker, ft.DatePicker)
    assert picker.entry_mode == ft.DatePickerEntryMode.CALENDAR_ONLY
    assert picker.value == selected
    assert picker.locale == ft.Locale("es", "MX")


def test_picker_datetime_is_normalized_to_a_date_object():
    result = crear._as_date(datetime(2026, 12, 11, 18, 30))

    assert result == date(2026, 12, 11)
    assert type(result) is date
