import tkinter as tk

import logica.unidades_logica as _logica
from config.config import COLORS
from UI._base_maestra import MaestraBase, form_label, form_entry, form_estado


def open_window(master):
    UnidadesWindow(master)


class UnidadesWindow(MaestraBase):
    TITLE = "Maestra de Unidades"
    LOGICA_MODULE = _logica
    WINDOW_SIZE = "950x560"
    LIST_TITLE = "Unidades registradas"
    DETAIL_TITLE = "Detalle de la unidad"

    # ── Construccion del formulario ──────────────────────

    def _build_form(self, parent):
        self._v_unidad = tk.StringVar()

        f = tk.Frame(parent, bg=COLORS["secondary"])
        f.pack(fill="both", expand=True)
        f.grid_columnconfigure(0, weight=1)
        f.grid_columnconfigure(1, weight=1)

        form_label(f, "Unidad de Medida", 0, 0, 2)
        form_entry(f, self._v_unidad,     1, 0, 2)

        self._lbl_estado = form_estado(f, self._var_estado, 2, 0, 2)

    # ── Interface ────────────────────────────────────────

    def _get_form_data(self) -> dict:
        return {"unidad": self._v_unidad.get().strip()}

    def _set_form_data(self, r: dict):
        self._v_unidad.set(r.get("unidad", ""))

    def _clear_form(self):
        self._v_unidad.set("")

    def _list_label(self, r: dict) -> str:
        estado = r.get("estado", "HABILITADA")
        return f"{r.get('unidad', '')}  [{estado}]"

    def _validate(self, datos: dict):
        if not datos.get("unidad"):
            return False, "La unidad de medida es obligatoria."
        return True, ""
