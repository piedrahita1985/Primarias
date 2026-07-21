import logging
import sys

from app_paths import resource_path
from UI.login import LoginApp


def _configurar_logging():
    """Registra errores no controlados en un archivo de log junto al
    ejecutable: en un build congelado (sin consola) es la unica forma de
    diagnosticar un fallo que la UI no logro mostrar."""
    logging.basicConfig(
        filename=str(resource_path("errores.log")),
        level=logging.ERROR,
        format="%(asctime)s [%(levelname)s] %(message)s",
        encoding="utf-8",
    )


def _habilitar_dpi_awareness():
    """En Windows, Tkinter se ve borroso/escalado en monitores de alta
    resolucion si el proceso no se declara DPI-aware antes de crear la
    primera ventana."""
    if sys.platform != "win32":
        return
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # PROCESS_SYSTEM_DPI_AWARE
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass


def main():
    _configurar_logging()
    _habilitar_dpi_awareness()
    app = LoginApp()
    app.mainloop()


if __name__ == "__main__":
    main()

