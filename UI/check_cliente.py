"""Lista de Chequeo – Recepción de Sustancias de Referencia enviadas por el Cliente."""
import os
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

from app_paths import resource_path
from config.config import COLORS
from logica import check_logica as chk
from logica import movimientos_common as common
from logica import usuarios_logica as usr
from UI._mov_utils import (
    draw_title,
    get_date_value,
    make_date_input,
    make_labeled_entry,
    only_numeric,
    upper_text_var,
)
from UI.check_cecif import FirmaSelector, VerifRow


def open_window(master):
    CheckClienteWindow(master)


# ---------------------------------------------------------------------------
# Client checklist window
# ---------------------------------------------------------------------------

class CheckClienteWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Lista de Chequeo – Recepción Sustancias de Referencia por el Cliente")
        self.configure(bg=COLORS["secondary"])
        self.geometry("1100x900")
        self.minsize(900, 720)

        self._maestras = common.cargar_maestras()
        self._sustancias_by_codigo = common.map_sustancia_by_codigo(self._maestras["sustancias"])
        self._sustancias_codigos = sorted(self._sustancias_by_codigo.keys(), key=lambda x: (len(x), x))
        self._usuarios = usr.cargar()

        self._current_sustancia = None
        self._clientes_items = chk.cargar_clientes()
        self._wheel_active = False
        self._verif_nuevas: dict[str, VerifRow] = {}
        self._verif_destapadas: dict[str, VerifRow] = {}
        self._canvas = None

        self._build_ui()
        self.bind("<Enter>", self._activate_wheel)
        self.bind("<Leave>", self._deactivate_wheel)
        self.bind("<Destroy>", self._on_destroy)

    # ------------------------------------------------------------------
    # Scroll
    # ------------------------------------------------------------------
    def _activate_wheel(self, _e=None):
        if self._wheel_active:
            return
        self.bind_all("<MouseWheel>", self._on_wheel)
        self._wheel_active = True

    def _deactivate_wheel(self, _e=None):
        if not self._wheel_active:
            return
        self.unbind_all("<MouseWheel>")
        self._wheel_active = False

    def _on_wheel(self, event):
        if self._canvas:
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_destroy(self, _e=None):
        self._deactivate_wheel()

    # ------------------------------------------------------------------
    # UI build
    # ------------------------------------------------------------------
    def _build_ui(self):
        draw_title(self, "LISTA DE CHEQUEO  –  RECEPCIÓN SUSTANCIAS DE REFERENCIA  /  CLIENTE")

        wrap = tk.Frame(self, bg=COLORS["secondary"])
        wrap.pack(fill="both", expand=True, padx=10, pady=(8, 4))
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)

        self._canvas = tk.Canvas(wrap, bg=COLORS["secondary"], highlightthickness=0)
        ysb = tk.Scrollbar(wrap, orient="vertical", command=self._canvas.yview)
        self._form = tk.Frame(self._canvas, bg=COLORS["secondary"])

        self._form.bind("<Configure>", lambda _: self._canvas.configure(
            scrollregion=self._canvas.bbox("all")))
        _win = self._canvas.create_window((0, 0), window=self._form, anchor="nw")
        self._canvas.configure(yscrollcommand=ysb.set)
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfigure(_win, width=e.width))

        self._canvas.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")

        self._build_section_recepcion()
        self._build_section_producto()
        self._build_section_nuevas()
        self._build_section_destapadas()
        self._build_section_observaciones()
        self._build_section_firmas()

        bar = tk.Frame(self, bg=COLORS["secondary"])
        bar.pack(fill="x", padx=10, pady=(4, 10))
        self._btn("Guardar", COLORS["primary"], self._save).pack(side="right", padx=6)
        self._btn("Limpiar", "#6C757D", self._clear).pack(side="left", padx=6)
        self._btn("Salir", "#6C757D", self.destroy).pack(side="right")

    # ------------------------------------------------------------------
    # Sections
    # ------------------------------------------------------------------
    def _sec(self, title):
        f = tk.LabelFrame(self._form, text=f"  {title}  ",
                          bg=COLORS["secondary"], fg=COLORS["primary_dark"],
                          font=("Segoe UI", 10, "bold"), bd=1, relief="groove", padx=6, pady=4)
        f.pack(fill="x", padx=6, pady=6)
        return f

    def _build_section_recepcion(self):
        sec = self._sec("Datos de recepción")
        for c in range(2):
            sec.grid_columnconfigure(c, weight=1)

        self.w_fecha_recepcion = make_date_input(sec, 0, 0, "Fecha Recepción",
                                                 allow_past=True, empty_default=False)

        self.v_nombre_cliente = tk.StringVar()
        upper_text_var(self.v_nombre_cliente)
        make_labeled_entry(sec, "Nombre del Cliente", self.v_nombre_cliente, 0, 1, width=40)

    def _build_section_producto(self):
        sec = self._sec("Sustancia de referencia recibida")
        for c in range(4):
            sec.grid_columnconfigure(c, weight=1)

        tk.Label(sec, text="Código Producto", bg=COLORS["secondary"], fg=COLORS["text_dark"],
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", padx=8, pady=(6, 2))
        self.v_codigo = tk.StringVar()
        self.cb_codigo = ttk.Combobox(sec, textvariable=self.v_codigo,
                                      values=self._sustancias_codigos, state="normal",
                                      font=("Segoe UI", 10))
        self.cb_codigo.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        self.cb_codigo.bind("<KeyRelease>", self._on_codigo_key)
        self.cb_codigo.bind("<<ComboboxSelected>>", self._on_codigo_selected)
        self.cb_codigo.bind("<FocusOut>", self._on_codigo_focusout)

        self.v_cantidad = tk.StringVar()
        e_cant = make_labeled_entry(sec, "Cantidad", self.v_cantidad, 0, 1)
        e_cant.bind("<KeyPress>", only_numeric)

        self.v_obs_prod = tk.StringVar()
        upper_text_var(self.v_obs_prod)
        make_labeled_entry(sec, "Observación", self.v_obs_prod, 0, 2, width=40)

        self.v_nombre = tk.StringVar()
        # Nombre autocompleted, span 4 cols
        tk.Label(sec, text="Nombre de la Sustancia", bg=COLORS["secondary"], fg=COLORS["text_dark"],
                 font=("Segoe UI", 9, "bold")).grid(row=2, column=0, sticky="w", padx=8, pady=(6, 2))
        tk.Entry(sec, textvariable=self.v_nombre, state="readonly", font=("Segoe UI", 10),
                 bg=COLORS["surface"], fg=COLORS["text_dark"], relief="flat", bd=0,
                 highlightthickness=1, highlightbackground=COLORS["border_soft"],
                 highlightcolor=COLORS["primary"],
                 ).grid(row=3, column=0, columnspan=4, sticky="ew", padx=8, pady=(0, 8))

    def _build_section_nuevas(self):
        sec = self._sec("1. Verificación – Sustancias Nuevas (selladas)")
        sec.grid_columnconfigure(0, weight=1)
        for i, (key, label) in enumerate(chk.VERIFICACION_NUEVAS_CAMPOS):
            row = VerifRow(sec, label, COLORS["secondary"])
            row.grid(row=i, column=0, sticky="ew", padx=4, pady=1)
            self._verif_nuevas[key] = row

    def _build_section_destapadas(self):
        sec = self._sec("2. Verificación – Sustancias ya Destapadas o Reenvasadas por el Cliente")
        sec.grid_columnconfigure(0, weight=1)
        for i, (key, label) in enumerate(chk.VERIFICACION_DESTAPADAS_CAMPOS):
            row = VerifRow(sec, label, COLORS["secondary"])
            row.grid(row=i, column=0, sticky="ew", padx=4, pady=1)
            self._verif_destapadas[key] = row

    def _build_section_observaciones(self):
        sec = self._sec("Observaciones")
        self.txt_obs = tk.Text(sec, height=4, bg=COLORS["surface"], fg=COLORS["text_dark"],
                               font=("Segoe UI", 10), relief="flat", bd=0,
                               highlightthickness=1, highlightbackground=COLORS["border_soft"],
                               highlightcolor=COLORS["primary"])
        self.txt_obs.pack(fill="x", padx=4, pady=4)
        self.txt_obs.bind("<KeyRelease>", self._obs_upper)

    def _build_section_firmas(self):
        sec = self._sec("Firmas")
        sec.grid_columnconfigure(0, weight=1)
        sec.grid_columnconfigure(1, weight=1)

        self.firma_reviso = FirmaSelector(sec, "Revisó", self._usuarios, COLORS["secondary"])
        self.firma_reviso.grid(row=0, column=0, sticky="nsew", padx=8, pady=4)

        self.firma_verifico = FirmaSelector(sec, "Verificó", self._usuarios, COLORS["secondary"])
        self.firma_verifico.grid(row=0, column=1, sticky="nsew", padx=8, pady=4)

        self.firma_reviso.set_other(self.firma_verifico)
        self.firma_verifico.set_other(self.firma_reviso)
        self.firma_reviso._refresh_options()
        self.firma_verifico._refresh_options()

    # ------------------------------------------------------------------
    # Code filter (same as entradas.py)
    # ------------------------------------------------------------------
    def _on_codigo_key(self, event=None):
        typed = self.v_codigo.get().strip()
        ordered = self._ordered_codes(typed)
        self.cb_codigo.configure(values=ordered)
        if not typed:
            self._clear_code_fields()
            return
        if not any(typed in c for c in self._sustancias_codigos):
            self.v_codigo.set("")
            self._clear_code_fields()
            return
        match = next((c for c in ordered if typed in c), None)
        if match is None:
            return
        if event and event.keysym not in {"BackSpace", "Left", "Right", "Up", "Down"}:
            self.v_codigo.set(match)
            self.cb_codigo.icursor(len(typed))
            self.cb_codigo.selection_range(len(typed), len(match))
        if typed == match:
            self._fill_sustancia(match)

    def _on_codigo_selected(self, _event=None):
        self._fill_sustancia(self.v_codigo.get().strip())

    def _on_codigo_focusout(self, _event=None):
        codigo = self.v_codigo.get().strip()
        if codigo in self._sustancias_by_codigo:
            self._fill_sustancia(codigo)
            return
        if codigo:
            self.v_codigo.set("")
        self._clear_code_fields()

    def _ordered_codes(self, typed):
        txt = str(typed or "").strip()
        if not txt:
            return list(self._sustancias_codigos)
        return sorted(
            self._sustancias_codigos,
            key=lambda code: (
                txt not in code,
                code.find(txt) if txt in code else 10**9,
                len(code),
                code,
            ),
        )

    def _fill_sustancia(self, codigo):
        s = self._sustancias_by_codigo.get(codigo)
        self._current_sustancia = s
        if s is None:
            self._clear_code_fields()
            return
        self.v_nombre.set(s.get("nombre", ""))

    def _clear_code_fields(self):
        self._current_sustancia = None
        self.v_nombre.set("")

    # ------------------------------------------------------------------
    # Misc helpers
    # ------------------------------------------------------------------
    def _obs_upper(self, _e=None):
        val = self.txt_obs.get("1.0", "end-1c")
        up = val.upper()
        if val != up:
            pos = self.txt_obs.index("insert")
            self.txt_obs.delete("1.0", "end")
            self.txt_obs.insert("1.0", up)
            self.txt_obs.mark_set("insert", pos)

    def _btn(self, text, bg, cmd):
        return tk.Button(self, text=text, bg=bg, fg="white",
                         font=("Segoe UI", 10, "bold"), relief="flat", bd=0,
                         padx=14, pady=6, cursor="hand2", command=cmd)

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------
    def _save(self):
        # --- Campos obligatorios ---
        fecha = get_date_value(self.w_fecha_recepcion)
        if not fecha:
            messagebox.showwarning("Aviso", "Ingrese la Fecha de Recepción.", parent=self)
            return

        nombre_cliente = self.v_nombre_cliente.get().strip()
        if not nombre_cliente:
            messagebox.showwarning("Aviso", "Ingrese el Nombre del Cliente.", parent=self)
            return

        if self._current_sustancia is None:
            messagebox.showwarning("Aviso", "Seleccione un Código de Producto válido.", parent=self)
            return

        if not self.v_cantidad.get().strip():
            messagebox.showwarning("Aviso", "Ingrese la Cantidad.", parent=self)
            return

        # --- Verificación: todos los ítems deben estar respondidos ---
        unanswered = []
        for key, label in chk.VERIFICACION_NUEVAS_CAMPOS:
            if not self._verif_nuevas[key].get():
                unanswered.append(f"[Nuevas] {label}")
        for key, label in chk.VERIFICACION_DESTAPADAS_CAMPOS:
            if not self._verif_destapadas[key].get():
                unanswered.append(f"[Destapadas] {label}")
        if unanswered:
            messagebox.showwarning(
                "Verificación incompleta",
                "Responda todos los ítems de verificación:\n• " + "\n• ".join(unanswered),
                parent=self,
            )
            return

        # --- Firmas obligatorias ---
        if self.firma_reviso.get_id() is None:
            messagebox.showwarning("Aviso", "Seleccione el usuario que Revisó.", parent=self)
            return
        if self.firma_verifico.get_id() is None:
            messagebox.showwarning("Aviso", "Seleccione el usuario que Verificó.", parent=self)
            return

        verificacion_nuevas = {key: row.get() for key, row in self._verif_nuevas.items()}
        verificacion_destapadas = {key: row.get() for key, row in self._verif_destapadas.items()}

        datos = {
            "fecha_recepcion": fecha,
            "nombre_cliente": nombre_cliente,
            "id_sustancia": self._current_sustancia["id"],
            "cantidad": self.v_cantidad.get().strip(),
            "observacion_producto": self.v_obs_prod.get().strip(),
            "verificacion_nuevas": verificacion_nuevas,
            "verificacion_destapadas": verificacion_destapadas,
            "observaciones": self.txt_obs.get("1.0", "end-1c").strip(),
            "id_usuario_reviso": self.firma_reviso.get_id(),
            "id_usuario_verifico": self.firma_verifico.get_id(),
        }

        prefill = {
            "codigo": self.v_codigo.get().strip(),
            "cantidad": self.v_cantidad.get().strip(),
            "fecha_entrada": fecha,
            "cert_anl": verificacion_nuevas.get("certificado_calidad") == "Si",
            "ficha_seg": verificacion_nuevas.get("ficha_seguridad") == "Si",
        }

        chk.guardar_cliente_nuevo(self._clientes_items, datos)
        messagebox.showinfo("Guardado", "Lista de chequeo de Cliente guardada exitosamente.", parent=self)
        self._clear()
        if messagebox.askyesno("Continuar", "¿Desea registrar la entrada de este producto?", parent=self):
            from UI.entradas import EntradasWindow
            EntradasWindow(self.master, prefill=prefill)

    # ------------------------------------------------------------------
    # Clear
    # ------------------------------------------------------------------
    def _clear(self):
        try:
            self.w_fecha_recepcion.delete(0, "end")
        except Exception:
            pass
        self.v_nombre_cliente.set("")
        self.v_codigo.set("")
        self.v_cantidad.set("")
        self.v_obs_prod.set("")
        self.v_nombre.set("")
        self._current_sustancia = None
        for row in self._verif_nuevas.values():
            row.set("N/A")
        for row in self._verif_destapadas.values():
            row.set("N/A")
        self.txt_obs.delete("1.0", "end")
        self.firma_reviso.var.set("")
        self.firma_reviso._clear_firma()
        self.firma_reviso._selected_id = None
        self.firma_verifico.var.set("")
        self.firma_verifico._clear_firma()
        self.firma_verifico._selected_id = None
        self.firma_reviso._refresh_options()
        self.firma_verifico._refresh_options()
