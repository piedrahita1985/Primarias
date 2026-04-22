import tkinter as tk

import logica.colores_logica as _logica
from config.config import COLORS
from UI._base_maestra import MaestraBase, form_label, form_entry, form_estado


def open_window(master):
    ColoresWindow(master)


class ColoresWindow(MaestraBase):
    TITLE = "Maestra de Colores de Refuerzo"
    LOGICA_MODULE = _logica
    WINDOW_SIZE = "950x560"
    LIST_TITLE = "Colores registrados"
    DETAIL_TITLE = "Detalle del color"

    # ── Construccion del formulario ──────────────────────

    def _build_form(self, parent):
        self._v_color = tk.StringVar()

        f = tk.Frame(parent, bg=COLORS["secondary"])
        f.pack(fill="both", expand=True)
        f.grid_columnconfigure(0, weight=1)
        f.grid_columnconfigure(1, weight=1)

        form_label(f, "Color de Refuerzo", 0, 0, 2)
        form_entry(f, self._v_color,       1, 0, 2)

        self._lbl_estado = form_estado(f, self._var_estado, 2, 0, 2)

    # ── Interface ────────────────────────────────────────

    def _get_form_data(self) -> dict:
        return {"color_refuerzo": self._v_color.get().strip()}

    def _set_form_data(self, r: dict):
        self._v_color.set(r.get("color_refuerzo", ""))

    def _clear_form(self):
        self._v_color.set("")

    def _list_label(self, r: dict) -> str:
        estado = r.get("estado", "HABILITADA")
        return f"{r.get('color_refuerzo', '')}  [{estado}]"

    def _validate(self, datos: dict):
        if not datos.get("color_refuerzo"):
            return False, "El nombre del color es obligatorio."
        return True, ""
