import tkinter as tk

import logica.tipos_salida_logica as _logica
from config.config import COLORS
from UI._base_maestra import MaestraBase, form_entry, form_estado, form_label


def open_window(master):
    TiposSalidaWindow(master)


class TiposSalidaWindow(MaestraBase):
    TITLE = "Maestra de Tipos de Salida"
    LOGICA_MODULE = _logica
    WINDOW_SIZE = "950x560"
    LIST_TITLE = "Tipos de salida registrados"
    DETAIL_TITLE = "Detalle del tipo de salida"

    def _build_form(self, parent):
        self._v_tipo = tk.StringVar()

        frame = tk.Frame(parent, bg=COLORS["secondary"])
        frame.pack(fill="both", expand=True)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=1)

        form_label(frame, "Tipo de Salida", 0, 0, 2)
        form_entry(frame, self._v_tipo, 1, 0, 2)

        self._lbl_estado = form_estado(frame, self._var_estado, 2, 0, 2)

    def _get_form_data(self) -> dict:
        return {"tipo_salida": self._v_tipo.get().strip().upper()}

    def _set_form_data(self, record: dict):
        self._v_tipo.set(record.get("tipo_salida", ""))

    def _clear_form(self):
        self._v_tipo.set("")

    def _list_label(self, record: dict) -> str:
        estado = record.get("estado", "HABILITADA")
        return f"{record.get('tipo_salida', '')}  [{estado}]"

    def _validate(self, datos: dict):
        if not datos.get("tipo_salida"):
            return False, "El tipo de salida es obligatorio."
        return True, ""
