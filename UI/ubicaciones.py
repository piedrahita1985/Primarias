import tkinter as tk
from tkinter import ttk

import logica.ubicaciones_logica as _logica
from config.config import COLORS
from UI._base_maestra import MaestraBase, form_label, form_estado

_OPCIONES_UBICACION = ["FREEZER", "NEVERA", "CABINA"]
_SUFIJO = {"FREEZER": "F", "NEVERA": "N", "CABINA": "C"}


def open_window(master):
    UbicacionesWindow(master)


class UbicacionesWindow(MaestraBase):
    TITLE = "Maestra de Ubicaciones"
    LOGICA_MODULE = _logica
    WINDOW_SIZE = "1000x580"
    LIST_TITLE = "Ubicaciones registradas"
    DETAIL_TITLE = "Detalle de la ubicacion"

    # ── Construccion del formulario ──────────────────────

    def _build_form(self, parent):
        self._v_ubicacion = tk.StringVar()
        self._v_no_caja   = tk.StringVar()

        f = tk.Frame(parent, bg=COLORS["secondary"])
        f.pack(fill="both", expand=True)
        for i in range(4):
            f.grid_columnconfigure(i, weight=1)

        # Ubicacion (combobox)
        form_label(f, "Ubicacion", 0, 0, 2)
        self._combo_ubic = ttk.Combobox(
            f,
            textvariable=self._v_ubicacion,
            values=_OPCIONES_UBICACION,
            state="readonly",
            font=("Segoe UI", 10),
        )
        self._combo_ubic.grid(row=1, column=0, columnspan=2, sticky="ew", padx=(0, 10), pady=(2, 6))
        self._combo_ubic.bind("<<ComboboxSelected>>", self._on_ubicacion_change)

        # No. de caja
        form_label(f, "No. Caja", 0, 2, 2)
        self._entry_caja = tk.Entry(
            f,
            textvariable=self._v_no_caja,
            bg=COLORS["surface"],
            fg=COLORS["text_dark"],
            font=("Segoe UI", 10),
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["border_soft"],
            highlightcolor=COLORS["primary"],
        )
        self._entry_caja.grid(row=1, column=2, columnspan=2, sticky="ew", padx=(0, 10), pady=(2, 6))
        self._entry_caja.bind("<FocusOut>", self._auto_suffix)

        # Hint de sufijo
        self._lbl_hint = tk.Label(
            f,
            text="",
            bg=COLORS["secondary"],
            fg=COLORS["primary"],
            font=("Segoe UI", 8, "italic"),
        )
        self._lbl_hint.grid(row=2, column=2, columnspan=2, sticky="w", padx=(0, 10))

        # Estado
        self._lbl_estado = form_estado(f, self._var_estado, 3, 0, 2)

    def _on_ubicacion_change(self, event=None):
        sufijo = _SUFIJO.get(self._v_ubicacion.get().upper(), "")
        if sufijo:
            self._lbl_hint.configure(text=f"El No. caja debe terminar en '{sufijo}'")
        else:
            self._lbl_hint.configure(text="")

    def _auto_suffix(self, event=None):
        """Agrega automaticamente el sufijo correcto al perder el foco."""
        sufijo = _SUFIJO.get(self._v_ubicacion.get().upper(), "")
        val = self._v_no_caja.get().strip()
        if sufijo and val and val[-1].upper() != sufijo:
            self._v_no_caja.set(val + sufijo)

    # ── Interface ────────────────────────────────────────

    def _get_form_data(self) -> dict:
        return {
            "ubicacion": self._v_ubicacion.get().strip(),
            "no_caja":   self._v_no_caja.get().strip(),
        }

    def _set_form_data(self, r: dict):
        self._v_ubicacion.set(r.get("ubicacion", ""))
        self._v_no_caja.set(r.get("no_caja", ""))
        self._on_ubicacion_change()

    def _clear_form(self):
        self._v_ubicacion.set("")
        self._v_no_caja.set("")
        self._lbl_hint.configure(text="")

    def _list_label(self, r: dict) -> str:
        estado   = r.get("estado", "HABILITADA")
        no_caja  = r.get("no_caja", "")
        ubicacion = r.get("ubicacion", "")
        return f"{no_caja} — {ubicacion}  [{estado}]"

    def _validate(self, datos: dict):
        if not datos.get("ubicacion"):
            return False, "Debe seleccionar una ubicacion."
        if not datos.get("no_caja"):
            return False, "El numero de caja es obligatorio."
        sufijo = _SUFIJO.get(datos["ubicacion"].upper(), "")
        if sufijo and datos["no_caja"][-1].upper() != sufijo:
            return False, (
                f"El No. caja para '{datos['ubicacion']}' debe terminar en '{sufijo}'.\n"
                f"Ejemplo: 3{sufijo}"
            )
        return True, ""
