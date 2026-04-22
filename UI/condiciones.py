import tkinter as tk

import logica.condiciones_logica as _logica
from config.config import COLORS
from UI._base_maestra import MaestraBase, form_entry, form_estado, form_label


def open_window(master):
    CondicionesWindow(master)


class CondicionesWindow(MaestraBase):
    TITLE = "Maestra de Condiciones de Almacenamiento"
    LOGICA_MODULE = _logica
    WINDOW_SIZE = "980x580"
    LIST_TITLE = "Condiciones registradas"
    DETAIL_TITLE = "Detalle de la condicion"

    def _build_form(self, parent):
        self._v_condicion = tk.StringVar()

        f = tk.Frame(parent, bg=COLORS["secondary"])
        f.pack(fill="both", expand=True)
        f.grid_columnconfigure(0, weight=1)
        f.grid_columnconfigure(1, weight=1)

        form_label(f, "Condicion de almacenamiento", 0, 0, 2)
        form_entry(f, self._v_condicion, 1, 0, 2)

        self._lbl_estado = form_estado(f, self._var_estado, 2, 0, 2)

    def _get_form_data(self) -> dict:
        return {"condicion": self._v_condicion.get().strip().upper()}

    def _set_form_data(self, r: dict):
        self._v_condicion.set(r.get("condicion", ""))

    def _clear_form(self):
        self._v_condicion.set("")

    def _list_label(self, r: dict) -> str:
        estado = r.get("estado", "HABILITADA")
        return f"{r.get('condicion', '')}  [{estado}]"

    def _validate(self, datos: dict):
        if not datos.get("condicion"):
            return False, "La condicion es obligatoria."
        return True, ""
