import tkinter as tk
from tkinter import messagebox, ttk

from config.config import COLORS
from logica import entradas_mov_logica as ent
from logica import inventario_mov_logica as inv
from logica import movimientos_common as common
from UI._mov_utils import (
    attach_treeview_sorting,
    apply_default_window,
    draw_title,
    get_date_value,
    make_date_input,
    make_date_widget,
    make_labeled_entry,
    only_numeric,
    upper_text_var,
    validate_today_or_future,
)


def open_window(master):
    _ChecklistDialog(master)


class _ChecklistDialog(tk.Toplevel):
    """Ask user whether to fill a checklist before the entry form."""

    def __init__(self, master):
        super().__init__(master)
        self.title("Recepción de Compra")
        self.configure(bg=COLORS["secondary"])
        self.resizable(False, False)
        self.grab_set()

        # Center on screen
        self.update_idletasks()
        w, h = 420, 180
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

        tk.Label(
            self,
            text="¿Desea realizar lista de chequeo?",
            bg=COLORS["secondary"],
            fg=COLORS["text_dark"],
            font=("Segoe UI", 12, "bold"),
            wraplength=380,
            justify="center",
        ).pack(pady=(28, 20))

        btn_frame = tk.Frame(self, bg=COLORS["secondary"])
        btn_frame.pack()

        def _btn(text, bg, cmd):
            return tk.Button(
                btn_frame, text=text, bg=bg, fg="white",
                font=("Segoe UI", 10, "bold"), relief="flat",
                padx=16, pady=6, cursor="hand2", command=cmd,
            )

        _btn("CECIF", COLORS["primary"], self._open_cecif).pack(side="left", padx=8)
        _btn("Cliente", "#2EAF62", self._open_cliente).pack(side="left", padx=8)
        _btn("Omitir", "#6C757D", self._open_entrada).pack(side="left", padx=8)
        _btn("Salir", "#6C757D", self.destroy).pack(side="left", padx=8)

    def _open_cecif(self):
        self.destroy()
        from UI import check_cecif
        check_cecif.open_window(self.master)

    def _open_cliente(self):
        self.destroy()
        from UI import check_cliente
        check_cliente.open_window(self.master)

    def _open_entrada(self):
        self.destroy()
        EntradasWindow(self.master)


class EntradasWindow(tk.Toplevel):
    def __init__(self, master, prefill=None):
        super().__init__(master)
        self._prefill = prefill
        self.username = getattr(master, "username", "SISTEMA")
        self.title("Sistema de Gestion - Entradas")
        self.configure(bg=COLORS["secondary"])
        apply_default_window(self, min_width=1100, min_height=700)

        self._maestras = common.cargar_maestras()
        self._sustancias_by_codigo = common.map_sustancia_by_codigo(self._maestras["sustancias"])
        self._sustancias_by_id = common.map_by_id(self._maestras["sustancias"])
        self._sustancias_codigos = sorted(self._sustancias_by_codigo.keys(), key=lambda x: (len(x), x))
        self._unidades_by_id = common.map_by_id(self._maestras["unidades"])
        self._tipos_entrada_by_id = common.map_by_id(self._maestras["tipos_entrada"])
        self._tipos_entrada = [
            r.get("tipo_entrada", "")
            for r in self._maestras["tipos_entrada"]
            if r.get("tipo_entrada")
        ]
        self._fabricantes_by_nombre = {
            str(f.get("fabricante", "")).strip().upper(): f
            for f in self._maestras["fabricantes"]
        }

        self._current_sustancia = None
        self._editing_id = None
        self._lotes_sugeridos = []
        self._form_canvas = None
        self._wheel_active = False

        self._vars()
        self._build_ui()
        self._set_default_tipo_entrada()
        self._refresh_list()
        self._load_history_default()

        self.bind("<Enter>", self._activate_wheel)
        self.bind("<Leave>", self._deactivate_wheel)
        self.bind("<Destroy>", self._on_destroy)
        if self._prefill:
            self.after(100, self._apply_prefill)

    def _vars(self):
        self.v_tipo_entrada = tk.StringVar()
        self.v_codigo = tk.StringVar()
        self.v_nombre = tk.StringVar()
        self.v_propiedad = tk.StringVar()
        self.v_codigo_sistema = tk.StringVar()
        self.v_lote = tk.StringVar()
        self.v_catalogo = tk.StringVar()
        self.v_cantidad = tk.StringVar()
        self.v_presentacion = tk.StringVar()
        self.v_total_neto = tk.StringVar()
        self.v_unidad = tk.StringVar()
        self.v_potencia = tk.StringVar()
        self.v_costo_unitario = tk.StringVar()
        self.v_costo_total = tk.StringVar(value="0")
        self.v_factura = tk.StringVar()
        self.v_ubicacion_tipo = tk.StringVar()
        self.v_no_caja = tk.StringVar()
        self.v_condicion = tk.StringVar()
        self.v_color_refuerzo = tk.StringVar()

        self.v_cert_anl = tk.BooleanVar(value=False)
        self.v_ficha_seg = tk.BooleanVar(value=False)
        self.v_factura_compra = tk.BooleanVar(value=False)

        self.h_codigo = tk.StringVar()
        self.h_lote = tk.StringVar()

        for var in [
            self.v_tipo_entrada,
            self.v_lote,
            self.v_catalogo,
            self.v_potencia,
            self.v_factura,
        ]:
            upper_text_var(var)

    def _build_ui(self):
        draw_title(self, "Sistema de Gestion - Entradas")

        top = tk.Frame(self, bg=COLORS["secondary"])
        top.pack(fill="x", expand=False, padx=10, pady=(10, 6))
        top.grid_columnconfigure(0, weight=1)
        top.grid_rowconfigure(0, weight=1)

        right = tk.LabelFrame(
            top,
            text="  Registro de entrada  ",
            bg=COLORS["secondary"],
            fg=COLORS["text_dark"],
            font=("Segoe UI", 9, "bold"),
        )
        right.grid(row=0, column=0, sticky="nsew")
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)

        canvas = tk.Canvas(right, bg=COLORS["secondary"], highlightthickness=0)
        self._form_canvas = canvas
        ysb = tk.Scrollbar(right, orient="vertical", command=canvas.yview)
        form = tk.Frame(canvas, bg=COLORS["secondary"])

        form.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        win_id = canvas.create_window((0, 0), window=form, anchor="nw")
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win_id, width=e.width))
        canvas.configure(yscrollcommand=ysb.set)

        canvas.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")

        self._build_sections(form)

        bar = tk.Frame(self, bg=COLORS["secondary"])
        bar.pack(side="bottom", fill="x", padx=10, pady=(0, 10))
        self.lbl_status = tk.Label(
            bar,
            text="Listo para registrar entrada.",
            bg=COLORS["secondary"],
            fg=COLORS["text_muted"],
            font=("Segoe UI", 9),
            anchor="w",
        )
        self.lbl_status.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._button(bar, "Salir", "#6C757D", self.destroy).pack(side="right")
        self._button(bar, "Guardar", COLORS["primary"], self._save).pack(side="right", padx=(0, 6))
        self._button(bar, "Nuevo", "#6C757D", self._clear_form).pack(side="left", padx=(0, 6))

        self._build_history()

    def _build_history(self):
        hist = tk.LabelFrame(
            self,
            text="  Historial de Entradas  ",
            bg=COLORS["secondary"],
            fg=COLORS["primary_dark"],
            font=("Segoe UI", 10, "bold"),
        )
        hist.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        ftop = tk.Frame(hist, bg=COLORS["secondary"])
        ftop.pack(fill="x", padx=6, pady=(6, 4))
        _e_style = dict(bg=COLORS["surface"], fg=COLORS["text_dark"], font=("Segoe UI", 10),
                        relief="flat", bd=0, highlightthickness=1,
                        highlightbackground=COLORS["border_soft"], highlightcolor=COLORS["primary"])
        def _lbl(t):
            return tk.Label(ftop, text=t, bg=COLORS["secondary"], fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold"))
        _lbl("Desde:").pack(side="left", padx=(0, 3))
        self.h_w_desde = make_date_widget(ftop)
        self.h_w_desde.pack(side="left", padx=(0, 10))
        _lbl("Hasta:").pack(side="left", padx=(0, 3))
        self.h_w_hasta = make_date_widget(ftop)
        self.h_w_hasta.pack(side="left", padx=(0, 10))
        _lbl("Codigo:").pack(side="left", padx=(0, 3))
        tk.Entry(ftop, textvariable=self.h_codigo, width=10, **_e_style).pack(side="left", padx=(0, 10))
        _lbl("Lote:").pack(side="left", padx=(0, 3))
        tk.Entry(ftop, textvariable=self.h_lote, width=10, **_e_style).pack(side="left", padx=(0, 10))
        self._button(ftop, "Filtrar", COLORS["primary"], self._apply_filters).pack(side="left", padx=(0, 6))
        self._button(ftop, "Borrar filtros", "#B0B0B0", self._clear_filters).pack(side="left")

        cols = ("id", "fecha", "codigo", "nombre", "lote", "total", "unidad", "estado")
        self.h_tree = ttk.Treeview(hist, columns=cols, show="headings", height=8)
        for key, title, width in [
            ("id", "ID", 60),
            ("fecha", "Fecha", 110),
            ("codigo", "Codigo", 90),
            ("nombre", "Nombre", 290),
            ("lote", "Lote", 100),
            ("total", "Total", 90),
            ("unidad", "Unidad", 80),
            ("estado", "Estado", 90),
        ]:
            self.h_tree.heading(key, text=title)
            self.h_tree.column(key, width=width, anchor="center")
        attach_treeview_sorting(self.h_tree)
        self.h_tree.pack(fill="both", expand=True, padx=6)

        ysb = ttk.Scrollbar(hist, orient="vertical", command=self.h_tree.yview)
        self.h_tree.configure(yscrollcommand=ysb.set)
        ysb.place(relx=0.996, rely=0.22, relheight=0.58, anchor="ne")

        fbot = tk.Frame(hist, bg=COLORS["secondary"])
        fbot.pack(fill="x", padx=6, pady=6)
        self._button(fbot, "Editar seleccionado", COLORS["primary_dark"], self._edit_selected).pack(side="left", padx=(0, 6))
        self._button(fbot, "Anular seleccionado", COLORS["error"], self._cancel_selected).pack(side="left")
        self._button(fbot, "Actualizar", "#BDBDBD", self._load_history_default).pack(side="right")

    def _build_sections(self, parent):
        sec1 = self._section(parent, "Informacion General")
        for c in range(4):
            sec1.grid_columnconfigure(c, weight=1)

        self.w_fecha_entrada = make_date_input(sec1, 0, 0, "Fecha Ingreso", allow_past=True, empty_default=True)

        tk.Label(sec1, text="Tipo Entrada", bg=COLORS["secondary"], fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold")).grid(row=0, column=1, sticky="w", padx=8, pady=(6, 2))
        self.cb_tipo_entrada = ttk.Combobox(sec1, textvariable=self.v_tipo_entrada, values=self._tipos_entrada, state="readonly", font=("Segoe UI", 10))
        self.cb_tipo_entrada.grid(row=1, column=1, sticky="ew", padx=8, pady=(0, 8))

        tk.Label(sec1, text="Codigo de Uso", bg=COLORS["secondary"], fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold")).grid(row=0, column=2, sticky="w", padx=8, pady=(6, 2))
        self.cb_codigo = ttk.Combobox(sec1, textvariable=self.v_codigo, values=self._sustancias_codigos, state="normal", font=("Segoe UI", 10))
        self.cb_codigo.grid(row=1, column=2, sticky="ew", padx=8, pady=(0, 8))
        self.cb_codigo.bind("<KeyRelease>", self._on_codigo_key)
        self.cb_codigo.bind("<<ComboboxSelected>>", self._on_codigo_selected)
        self.cb_codigo.bind("<FocusOut>", self._on_codigo_focusout)

        tk.Label(sec1, text="Lote", bg=COLORS["secondary"], fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold")).grid(row=0, column=3, sticky="w", padx=8, pady=(6, 2))
        self.cb_lote = ttk.Combobox(sec1, textvariable=self.v_lote, values=[], state="normal", font=("Segoe UI", 10))
        self.cb_lote.grid(row=1, column=3, sticky="ew", padx=8, pady=(0, 8))
        make_labeled_entry(sec1, "Catalogo", self.v_catalogo, 2, 3, width=18)

        make_labeled_entry(sec1, "Nombre del Producto", self.v_nombre, 2, 0, read_only=True)
        make_labeled_entry(sec1, "Propiedad", self.v_propiedad, 2, 1, read_only=True)
        make_labeled_entry(sec1, "Codigo Sistema", self.v_codigo_sistema, 2, 2, read_only=True)

        # Bloque doble para evitar scroll vertical: detalles a la izquierda, costos/facturación a la derecha.
        details_wrap = tk.Frame(parent, bg=COLORS["secondary"])
        details_wrap.pack(fill="x", padx=6, pady=6)
        details_wrap.grid_columnconfigure(0, weight=3)
        details_wrap.grid_columnconfigure(1, weight=2)

        sec2 = tk.LabelFrame(
            details_wrap,
            text="  Detalles del Producto  ",
            bg=COLORS["secondary"],
            fg=COLORS["primary_dark"],
            font=("Segoe UI", 10, "bold"),
            bd=1,
            relief="groove",
            padx=6,
            pady=4,
        )
        sec2.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        for c in range(5):
            sec2.grid_columnconfigure(c, weight=1)

        e_cantidad = make_labeled_entry(sec2, "Cantidad", self.v_cantidad, 0, 0)
        e_present = make_labeled_entry(sec2, "Presentacion", self.v_presentacion, 0, 1)
        make_labeled_entry(sec2, "Total (contenido neto)", self.v_total_neto, 0, 2, read_only=True)

        tk.Label(sec2, text="Unidad", bg=COLORS["secondary"], fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold")).grid(row=0, column=3, sticky="w", padx=8, pady=(6, 2))
        self.cb_unidad = ttk.Combobox(sec2, textvariable=self.v_unidad, values=[u.get("unidad", "") for u in self._maestras["unidades"] if u.get("unidad")], state="readonly", font=("Segoe UI", 10))
        self.cb_unidad.grid(row=1, column=3, sticky="ew", padx=8, pady=(0, 8))

        e_potencia = make_labeled_entry(sec2, "Potencia", self.v_potencia, 0, 4)

        sec3 = tk.LabelFrame(
            details_wrap,
            text="  Costos y Facturación  ",
            bg=COLORS["secondary"],
            fg=COLORS["primary_dark"],
            font=("Segoe UI", 10, "bold"),
            bd=1,
            relief="groove",
            padx=6,
            pady=4,
        )
        sec3.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        for c in range(3):
            sec3.grid_columnconfigure(c, weight=1)

        e_costo_u = make_labeled_entry(sec3, "Costo Unitario", self.v_costo_unitario, 0, 0, width=14)
        make_labeled_entry(sec3, "Costo Total", self.v_costo_total, 0, 1, width=14, read_only=True)
        make_labeled_entry(sec3, "Factura", self.v_factura, 0, 2, width=14)

        sec4 = self._section(parent, "Documentacion Tecnica")
        for c in range(4):
            sec4.grid_columnconfigure(c, weight=1)

        tk.Checkbutton(sec4, text="Certificado Anl.", variable=self.v_cert_anl, bg=COLORS["secondary"], fg=COLORS["text_dark"], font=("Segoe UI", 10)).grid(row=0, column=0, sticky="w", padx=8, pady=(6, 2))
        tk.Checkbutton(sec4, text="Ficha Seguridad", variable=self.v_ficha_seg, bg=COLORS["secondary"], fg=COLORS["text_dark"], font=("Segoe UI", 10)).grid(row=0, column=1, sticky="w", padx=8, pady=(6, 2))
        tk.Checkbutton(sec4, text="Factura de compra", variable=self.v_factura_compra, bg=COLORS["secondary"], fg=COLORS["text_dark"], font=("Segoe UI", 10)).grid(row=0, column=2, sticky="w", padx=8, pady=(6, 2))

        self.w_fecha_venc = make_date_input(sec4, 1, 0, "Fecha Vencimiento", allow_past=False, empty_default=True)

        sec5 = self._section(parent, "Almacenamiento y Observaciones")
        for c in range(4):
            sec5.grid_columnconfigure(c, weight=1)

        tk.Label(sec5, text="Ubicación", bg=COLORS["secondary"], fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", padx=8, pady=(6, 2))
        self._ubicaciones_rows = list(self._maestras["ubicaciones"])
        self._ubicacion_tipos = sorted({str(u.get("ubicacion", "")).strip() for u in self._ubicaciones_rows if str(u.get("ubicacion", "")).strip()})
        self._caja_values = []
        self.cb_ubicacion_tipo = ttk.Combobox(
            sec5,
            textvariable=self.v_ubicacion_tipo,
            values=self._ubicacion_tipos,
            state="readonly",
            font=("Segoe UI", 10),
        )
        self.cb_ubicacion_tipo.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        self.cb_ubicacion_tipo.bind("<<ComboboxSelected>>", self._on_ubicacion_tipo_selected)

        tk.Label(sec5, text="No. Caja", bg=COLORS["secondary"], fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold")).grid(row=0, column=1, sticky="w", padx=8, pady=(6, 2))
        self.cb_no_caja = ttk.Combobox(
            sec5,
            textvariable=self.v_no_caja,
            values=[],
            state="disabled",
            font=("Segoe UI", 10),
        )
        self.cb_no_caja.grid(row=1, column=1, sticky="ew", padx=8, pady=(0, 8))

        self.lbl_ubicacion_hint = tk.Label(
            sec5,
            text="Primero elija ubicación para habilitar No. Caja",
            bg=COLORS["secondary"],
            fg=COLORS["text_muted"],
            font=("Segoe UI", 8, "italic"),
        )
        self.lbl_ubicacion_hint.grid(row=2, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 6))

        tk.Label(sec5, text="Condicion de almacenamiento", bg=COLORS["secondary"], fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold")).grid(row=0, column=2, sticky="w", padx=8, pady=(6, 2))
        self._cond_values = []
        for c in self._maestras["condiciones"]:
            self._cond_values.append((c.get("condicion", ""), c.get("id")))
        self.cb_cond = ttk.Combobox(sec5, textvariable=self.v_condicion, values=[x[0] for x in self._cond_values], state="readonly", font=("Segoe UI", 10))
        self.cb_cond.grid(row=1, column=2, sticky="ew", padx=8, pady=(0, 8))

        tk.Label(sec5, text="Color Refuerzo", bg=COLORS["secondary"], fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold")).grid(row=0, column=3, sticky="w", padx=8, pady=(6, 2))
        self._color_values = []
        for c in self._maestras["colores"]:
            self._color_values.append((c.get("color_refuerzo", ""), c.get("id")))
        self.cb_color = ttk.Combobox(sec5, textvariable=self.v_color_refuerzo, values=[x[0] for x in self._color_values], state="readonly", font=("Segoe UI", 10))
        self.cb_color.grid(row=1, column=3, sticky="ew", padx=8, pady=(0, 8))

        tk.Label(sec5, text="Observaciones", bg=COLORS["secondary"], fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold")).grid(row=3, column=0, sticky="w", padx=8, pady=(6, 2))
        self.txt_obs = tk.Text(sec5, height=3, bg=COLORS["surface"], fg=COLORS["text_dark"], font=("Segoe UI", 10), relief="flat", bd=0, highlightthickness=1, highlightbackground=COLORS["border_soft"], highlightcolor=COLORS["primary"])
        self.txt_obs.grid(row=4, column=0, columnspan=4, sticky="ew", padx=8, pady=(0, 10))
        self.txt_obs.bind("<KeyRelease>", self._on_obs_upper)

        for e in [e_cantidad, e_present, e_costo_u]:
            e.bind("<KeyPress>", only_numeric)

        self.v_cantidad.trace_add("write", lambda *_: self._update_total_neto())
        self.v_presentacion.trace_add("write", lambda *_: self._update_total_neto())
        self.v_cantidad.trace_add("write", lambda *_: self._update_costo_total())
        self.v_costo_unitario.trace_add("write", lambda *_: self._update_costo_total())

        e_potencia.bind("<FocusOut>", lambda _: self.v_potencia.set(self.v_potencia.get().upper()))

    def _section(self, parent, title):
        frame = tk.LabelFrame(parent, text=f"  {title}  ", bg=COLORS["secondary"], fg=COLORS["primary_dark"], font=("Segoe UI", 10, "bold"), bd=1, relief="groove", padx=6, pady=4)
        frame.pack(fill="x", padx=6, pady=6)
        return frame

    def _button(self, parent, text, bg, cmd):
        return tk.Button(parent, text=text, bg=bg, fg="white", font=("Segoe UI", 10, "bold"), relief="flat", bd=0, padx=12, pady=6, cursor="hand2", command=cmd)

    def _set_status(self, text, is_error=False):
        if hasattr(self, "lbl_status"):
            self.lbl_status.configure(
                text=text,
                fg=COLORS["error"] if is_error else COLORS["text_muted"],
            )

    def _warn(self, text):
        self._set_status(text, is_error=True)
        messagebox.showwarning("Aviso", text, parent=self)

    def _on_obs_upper(self, _event=None):
        value = self.txt_obs.get("1.0", "end-1c")
        up = value.upper()
        if value != up:
            pos = self.txt_obs.index("insert")
            self.txt_obs.delete("1.0", "end")
            self.txt_obs.insert("1.0", up)
            self.txt_obs.mark_set("insert", pos)

    def _update_costo_total(self):
        try:
            cant = float(self.v_cantidad.get() or 0)
            costo_u = float((self.v_costo_unitario.get() or "0").replace(",", "."))
            self.v_costo_total.set(str(round(cant * costo_u, 4)))
        except ValueError:
            self.v_costo_total.set("0")

    def _update_total_neto(self):
        try:
            cantidad = float((self.v_cantidad.get() or "0").replace(",", "."))
            presentacion = float((self.v_presentacion.get() or "0").replace(",", "."))
        except ValueError:
            self.v_total_neto.set("")
            return
        self.v_total_neto.set(self._fmt_num(cantidad * presentacion))

    @staticmethod
    def _fmt_num(value):
        return f"{value:.4f}".rstrip("0").rstrip(".") if value else "0"

    def _set_default_tipo_entrada(self):
        if self.v_tipo_entrada.get().strip():
            return
        if self._tipos_entrada:
            self.v_tipo_entrada.set(self._tipos_entrada[0])

    def _apply_prefill(self):
        """Pre-populate form fields from checklist data passed at construction."""
        data = self._prefill
        if not data:
            return
        codigo = data.get("codigo", "")
        if codigo and codigo in self._sustancias_by_codigo:
            self.v_codigo.set(codigo)
            self._fill_sustancia(codigo)
        if data.get("lote"):
            self.v_lote.set(data["lote"])
        if data.get("cantidad"):
            self.v_cantidad.set(str(data["cantidad"]))
        if data.get("fecha_entrada"):
            self._set_date_widget(self.w_fecha_entrada, data["fecha_entrada"])
        if data.get("cert_anl"):
            self.v_cert_anl.set(True)
        if data.get("ficha_seg"):
            self.v_ficha_seg.set(True)

    def _on_codigo_key(self, event=None):
        typed = self.v_codigo.get().strip()
        ordered = self._ordered_codes(typed)
        self.cb_codigo.configure(values=ordered)
        if not typed:
            self._clear_auto_fields()
            return

        if not any(typed in c for c in self._sustancias_codigos):
            self.v_codigo.set("")
            self._clear_auto_fields()
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
        self._clear_auto_fields()

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
            self._clear_auto_fields()
            return

        self.v_nombre.set(s.get("nombre", ""))
        self.v_propiedad.set(s.get("propiedad", ""))
        self.v_codigo_sistema.set(s.get("codigo_sistema", ""))
        self._actualizar_lotes_sugeridos(s.get("id"))

        unidad_id = inv.sugerir_unidad_id(s.get("id"))
        if unidad_id and unidad_id in self._unidades_by_id:
            self.v_unidad.set(self._unidades_by_id[unidad_id].get("unidad", ""))

    def _actualizar_lotes_sugeridos(self, id_sustancia):
        entradas = common.cargar_entradas()
        lotes = []
        seen = set()
        for e in entradas:
            if e.get("estado", "ACTIVA") != "ACTIVA":
                continue
            if e.get("id_sustancia") != id_sustancia:
                continue
            lote = str(e.get("lote", "")).strip()
            if not lote or lote in seen:
                continue
            seen.add(lote)
            lotes.append(lote)
        self._lotes_sugeridos = sorted(lotes, key=lambda x: (len(x), x))
        self.cb_lote.configure(values=self._lotes_sugeridos)

    def _clear_auto_fields(self):
        self._current_sustancia = None
        self.v_nombre.set("")
        self.v_propiedad.set("")
        self.v_codigo_sistema.set("")
        self.cb_lote.configure(values=[])
        self.v_lote.set("")

    def _id_from_display(self, pairs, selected_text):
        for text, id_ in pairs:
            if text == selected_text:
                return id_
        return None

    def _on_ubicacion_tipo_selected(self, _event=None):
        self._rebuild_cajas_por_ubicacion(self.v_ubicacion_tipo.get().strip())

    def _rebuild_cajas_por_ubicacion(self, ubicacion_tipo):
        tipo = str(ubicacion_tipo or "").strip()
        self._caja_values = []
        seen = set()
        for row in self._ubicaciones_rows:
            if str(row.get("ubicacion", "")).strip() != tipo:
                continue
            no_caja = str(row.get("no_caja", "")).strip()
            label = no_caja if no_caja else "(SIN CAJA)"
            if label in seen:
                continue
            seen.add(label)
            self._caja_values.append((label, row.get("id")))
        self.cb_no_caja.configure(values=[x[0] for x in self._caja_values])
        if self._caja_values:
            self.cb_no_caja.configure(state="readonly")
            self.lbl_ubicacion_hint.configure(text="Seleccione No. Caja")
            if len(self._caja_values) == 1:
                self.v_no_caja.set(self._caja_values[0][0])
            else:
                self.v_no_caja.set("")
        else:
            self.cb_no_caja.configure(state="disabled")
            self.lbl_ubicacion_hint.configure(text="No hay cajas registradas para esta ubicación")
            self.v_no_caja.set("")

    def _selected_id_ubicacion(self):
        tipo = self.v_ubicacion_tipo.get().strip()
        caja = self.v_no_caja.get().strip()
        if not tipo or not caja:
            return None
        for label, id_ in self._caja_values:
            if label == caja:
                return id_
        return None

    def _set_date_widget(self, widget, value):
        if hasattr(widget, "set_date"):
            try:
                if value:
                    widget.set_date(value)
                else:
                    widget.delete(0, "end")
                return
            except Exception:
                pass
        var = getattr(widget, "_fallback_var", None)
        if var is not None:
            var.set(value or "")

    def _save(self):
        codigo = self.v_codigo.get().strip()
        sustancia = self._sustancias_by_codigo.get(codigo)
        if sustancia is None:
            self._warn("Seleccione un codigo de uso valido.")
            return

        if not self.v_lote.get().strip() or not self.v_catalogo.get().strip() or not self.v_cantidad.get().strip():
            self._warn("Lote, catalogo y cantidad son obligatorios.")
            return

        try:
            cantidad = float(self.v_cantidad.get().replace(",", "."))
        except ValueError:
            self._warn("Cantidad invalida.")
            return
        if cantidad <= 0:
            self._warn("La cantidad debe ser mayor a 0.")
            return

        try:
            presentacion = float((self.v_presentacion.get() or "0").replace(",", "."))
        except ValueError:
            self._warn("Presentacion invalida.")
            return

        if presentacion <= 0:
            self._warn("La presentacion debe ser mayor a 0.")
            return

        fecha_vencimiento = get_date_value(self.w_fecha_venc)
        if not validate_today_or_future(fecha_vencimiento, parent=self, field_name="Fecha de vencimiento"):
            return

        if self._editing_id is not None:
            ya_salida = ent.total_salidas_activas(self._editing_id)
            if cantidad < ya_salida:
                messagebox.showwarning(
                    "Aviso",
                    f"La cantidad no puede ser menor que lo ya retirado ({ya_salida}).",
                    parent=self,
                )
                return

        unidad = self.v_unidad.get().strip()
        if not unidad:
            self._warn("Seleccione la unidad.")
            return

        unidad_id = None
        for u in self._maestras["unidades"]:
            if u.get("unidad", "") == unidad:
                unidad_id = u.get("id")
                break
        if unidad_id is None:
            self._warn("Unidad invalida.")
            return

        tipo_entrada_id = None
        for t in self._maestras["tipos_entrada"]:
            if t.get("tipo_entrada", "") == self.v_tipo_entrada.get().strip():
                tipo_entrada_id = t.get("id")
                break
        if tipo_entrada_id is None:
            self._warn("Seleccione un tipo de entrada valido.")
            return

        id_ubicacion = self._selected_id_ubicacion()
        if id_ubicacion is None:
            self._warn("Seleccione Ubicación y No. Caja válidos.")
            return

        propiedad = str(sustancia.get("propiedad", "")).strip().upper()
        fabricante = self._fabricantes_by_nombre.get(propiedad)

        record = {
            "fecha_entrada": get_date_value(self.w_fecha_entrada),
            "id_tipo_entrada": tipo_entrada_id,
            "id_sustancia": sustancia.get("id"),
            "id_fabricante": fabricante.get("id") if fabricante else None,
            "lote": self.v_lote.get().strip(),
            "catalogo": self.v_catalogo.get().strip(),
            "cantidad": cantidad,
            "presentacion": presentacion,
            "total_contenido": cantidad * presentacion,
            "id_unidad": unidad_id,
            "potencia": self.v_potencia.get().strip(),
            "costo_unitario": float((self.v_costo_unitario.get() or "0").replace(",", ".")),
            "costo_total": float((self.v_costo_total.get() or "0").replace(",", ".")),
            "factura": self.v_factura.get().strip(),
            "certificado_anl": self.v_cert_anl.get(),
            "ficha_seguridad": self.v_ficha_seg.get(),
            "factura_compra": self.v_factura_compra.get(),
            "fecha_vencimiento": fecha_vencimiento,
            "id_ubicacion": id_ubicacion,
            "id_condicion_alm": self._id_from_display(self._cond_values, self.v_condicion.get().strip()),
            "id_color_refuerzo": self._id_from_display(self._color_values, self.v_color_refuerzo.get().strip()),
            "observaciones": self.txt_obs.get("1.0", "end-1c").strip(),
        }

        if self._editing_id is None:
            ent.agregar(record, usuario=self.username)
            self._set_status("Entrada guardada correctamente.")
            messagebox.showinfo("Exito", "Entrada guardada correctamente.", parent=self)
        else:
            ent.actualizar(self._editing_id, record, usuario=self.username)
            self._set_status("Entrada actualizada correctamente.")
            messagebox.showinfo("Exito", "Entrada actualizada correctamente.", parent=self)

        self._refresh_list()
        self._load_history_default()
        self._clear_form()

    def _clear_form(self):
        self._editing_id = None
        for v in [
            self.v_codigo,
            self.v_nombre,
            self.v_propiedad,
            self.v_codigo_sistema,
            self.v_lote,
            self.v_catalogo,
            self.v_cantidad,
            self.v_presentacion,
            self.v_total_neto,
            self.v_unidad,
            self.v_potencia,
            self.v_costo_unitario,
            self.v_costo_total,
            self.v_factura,
            self.v_ubicacion_tipo,
            self.v_no_caja,
            self.v_condicion,
            self.v_color_refuerzo,
        ]:
            v.set("")
        self._set_default_tipo_entrada()
        self.v_cert_anl.set(False)
        self.v_ficha_seg.set(False)
        self.v_factura_compra.set(False)
        self.cb_no_caja.configure(values=[], state="disabled")
        self.lbl_ubicacion_hint.configure(text="Primero elija ubicación para habilitar No. Caja")
        self.txt_obs.delete("1.0", "end")
        self._set_status("Listo para registrar entrada.")

    def _refresh_list(self):
        return

    def _on_mousewheel(self, event):
        if self._form_canvas is None:
            return
        try:
            if event.widget.winfo_toplevel() is not self:
                return
        except Exception:
            return
        self._form_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _activate_wheel(self, _event=None):
        if self._wheel_active:
            return
        self.bind_all("<MouseWheel>", self._on_mousewheel)
        self._wheel_active = True

    def _deactivate_wheel(self, _event=None):
        if not self._wheel_active:
            return
        self.unbind_all("<MouseWheel>")
        self._wheel_active = False

    def _on_destroy(self, _event=None):
        try:
            self._deactivate_wheel()
        except Exception:
            pass

    def _load_history_default(self):
        rows = ent.ultimas_15(self._maestras)
        self._fill_history(rows)

    def _apply_filters(self):
        rows = ent.filtrar(
            fecha="",
            fecha_desde=get_date_value(self.h_w_desde),
            fecha_hasta=get_date_value(self.h_w_hasta),
            codigo=self.h_codigo.get().strip(),
            lote=self.h_lote.get().strip(),
            maestras=self._maestras,
        )
        self._fill_history(rows)

    def _clear_filters(self):
        self._set_date_widget(self.h_w_desde, "")
        self._set_date_widget(self.h_w_hasta, "")
        self.h_codigo.set("")
        self.h_lote.set("")
        self._load_history_default()

    def _fill_history(self, rows):
        self.h_tree.delete(*self.h_tree.get_children())
        for r in rows:
            self.h_tree.insert(
                "",
                "end",
                values=(
                    r.get("id", ""),
                    r.get("fecha_entrada", ""),
                    r.get("codigo", ""),
                    r.get("nombre", ""),
                    r.get("lote", ""),
                    r.get("cantidad", ""),
                    r.get("unidad_nombre", ""),
                    r.get("estado", "ACTIVA"),
                ),
            )

    def _selected_history_id(self):
        sel = self.h_tree.selection()
        if not sel:
            return None
        vals = self.h_tree.item(sel[0], "values")
        if not vals:
            return None
        return int(vals[0])

    def _edit_selected(self):
        id_entrada = self._selected_history_id()
        if id_entrada is None:
            messagebox.showwarning("Aviso", "Seleccione una entrada del historial.", parent=self)
            return

        rows = ent.cargar()
        rec = next((r for r in rows if r.get("id") == id_entrada), None)
        if rec is None:
            return
        if rec.get("estado") == "ANULADA":
            messagebox.showwarning("Aviso", "No se puede editar una entrada anulada.", parent=self)
            return

        self._editing_id = id_entrada
        sust = self._sustancias_by_id.get(rec.get("id_sustancia"), {})
        self.v_codigo.set(str(sust.get("codigo", "")))
        self._fill_sustancia(self.v_codigo.get())
        tipo_entrada = self._tipos_entrada_by_id.get(rec.get("id_tipo_entrada"), {}).get("tipo_entrada", "")
        self.v_tipo_entrada.set(tipo_entrada or rec.get("tipo_entrada", ""))
        self._set_default_tipo_entrada()
        self._set_date_widget(self.w_fecha_entrada, rec.get("fecha_entrada", ""))
        self._set_date_widget(self.w_fecha_venc, rec.get("fecha_vencimiento", ""))
        self.v_lote.set(rec.get("lote", ""))
        self.v_catalogo.set(rec.get("catalogo", ""))
        self.v_cantidad.set(str(rec.get("cantidad", "")))
        self.v_presentacion.set(rec.get("presentacion", ""))
        self.v_total_neto.set(str(rec.get("total_contenido", "")))
        self.v_potencia.set(rec.get("potencia", ""))
        self.v_costo_unitario.set(str(rec.get("costo_unitario", "")))
        self.v_costo_total.set(str(rec.get("costo_total", "")))
        self.v_factura.set(rec.get("factura", ""))

        uni = self._unidades_by_id.get(rec.get("id_unidad"), {})
        self.v_unidad.set(uni.get("unidad", ""))

        ubic = next((u for u in self._ubicaciones_rows if u.get("id") == rec.get("id_ubicacion")), None)
        if ubic:
            self.v_ubicacion_tipo.set(str(ubic.get("ubicacion", "")).strip())
            self._rebuild_cajas_por_ubicacion(self.v_ubicacion_tipo.get())
            caja_val = str(ubic.get("no_caja", "")).strip()
            self.v_no_caja.set(caja_val if caja_val else "(SIN CAJA)")
        for txt, id_ in self._cond_values:
            if id_ == rec.get("id_condicion_alm"):
                self.v_condicion.set(txt)
                break
        for txt, id_ in self._color_values:
            if id_ == rec.get("id_color_refuerzo"):
                self.v_color_refuerzo.set(txt)
                break

        self.v_cert_anl.set(bool(rec.get("certificado_anl")))
        self.v_ficha_seg.set(bool(rec.get("ficha_seguridad")))
        self.v_factura_compra.set(bool(rec.get("factura_compra")))

        self.txt_obs.delete("1.0", "end")
        self.txt_obs.insert("1.0", rec.get("observaciones", ""))

    def _cancel_selected(self):
        id_entrada = self._selected_history_id()
        if id_entrada is None:
            messagebox.showwarning("Aviso", "Seleccione una entrada del historial.", parent=self)
            return
        if not messagebox.askyesno("Confirmar", "¿Anular la entrada seleccionada?", parent=self):
            return

        ent.anular(id_entrada, usuario=self.username)
        self._refresh_list()
        self._load_history_default()
