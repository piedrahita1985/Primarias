import tkinter as tk
from tkinter import messagebox, ttk

from config.config import COLORS
from logica import movimientos_common as common
from logica import salidas_mov_logica as sal
from UI._base_movimientos import MovimientosBase
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
    validate_required_fields,
)
from UI._searchable_treeview import SearchableTreeview
from UI._smart_combobox import SmartCodeCombobox


def open_window(master):
    SalidasWindow(master)


class SalidasWindow(MovimientosBase):
    def __init__(self, master):
        super().__init__(master, "Sistema de Gestion - Salidas")
        apply_default_window(self, min_width=1100, min_height=700)

        self._maestras = common.cargar_maestras()
        self._sustancias_by_codigo = common.map_sustancia_by_codigo(self._maestras["sustancias"])
        self._sustancias_by_id = common.map_by_id(self._maestras["sustancias"])
        self._sustancias_codigos = sorted(self._sustancias_by_codigo.keys(), key=lambda x: (len(x), x))
        self._sustancias_codigos_disponibles = []
        self._unidades_by_id = common.map_by_id(self._maestras["unidades"])
        self._tipos_salida_by_id = common.map_by_id(self._maestras["tipos_salida"])
        self._tipos_salida = [
            r.get("tipo_salida", "")
            for r in self._maestras["tipos_salida"]
            if r.get("tipo_salida")
        ]

        self._current_sustancia = None
        self._lotes = []
        self._editing_id = None

        self._vars()
        self._build_ui()
        self._set_default_tipo_salida()
        self._refresh_list()
        self._load_history_default()

    def _vars(self):
        self.v_codigo = tk.StringVar()
        self.v_tipo_salida = tk.StringVar()
        self.v_nombre = tk.StringVar()
        self.v_propiedad = tk.StringVar()
        self.v_codigo_sistema = tk.StringVar()
        self.v_lote = tk.StringVar()
        self.v_disponible = tk.StringVar(value="0")
        self.v_nuevo_stock = tk.StringVar(value="0")
        self.v_unidad = tk.StringVar()
        self.v_cantidad = tk.StringVar()
        self.v_actividad = tk.StringVar()
        self.h_codigo = tk.StringVar()
        self.h_lote = tk.StringVar()

        upper_text_var(self.v_actividad)
        self.v_cantidad.trace_add("write", lambda *_: self._update_nuevo_stock())

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self):
        draw_title(self, "Sistema de Gestion - Salidas")

        main_frame = tk.Frame(self, bg=COLORS["secondary"])
        main_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill="both", expand=True)

        tab_reg = tk.Frame(self.notebook, bg=COLORS["secondary"])
        tab_hist = tk.Frame(self.notebook, bg=COLORS["secondary"])
        self.notebook.add(tab_reg, text="  📋 Registro de Salida  ")
        self.notebook.add(tab_hist, text="  📖 Historial  ")

        self._build_registro_tab(tab_reg)
        self._build_historial_tab(tab_hist)

        bar = tk.Frame(self, bg=COLORS["secondary"])
        bar.pack(side="bottom", fill="x", padx=10, pady=(0, 10))
        self.lbl_status = tk.Label(
            bar,
            text="Listo para registrar salida.",
            bg=COLORS["secondary"],
            fg=COLORS["text_muted"],
            font=("Segoe UI", 9),
            anchor="w",
        )
        self.lbl_status.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._button(bar, "Salir", "#6C757D", self.destroy).pack(side="right")
        self._button(bar, "Guardar  [Ctrl+G]", COLORS["primary"], self._save).pack(side="right", padx=(0, 6))
        self._button(bar, "Nuevo", "#6C757D", self._clear_form).pack(side="left", padx=(0, 6))

    def _build_registro_tab(self, parent):
        canvas = tk.Canvas(parent, bg=COLORS["secondary"], highlightthickness=0)
        vsb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        form = tk.Frame(canvas, bg=COLORS["secondary"])
        form_window = canvas.create_window((0, 0), window=form, anchor="nw")

        def _on_form_config(_event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_config(event):
            canvas.itemconfig(form_window, width=event.width)

        form.bind("<Configure>", _on_form_config)
        canvas.bind("<Configure>", _on_canvas_config)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        self._build_form_fields(form)

    def _build_form_fields(self, parent):
        for c in range(5):
            parent.grid_columnconfigure(c, weight=1)

        tk.Label(parent, text="Tipo Salida", bg=COLORS["secondary"], fg=COLORS["text_dark"],
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", padx=8, pady=(10, 2))
        self.cb_tipo_salida = ttk.Combobox(
            parent, textvariable=self.v_tipo_salida, values=self._tipos_salida,
            state="readonly", font=("Segoe UI", 10))
        self.cb_tipo_salida.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))

        self.w_fecha = make_date_input(parent, 0, 1, "Fecha")

        tk.Label(parent, text="Codigo de Uso", bg=COLORS["secondary"], fg=COLORS["text_dark"],
                 font=("Segoe UI", 9, "bold")).grid(row=0, column=2, sticky="w", padx=8, pady=(10, 2))
        self.cb_codigo = SmartCodeCombobox(parent, self._sustancias_by_codigo, state="normal", font=("Segoe UI", 10))
        self.cb_codigo.grid(row=1, column=2, sticky="ew", padx=8, pady=(0, 8))
        self.cb_codigo.bind("<<SmartCodeSelected>>", self._on_codigo_selected)
        self.cb_codigo.bind("<FocusOut>", self._on_codigo_focusout)

        make_labeled_entry(parent, "Nombre", self.v_nombre, 0, 3, read_only=True)
        make_labeled_entry(parent, "Propiedad", self.v_propiedad, 0, 4, read_only=True)

        make_labeled_entry(parent, "Codigo Sistema", self.v_codigo_sistema, 2, 0, read_only=True)

        tk.Label(parent, text="Lote", bg=COLORS["secondary"], fg=COLORS["text_dark"],
                 font=("Segoe UI", 9, "bold")).grid(row=2, column=1, sticky="w", padx=8, pady=(6, 2))
        self.cb_lote = ttk.Combobox(parent, textvariable=self.v_lote, values=[],
                                    state="readonly", font=("Segoe UI", 10))
        self.cb_lote.grid(row=3, column=1, sticky="ew", padx=8, pady=(0, 8))
        self.cb_lote.bind("<<ComboboxSelected>>", self._on_lote_selected)

        make_labeled_entry(parent, "Disponible", self.v_disponible, 2, 2, read_only=True)
        make_labeled_entry(parent, "Unidad", self.v_unidad, 2, 3, read_only=True)
        self.e_nuevo_stock = make_labeled_entry(parent, "Nuevo stock", self.v_nuevo_stock, 2, 4, read_only=True)
        self._paint_nuevo_stock(None)

        e_cantidad = make_labeled_entry(parent, "Cantidad a retirar", self.v_cantidad, 4, 0)
        e_cantidad.bind("<KeyPress>", only_numeric)
        make_labeled_entry(parent, "Actividad", self.v_actividad, 4, 1)

        tk.Label(parent, text="Observacion", bg=COLORS["secondary"], fg=COLORS["text_dark"],
                 font=("Segoe UI", 9, "bold")).grid(row=6, column=0, columnspan=5, sticky="w",
                                                    padx=8, pady=(6, 2))
        self.txt_obs = tk.Text(
            parent, height=5, bg=COLORS["surface"], fg=COLORS["text_dark"],
            font=("Segoe UI", 10), relief="flat", bd=0,
            highlightthickness=1, highlightbackground=COLORS["border_soft"],
            highlightcolor=COLORS["primary"])
        self.txt_obs.grid(row=7, column=0, columnspan=5, sticky="nsew", padx=8, pady=(0, 12))
        self.txt_obs.bind("<KeyRelease>", self._on_obs_upper)

    def _build_historial_tab(self, parent):
        ftop = tk.Frame(parent, bg=COLORS["secondary"])
        ftop.pack(fill="x", padx=8, pady=(8, 4))

        _e_style = dict(bg=COLORS["surface"], fg=COLORS["text_dark"], font=("Segoe UI", 10),
                        relief="flat", bd=0, highlightthickness=1,
                        highlightbackground=COLORS["border_soft"], highlightcolor=COLORS["primary"])

        def _lbl(t):
            return tk.Label(ftop, text=t, bg=COLORS["secondary"], fg=COLORS["text_dark"],
                            font=("Segoe UI", 9, "bold"))

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
        self._button(ftop, "Actualizar  [F5]", "#BDBDBD", self._refresh_all).pack(side="right")

        tbl_frame = tk.Frame(parent, bg=COLORS["secondary"])
        tbl_frame.pack(fill="both", expand=True, padx=8)
        tbl_frame.grid_rowconfigure(0, weight=1)
        tbl_frame.grid_columnconfigure(0, weight=1)

        cols = ("id", "fecha", "codigo", "lote", "cantidad", "unidad", "actividad", "estado")
        self.h_tree = SearchableTreeview(
            tbl_frame, columns=cols,
            search_columns=["codigo", "lote", "actividad"],
            height=10,
        )
        self.h_tree.pack(fill="both", expand=True)
        for key, title, width in [
            ("id", "ID", 60),
            ("fecha", "Fecha", 110),
            ("codigo", "Codigo", 90),
            ("lote", "Lote", 120),
            ("cantidad", "Cantidad", 90),
            ("unidad", "Unidad", 80),
            ("actividad", "Actividad", 220),
            ("estado", "Estado", 90),
        ]:
            self.h_tree.heading(key, text=title)
            self.h_tree.column(key, width=width, anchor="center")
        attach_treeview_sorting(self.h_tree.tree)

        pag_frame = self._build_pagination_controls(parent)
        pag_frame.pack(fill="x", padx=8, pady=(4, 2))

        fbot = tk.Frame(parent, bg=COLORS["secondary"])
        fbot.pack(fill="x", padx=8, pady=(0, 8))
        self._button(fbot, "Editar seleccionado", COLORS["primary_dark"], self._edit_selected).pack(side="left", padx=(0, 6))
        self._button(fbot, "Anular seleccionado", COLORS["error"], self._cancel_selected).pack(side="left")

    def _button(self, parent, text, bg, cmd):
        return tk.Button(parent, text=text, bg=bg, fg="white",
                         font=("Segoe UI", 10, "bold"), relief="flat", bd=0,
                         padx=10, pady=6, cursor="hand2", command=cmd)

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------
    def _load_history_default(self):
        self._current_page = 1
        self._load_page()

    def _load_page(self):
        self.after(10, self._do_load_page)

    def _do_load_page(self):
        desde = get_date_value(self.h_w_desde) if hasattr(self, "h_w_desde") else ""
        hasta = get_date_value(self.h_w_hasta) if hasattr(self, "h_w_hasta") else ""
        codigo = self.h_codigo.get().strip() if hasattr(self, "h_codigo") else ""
        lote = self.h_lote.get().strip() if hasattr(self, "h_lote") else ""

        all_rows = sal.filtrar(
            fecha="",
            fecha_desde=desde,
            fecha_hasta=hasta,
            codigo=codigo,
            lote=lote,
            maestras=self._maestras,
        )
        self._total_records = len(all_rows)
        self._total_pages = max(1, -(-self._total_records // self._page_size))
        if self._current_page > self._total_pages:
            self._current_page = self._total_pages
        start = (self._current_page - 1) * self._page_size
        self._fill_history(all_rows[start:start + self._page_size])
        self._update_pagination_buttons()

    def _apply_filters(self):
        self._current_page = 1
        self._load_page()

    def _clear_filters(self):
        self._set_date_widget(self.h_w_desde, "")
        self._set_date_widget(self.h_w_hasta, "")
        self.h_codigo.set("")
        self.h_lote.set("")
        self._load_history_default()

    # ------------------------------------------------------------------
    # Save / Refresh
    # ------------------------------------------------------------------
    def _save(self):
        self._show_progress(True)
        self.after(10, self._do_save)

    def _do_save(self):
        try:
            if self._current_sustancia is None:
                self._show_status("Seleccione un codigo de uso valido.", is_error=True)
                messagebox.showwarning("Aviso", "Seleccione un codigo de uso valido.", parent=self)
                return

            lote_idx = self.cb_lote.current()
            if lote_idx < 0 or lote_idx >= len(self._lotes):
                self._show_status("Seleccione un lote valido.", is_error=True)
                messagebox.showwarning("Aviso", "Seleccione un lote valido.", parent=self)
                return

            try:
                cantidad = float((self.v_cantidad.get() or "0").replace(",", "."))
            except ValueError:
                self._show_status("Cantidad invalida.", is_error=True)
                messagebox.showwarning("Aviso", "Cantidad invalida.", parent=self)
                return

            if cantidad <= 0:
                self._show_status("La cantidad debe ser mayor a 0.", is_error=True)
                messagebox.showwarning("Aviso", "La cantidad debe ser mayor a 0.", parent=self)
                return

            lote_sel = self._lotes[lote_idx]
            disponible = self._available_for_selected_lote(lote_sel)

            if disponible <= 0:
                self._show_status("No hay stock disponible para el lote seleccionado.", is_error=True)
                messagebox.showwarning("Aviso", "No hay stock disponible.", parent=self)
                return

            if cantidad > disponible:
                self._show_status(f"Stock insuficiente. Disponible: {disponible}", is_error=True)
                messagebox.showwarning("Aviso", f"Stock insuficiente. Disponible: {disponible}", parent=self)
                return

            if disponible - cantidad < 0:
                self._show_status("La salida no puede dejar stock negativo.", is_error=True)
                messagebox.showwarning("Aviso", "La salida no puede dejar stock negativo.", parent=self)
                return

            tipo_salida_id = None
            for t in self._maestras["tipos_salida"]:
                if t.get("tipo_salida", "") == self.v_tipo_salida.get().strip():
                    tipo_salida_id = t.get("id")
                    break
            if tipo_salida_id is None:
                self._show_status("Seleccione un tipo de salida valido.", is_error=True)
                messagebox.showwarning("Aviso", "Seleccione un tipo de salida valido.", parent=self)
                return

            record = {
                "fecha_salida": get_date_value(self.w_fecha),
                "id_tipo_salida": tipo_salida_id,
                "id_sustancia": self._current_sustancia.get("id"),
                "id_entrada": lote_sel.get("id_entrada"),
                "id_unidad": lote_sel.get("id_unidad"),
                "cantidad": cantidad,
                "actividad": self.v_actividad.get().strip(),
                "observacion": self.txt_obs.get("1.0", "end-1c").strip(),
            }

            if self._editing_id is None:
                sal.agregar(record, usuario=self.username)
                msg = "Salida guardada correctamente."
            else:
                sal.actualizar(self._editing_id, record, usuario=self.username)
                msg = "Salida actualizada correctamente."

            self._show_status(msg, is_success=True)
            messagebox.showinfo("Exito", msg, parent=self)
            self._refresh_list()
            self._load_history_default()
            self._clear_form()
        finally:
            self._show_progress(False)

    def _refresh_all(self):
        self._maestras = common.cargar_maestras()
        self._sustancias_by_codigo = common.map_sustancia_by_codigo(self._maestras["sustancias"])
        self._sustancias_by_id = common.map_by_id(self._maestras["sustancias"])
        self._sustancias_codigos = sorted(self._sustancias_by_codigo.keys(), key=lambda x: (len(x), x))
        self._unidades_by_id = common.map_by_id(self._maestras["unidades"])
        self._tipos_salida_by_id = common.map_by_id(self._maestras["tipos_salida"])
        self._tipos_salida = [r.get("tipo_salida", "") for r in self._maestras["tipos_salida"] if r.get("tipo_salida")]
        self.cb_tipo_salida.configure(values=self._tipos_salida)
        self._refresh_list()
        self._load_history_default()
        self._show_status("Datos actualizados.", is_success=True)

    # ------------------------------------------------------------------
    # History table helpers
    # ------------------------------------------------------------------
    def _fill_history(self, rows):
        self.h_tree.clear()
        for r in rows:
            self.h_tree.insert("", "end", values=(
                r.get("id", ""),
                r.get("fecha_salida", ""),
                r.get("codigo", ""),
                r.get("lote", ""),
                r.get("cantidad", ""),
                r.get("unidad_nombre", ""),
                r.get("actividad", ""),
                r.get("estado", "ACTIVA"),
            ))

    def _selected_history_id(self):
        sel = self.h_tree.selection()
        if not sel:
            return None
        vals = self.h_tree.item(sel[0], "values")
        if not vals:
            return None
        return int(vals[0])

    def _edit_selected(self):
        id_salida = self._selected_history_id()
        if id_salida is None:
            messagebox.showwarning("Aviso", "Seleccione una salida del historial.", parent=self)
            return

        rows = sal.cargar()
        rec = next((r for r in rows if r.get("id") == id_salida), None)
        if rec is None:
            return
        if rec.get("estado") == "ANULADA":
            messagebox.showwarning("Aviso", "No se puede editar una salida anulada.", parent=self)
            return

        self._editing_id = id_salida
        sust = self._sustancias_by_id.get(rec.get("id_sustancia"), {})
        self.v_codigo.set(str(sust.get("codigo", "")))
        tipo_salida = self._tipos_salida_by_id.get(rec.get("id_tipo_salida"), {}).get("tipo_salida", "")
        self.v_tipo_salida.set(tipo_salida or rec.get("tipo_salida", ""))
        self._set_default_tipo_salida()
        self._set_date_widget(self.w_fecha, rec.get("fecha_salida", ""))
        self._fill_sustancia(self.v_codigo.get())

        if not any(l.get("id_entrada") == rec.get("id_entrada") for l in self._lotes):
            entrada = common.map_by_id(common.cargar_entradas()).get(rec.get("id_entrada"), {})
            self._lotes.append({
                "id_entrada": rec.get("id_entrada"),
                "lote": entrada.get("lote", ""),
                "catalogo": entrada.get("catalogo", ""),
                "disponible": 0,
                "id_unidad": rec.get("id_unidad"),
            })
            values = [str(l.get("lote", "")) for l in self._lotes]
            self.cb_lote.configure(values=values)

        for i, l in enumerate(self._lotes):
            if l.get("id_entrada") == rec.get("id_entrada"):
                self.cb_lote.current(i)
                self._on_lote_selected()
                break

        self.v_cantidad.set(str(rec.get("cantidad", "")))
        self.v_actividad.set(rec.get("actividad", ""))
        self.txt_obs.delete("1.0", "end")
        self.txt_obs.insert("1.0", rec.get("observacion", ""))
        self._update_nuevo_stock()
        self.notebook.select(0)

    def _cancel_selected(self):
        id_salida = self._selected_history_id()
        if id_salida is None:
            messagebox.showwarning("Aviso", "Seleccione una salida del historial.", parent=self)
            return
        if not messagebox.askyesno("Confirmar", "Anular la salida seleccionada?", parent=self):
            return
        sal.anular(id_salida, usuario=self.username)
        self._show_status("Salida anulada.", is_success=True)
        self._refresh_list()
        self._load_history_default()

    def _clear_form(self):
        self._editing_id = None
        self.cb_codigo.set("") if hasattr(self.cb_codigo, 'get_codigo') else None
        for v in [
            self.v_codigo, self.v_tipo_salida, self.v_nombre, self.v_propiedad,
            self.v_codigo_sistema, self.v_lote, self.v_disponible, self.v_nuevo_stock,
            self.v_unidad, self.v_cantidad, self.v_actividad,
        ]:
            v.set("")
        self._set_default_tipo_salida()
        self.txt_obs.delete("1.0", "end")
        self.cb_lote.configure(values=[])
        self._lotes = []
        self._current_sustancia = None
        self._rebuild_codigos_disponibles()
        self._show_status("Listo para registrar salida.")

    def _refresh_list(self):
        self._rebuild_codigos_disponibles()

    # ------------------------------------------------------------------
    # Form auto-complete helpers
    # ------------------------------------------------------------------
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

    def _on_obs_upper(self, _event=None):
        value = self.txt_obs.get("1.0", "end-1c")
        up = value.upper()
        if value != up:
            pos = self.txt_obs.index("insert")
            self.txt_obs.delete("1.0", "end")
            self.txt_obs.insert("1.0", up)
            self.txt_obs.mark_set("insert", pos)

    def _on_codigo_key(self, event=None):
        typed = self.cb_codigo.get_codigo().strip() if hasattr(self.cb_codigo, 'get_codigo') else self.v_codigo.get().strip()
        ordered = self._ordered_codes(typed)
        self.cb_codigo.configure(values=ordered)
        if not typed:
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
        codigo = self.cb_codigo.get_codigo().strip() if hasattr(self.cb_codigo, 'get_codigo') else self.v_codigo.get().strip()
        self._fill_sustancia(codigo)

    def _on_codigo_focusout(self, _event=None):
        codigo = self.cb_codigo.get_codigo().strip() if hasattr(self.cb_codigo, 'get_codigo') else self.v_codigo.get().strip()
        if codigo in self._sustancias_by_codigo:
            self._fill_sustancia(codigo)

    def _ordered_codes(self, typed):
        source = list(self._sustancias_codigos_disponibles or self._sustancias_codigos)
        txt = str(typed or "").strip()
        if not txt:
            return source
        return sorted(
            source,
            key=lambda code: (
                txt not in code,
                code.find(txt) if txt in code else 10**9,
                len(code),
                code,
            ),
        )

    def _rebuild_codigos_disponibles(self):
        self._sustancias_codigos_disponibles = sal.codigos_con_stock_disponible(self._maestras)
        self.cb_codigo.configure(values=self._sustancias_codigos_disponibles)

    def _fill_sustancia(self, codigo):
        s = self._sustancias_by_codigo.get(codigo)
        self._current_sustancia = s
        if s is None:
            self._clear_auto_fields()
            return
        self.v_nombre.set(s.get("nombre", ""))
        self.v_propiedad.set(s.get("propiedad", ""))
        self.v_codigo_sistema.set(s.get("codigo_sistema", ""))
        self._lotes = sal.lotes_disponibles_por_sustancia(s.get("id"))
        values = [str(l.get("lote", "")) for l in self._lotes]
        self.cb_lote.configure(values=values)
        self.v_lote.set("")
        self.v_disponible.set("0")
        self.v_nuevo_stock.set("0")
        self.v_unidad.set("")

    def _on_lote_selected(self, _event=None):
        idx = self.cb_lote.current()
        if idx < 0 or idx >= len(self._lotes):
            return
        l = self._lotes[idx]
        disponible = self._available_for_selected_lote(l)
        self.v_disponible.set(self._fmt_num(disponible))
        unidad = self._unidades_by_id.get(l.get("id_unidad"), {}).get("unidad", "")
        self.v_unidad.set(unidad)
        self._update_nuevo_stock()

    def _clear_auto_fields(self):
        self._current_sustancia = None
        self.v_nombre.set("")
        self.v_propiedad.set("")
        self.v_codigo_sistema.set("")
        self.cb_lote.configure(values=[])
        self.v_lote.set("")
        self.v_disponible.set("0")
        self.v_nuevo_stock.set("0")
        self.v_unidad.set("")

    def _set_default_tipo_salida(self):
        if self.v_tipo_salida.get().strip():
            return
        if self._tipos_salida:
            self.v_tipo_salida.set(self._tipos_salida[0])

    @staticmethod
    def _fmt_num(value):
        return f"{float(value):.4f}".rstrip("0").rstrip(".") if value else "0"

    def _available_for_selected_lote(self, lote):
        disponible = float(lote.get("disponible", 0))
        if self._editing_id is None:
            return disponible
        old = next((r for r in sal.cargar() if r.get("id") == self._editing_id), None)
        if old and old.get("id_entrada") == lote.get("id_entrada") and old.get("estado", "ACTIVA") == "ACTIVA":
            disponible += float(old.get("cantidad", 0))
        return disponible

    def _selected_lote(self):
        idx = self.cb_lote.current()
        if idx < 0 or idx >= len(self._lotes):
            return None
        return self._lotes[idx]

    def _update_nuevo_stock(self):
        lote = self._selected_lote()
        if lote is None:
            self.v_nuevo_stock.set("0")
            self._paint_nuevo_stock(0)
            return
        disponible = self._available_for_selected_lote(lote)
        try:
            cantidad = float((self.v_cantidad.get() or "0").replace(",", "."))
        except ValueError:
            self.v_nuevo_stock.set("")
            self._paint_nuevo_stock(None)
            return
        nuevo = disponible - cantidad
        self.v_nuevo_stock.set(self._fmt_num(nuevo))
        self._paint_nuevo_stock(nuevo)

    def _paint_nuevo_stock(self, value):
        if value is None:
            bg = COLORS["surface"]
            fg = COLORS["text_dark"]
        elif value < 0:
            bg = "#FFD6D6"
            fg = "#8B0000"
        elif value == 0:
            bg = "#FFF3CD"
            fg = "#7A5D00"
        else:
            bg = "#DFF7E2"
            fg = "#1E6B2A"
        self.e_nuevo_stock.configure(readonlybackground=bg, fg=fg)