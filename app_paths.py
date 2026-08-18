from pathlib import Path
import sys


def app_base_path() -> Path:
    """Base path for read-only bundled assets (images, etc.), compatible with
    PyInstaller executables. Under a frozen --onefile build this points into
    the ephemeral _MEIPASS extraction folder, which is recreated on every
    launch -- never write persistent data here, use writable_base_path()."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def resource_path(*parts: str) -> Path:
    return app_base_path().joinpath(*parts)


def writable_base_path() -> Path:
    """Base path for anything the app reads AND writes across runs (config.json,
    data/kardex.db, errores.log, firmas/). Always the folder next to the actual
    .exe (or the project folder when running from source) -- never _MEIPASS,
    which is wiped after each run of a --onefile build."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def writable_path(*parts: str) -> Path:
    return writable_base_path().joinpath(*parts)
