import tkinter as tk

import logica.fabricantes_logica as _logica
from config.config import COLORS
from UI._base_maestra import MaestraBase, form_label, form_entry, form_estado


def open_window(master):
    FabricantesWindow(master)


class FabricantesWindow(MaestraBase):
    TITLE = "Maestra de Fabricantes"
    LOGICA_MODULE = _logica
    WINDOW_SIZE = "950x560"
    LIST_TITLE = "Fabricantes registrados"
    DETAIL_TITLE = "Detalle del fabricante"

    # ── Construccion del formulario ──────────────────────

    def _build_form(self, parent):
        self._v_fabricante = tk.StringVar()

        f = tk.Frame(parent, bg=COLORS["secondary"])
        f.pack(fill="both", expand=True)
        f.grid_columnconfigure(0, weight=1)
        f.grid_columnconfigure(1, weight=1)

        form_label(f, "Fabricante",    0, 0, 2)
        form_entry(f, self._v_fabricante, 1, 0, 2)

        self._lbl_estado = form_estado(f, self._var_estado, 2, 0, 2)

    # ── Interface ────────────────────────────────────────

    def _get_form_data(self) -> dict:
        return {"fabricante": self._v_fabricante.get().strip()}

    def _set_form_data(self, r: dict):
        self._v_fabricante.set(r.get("fabricante", ""))

    def _clear_form(self):
        self._v_fabricante.set("")

    def _list_label(self, r: dict) -> str:
        estado = r.get("estado", "HABILITADA")
        return f"{r.get('fabricante', '')}  [{estado}]"

    def _validate(self, datos: dict):
        if not datos.get("fabricante"):
            return False, "El nombre del fabricante es obligatorio."
        return True, ""
