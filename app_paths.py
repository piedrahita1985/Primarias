from pathlib import Path
import sys


def app_base_path() -> Path:
    """Return project base path, compatible with PyInstaller executables."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def resource_path(*parts: str) -> Path:
    return app_base_path().joinpath(*parts)
