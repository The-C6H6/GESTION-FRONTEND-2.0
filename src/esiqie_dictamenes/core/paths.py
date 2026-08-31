from collections.abc import Callable
from pathlib import Path


def _paths_module_file() -> Path:
    return Path(__file__).resolve()


def project_assets_dir(path_resolver: Callable[[], Path] = _paths_module_file) -> Path:
    """Return the repository asset directory without depending on the process CWD."""
    return path_resolver().parents[3] / "assets"
