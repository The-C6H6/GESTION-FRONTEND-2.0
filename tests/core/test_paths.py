from esiqie_dictamenes.core.paths import project_assets_dir


def test_project_assets_dir_is_stable_when_process_cwd_changes(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    assets_dir = project_assets_dir()

    assert assets_dir.is_dir()
    assert (assets_dir / "ipn_logo.jpg").is_file()
    assert (assets_dir / "logo_esiqie.png").is_file()
    assert (assets_dir / "imagen_fondo.png").is_file()
