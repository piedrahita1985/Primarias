import tkinter as tk

import logica.sustancias_logica as _logica
from config.config import COLORS
from UI._base_maestra import MaestraBase, form_label, form_entry, form_estado


def open_window(master):
    SustanciasWindow(master)


class SustanciasWindow(MaestraBase):
    TITLE = "Maestra de Sustancias"
    LOGICA_MODULE = _logica
    WINDOW_SIZE = "1200x680"
    LIST_TITLE = "Sustancias registradas"
    DETAIL_TITLE = "Detalle de la sustancia"

    # ── Construccion del formulario ──────────────────────

    def _build_form(self, parent):
        self._v_codigo          = tk.StringVar()
        self._v_nombre          = tk.StringVar()
        self._v_propiedad       = tk.StringVar()
        self._v_tipo_muestras   = tk.StringVar()
        self._v_uso_previsto    = tk.StringVar()
        self._v_cantidad_minima = tk.StringVar()
        self._v_codigo_sistema  = tk.StringVar()

        f = tk.Frame(parent, bg=COLORS["secondary"])
        f.pack(fill="both", expand=True)
        for i in range(6):
            f.grid_columnconfigure(i, weight=1)

        # Fila 0-1: Codigo | Nombre | Propiedad
        form_label(f, "Codigo",              0, 0, 2)
        form_entry(f, self._v_codigo,        1, 0, 2)

        form_label(f, "Nombre del Producto", 0, 2, 2)
        form_entry(f, self._v_nombre,        1, 2, 2)

        form_label(f, "Propiedad",           0, 4, 2)
        form_entry(f, self._v_propiedad,     1, 4, 2)

        # Fila 2-3: Tipo Muestras | Uso Previsto
        form_label(f, "Tipo de Muestras",    2, 0, 3)
        form_entry(f, self._v_tipo_muestras, 3, 0, 3)

        form_label(f, "Uso Previsto",        2, 3, 3)
        form_entry(f, self._v_uso_previsto,  3, 3, 3)

        # Fila 4-5: Cantidad Minima | Codigo Sistema | Estado
        form_label(f, "Cantidad Minima",        4, 0, 2)
        form_entry(f, self._v_cantidad_minima,  5, 0, 2)

        form_label(f, "Codigo Sistema",         4, 2, 2)
        form_entry(f, self._v_codigo_sistema,   5, 2, 2)

        self._lbl_estado = form_estado(f, self._var_estado, 4, 4, 2)

    # ── Interface ────────────────────────────────────────

    def _get_form_data(self) -> dict:
        return {
            "codigo":          self._v_codigo.get().strip(),
            "nombre":          self._v_nombre.get().strip(),
            "propiedad":       self._v_propiedad.get().strip(),
            "tipo_muestras":   self._v_tipo_muestras.get().strip(),
            "uso_previsto":    self._v_uso_previsto.get().strip(),
            "cantidad_minima": self._v_cantidad_minima.get().strip(),
            "codigo_sistema":  self._v_codigo_sistema.get().strip(),
        }

    def _set_form_data(self, r: dict):
        self._v_codigo.set(r.get("codigo", ""))
        self._v_nombre.set(r.get("nombre", ""))
        self._v_propiedad.set(r.get("propiedad", ""))
        self._v_tipo_muestras.set(r.get("tipo_muestras", ""))
        self._v_uso_previsto.set(r.get("uso_previsto", ""))
        self._v_cantidad_minima.set(r.get("cantidad_minima", ""))
        self._v_codigo_sistema.set(r.get("codigo_sistema", ""))

    def _clear_form(self):
        for v in (
            self._v_codigo, self._v_nombre, self._v_propiedad,
            self._v_tipo_muestras, self._v_uso_previsto,
            self._v_cantidad_minima, self._v_codigo_sistema,
        ):
            v.set("")

    def _list_label(self, r: dict) -> str:
        estado = r.get("estado", "HABILITADA")
        return f"{r.get('codigo', '')} - {r.get('nombre', '')}  [{estado}]"

    def _validate(self, datos: dict):
        if not datos.get("codigo") or not datos.get("nombre"):
            return False, "El codigo y el nombre son obligatorios."
        return True, ""
