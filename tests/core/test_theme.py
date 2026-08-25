import flet as ft

from esiqie_dictamenes.core.theme import build_theme
from esiqie_dictamenes.main import main
from esiqie_dictamenes.shared.components.app_shell import _nav_button


def _relative_luminance(color: str) -> float:
    channels = [int(color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92
        if channel <= 0.04045
        else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast_ratio(first: str, second: str) -> float:
    lighter, darker = sorted(
        (_relative_luminance(first), _relative_luminance(second)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


def test_theme_semantic_text_pairs_meet_normal_text_contrast() -> None:
    scheme = build_theme().color_scheme
    pairs = (
        (scheme.primary, scheme.on_primary),
        (scheme.primary_container, scheme.on_primary_container),
        (scheme.surface, scheme.on_surface),
    )

    assert all(background and foreground for background, foreground in pairs)
    assert all(_contrast_ratio(background, foreground) >= 4.5 for background, foreground in pairs)


def test_button_theme_uses_legible_primary_pair() -> None:
    theme = build_theme()

    assert theme.button_theme is not None
    assert theme.button_theme.style is not None
    assert theme.button_theme.style.bgcolor == theme.color_scheme.primary
    assert theme.button_theme.style.color == theme.color_scheme.on_primary


def test_page_uses_light_mode_with_its_light_surface() -> None:
    class FakePage:
        def render(self, component) -> None:
            self.component = component

    page = FakePage()

    main(page)

    assert page.theme_mode == ft.ThemeMode.LIGHT


def test_active_navigation_uses_flet_argb_order(monkeypatch) -> None:
    monkeypatch.setattr(ft, "is_route_active", lambda _path: True)

    control = _nav_button("Dictaminar", "/dictamenes/nuevo")

    assert control.bgcolor == "#24FFFFFF"
