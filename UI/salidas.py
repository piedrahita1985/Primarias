import tkinter as tk
from tkinter import messagebox, ttk

from config.config import COLORS
from logica import movimientos_common as common
from logica import salidas_mov_logica as sal
from UI._mov_utils import draw_title, get_date_value, make_date_input, make_labeled_entry, only_numeric, upper_text_var


def open_window(master):
    SalidasWindow(master)


class SalidasWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.username = getattr(master, "username", "SISTEMA")
        self.title("Sistema de Gestion - Salidas")
        self.configure(bg=COLORS["secondary"])
        self.geometry("1320x860")
        self.minsize(1100, 700)

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
        self.h_fecha = tk.StringVar()
        self.h_desde = tk.StringVar()
        self.h_hasta = tk.StringVar()
        self.h_codigo = tk.StringVar()
        self.h_lote = tk.StringVar()

        upper_text_var(self.v_actividad)
        self.v_cantidad.trace_add("write", lambda *_: self._update_nuevo_stock())

    def _build_ui(self):
        draw_title(self, "Sistema de Gestion - Salidas")

        wrap = tk.Frame(self, bg=COLORS["secondary"])
        wrap.pack(fill="both", expand=True, padx=10, pady=10)
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_rowconfigure(0, weight=1)

        right = tk.LabelFrame(
            wrap,
            text="  Registro de salida  ",
            bg=COLORS["secondary"],
            fg=COLORS["text_dark"],
            font=("Segoe UI", 9, "bold"),
            padx=8,
            pady=6,
        )
        right.grid(row=0, column=0, sticky="nsew")
        for c in range(5):
            right.grid_columnconfigure(c, weight=1)

        tk.Label(right, text="Tipo Salida", bg=COLORS["secondary"], fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", padx=8, pady=(6, 2))
        self.cb_tipo_salida = ttk.Combobox(right, textvariable=self.v_tipo_salida, values=self._tipos_salida, state="readonly", font=("Segoe UI", 10))
        self.cb_tipo_salida.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))

        self.w_fecha = make_date_input(right, 0, 1, "Fecha")

        tk.Label(right, text="Codigo de Uso", bg=COLORS["secondary"], fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold")).grid(row=0, column=2, sticky="w", padx=8, pady=(6, 2))
        self.cb_codigo = ttk.Combobox(right, textvariable=self.v_codigo, values=self._sustancias_codigos, state="normal", font=("Segoe UI", 10))
        self.cb_codigo.grid(row=1, column=2, sticky="ew", padx=8, pady=(0, 8))
        self.cb_codigo.bind("<KeyRelease>", self._on_codigo_key)
        self.cb_codigo.bind("<<ComboboxSelected>>", self._on_codigo_selected)
        self.cb_codigo.bind("<FocusOut>", self._on_codigo_focusout)

        make_labeled_entry(right, "Nombre", self.v_nombre, 0, 3, read_only=True)
        make_labeled_entry(right, "Propiedad", self.v_propiedad, 0, 4, read_only=True)

        make_labeled_entry(right, "Codigo Sistema", self.v_codigo_sistema, 2, 0, read_only=True)

        tk.Label(right, text="Lote", bg=COLORS["secondary"], fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold")).grid(row=2, column=1, sticky="w", padx=8, pady=(6, 2))
        self.cb_lote = ttk.Combobox(right, textvariable=self.v_lote, values=[], state="readonly", font=("Segoe UI", 10))
        self.cb_lote.grid(row=3, column=1, sticky="ew", padx=8, pady=(0, 8))
        self.cb_lote.bind("<<ComboboxSelected>>", self._on_lote_selected)

        make_labeled_entry(right, "Disponible", self.v_disponible, 2, 2, read_only=True)
        make_labeled_entry(right, "Unidad", self.v_unidad, 2, 3, read_only=True)
        self.e_nuevo_stock = make_labeled_entry(right, "Nuevo stock", self.v_nuevo_stock, 2, 4, read_only=True)
        self._paint_nuevo_stock(None)

        e_cantidad = make_labeled_entry(right, "Cantidad a retirar", self.v_cantidad, 4, 0)
        e_cantidad.bind("<KeyPress>", only_numeric)
        make_labeled_entry(right, "Actividad", self.v_actividad, 4, 1)

        tk.Label(right, text="Observacion", bg=COLORS["secondary"], fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold")).grid(row=6, column=0, columnspan=5, sticky="w", padx=8, pady=(6, 2))
        self.txt_obs = tk.Text(right, height=5, bg=COLORS["surface"], fg=COLORS["text_dark"], font=("Segoe UI", 10), relief="flat", bd=0, highlightthickness=1, highlightbackground=COLORS["border_soft"], highlightcolor=COLORS["primary"])
        self.txt_obs.grid(row=7, column=0, columnspan=5, sticky="nsew", padx=8, pady=(0, 8))
        self.txt_obs.bind("<KeyRelease>", self._on_obs_upper)

        self._build_history()

        bar = tk.Frame(self, bg=COLORS["secondary"])
        bar.pack(fill="x", padx=10, pady=(0, 10))
        self._button(bar, "Nuevo", "#6C757D", self._clear_form).pack(side="left", padx=(0, 6))
        self._button(bar, "Guardar", COLORS["primary"], self._save).pack(side="right", padx=6)
        self._button(bar, "Salir", "#6C757D", self.destroy).pack(side="right")

        self._rebuild_codigos_disponibles()

    def _build_history(self):
        hist = tk.LabelFrame(self, text="  Historial de Salidas  ", bg=COLORS["secondary"], fg=COLORS["primary_dark"], font=("Segoe UI", 10, "bold"))
        hist.pack(fill="both", expand=False, padx=10, pady=(0, 8))

        ftop = tk.Frame(hist, bg=COLORS["secondary"])
        ftop.pack(fill="x", padx=6, pady=6)

        tk.Label(ftop, text="Fecha:", bg=COLORS["secondary"], font=("Segoe UI", 10)).pack(side="left", padx=(0, 4))
        tk.Entry(ftop, textvariable=self.h_fecha, width=12).pack(side="left", padx=(0, 10))
        tk.Label(ftop, text="Desde:", bg=COLORS["secondary"], font=("Segoe UI", 10)).pack(side="left", padx=(0, 4))
        tk.Entry(ftop, textvariable=self.h_desde, width=12).pack(side="left", padx=(0, 10))
        tk.Label(ftop, text="Hasta:", bg=COLORS["secondary"], font=("Segoe UI", 10)).pack(side="left", padx=(0, 4))
        tk.Entry(ftop, textvariable=self.h_hasta, width=12).pack(side="left", padx=(0, 10))
        tk.Label(ftop, text="Codigo:", bg=COLORS["secondary"], font=("Segoe UI", 10)).pack(side="left", padx=(0, 4))
        tk.Entry(ftop, textvariable=self.h_codigo, width=12).pack(side="left", padx=(0, 10))
        tk.Label(ftop, text="Lote:", bg=COLORS["secondary"], font=("Segoe UI", 10)).pack(side="left", padx=(0, 4))
        tk.Entry(ftop, textvariable=self.h_lote, width=12).pack(side="left", padx=(0, 10))
        self._button(ftop, "Filtrar", COLORS["primary"], self._apply_filters).pack(side="left", padx=(0, 6))
        self._button(ftop, "Borrar filtros", "#B0B0B0", self._clear_filters).pack(side="left")

        cols = ("id", "fecha", "codigo", "lote", "cantidad", "unidad", "actividad", "estado")
        self.h_tree = ttk.Treeview(hist, columns=cols, show="headings", height=8)
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
        self.h_tree.pack(fill="both", expand=True, padx=6)

        ysb = ttk.Scrollbar(hist, orient="vertical", command=self.h_tree.yview)
        self.h_tree.configure(yscrollcommand=ysb.set)
        ysb.place(relx=0.996, rely=0.22, relheight=0.58, anchor="ne")

        fbot = tk.Frame(hist, bg=COLORS["secondary"])
        fbot.pack(fill="x", padx=6, pady=6)
        self._button(fbot, "Editar seleccionado", COLORS["primary_dark"], self._edit_selected).pack(side="left", padx=(0, 6))
        self._button(fbot, "Anular seleccionado", COLORS["error"], self._cancel_selected).pack(side="left")
        self._button(fbot, "Actualizar", "#BDBDBD", self._load_history_default).pack(side="right")

    def _button(self, parent, text, bg, cmd):
        return tk.Button(parent, text=text, bg=bg, fg="white", font=("Segoe UI", 10, "bold"), relief="flat", bd=0, padx=10, pady=6, cursor="hand2", command=cmd)

    def _set_date_widget(self, widget, value):
        if not value:
            return
        if hasattr(widget, "set_date"):
            try:
                widget.set_date(value)
                return
            except Exception:
                pass
        var = getattr(widget, "_fallback_var", None)
        if var is not None:
            var.set(value)

    def _on_obs_upper(self, _event=None):
        value = self.txt_obs.get("1.0", "end-1c")
        up = value.upper()
        if value != up:
            pos = self.txt_obs.index("insert")
            self.txt_obs.delete("1.0", "end")
            self.txt_obs.insert("1.0", up)
            self.txt_obs.mark_set("insert", pos)

    def _on_codigo_key(self, event=None):
        typed = self.v_codigo.get().strip()
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
        self._fill_sustancia(self.v_codigo.get().strip())

    def _on_codigo_focusout(self, _event=None):
        codigo = self.v_codigo.get().strip()
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

    def _save(self):
        if self._current_sustancia is None:
            messagebox.showwarning("Aviso", "Seleccione un codigo de uso valido.", parent=self)
            return

        lote_idx = self.cb_lote.current()
        if lote_idx < 0 or lote_idx >= len(self._lotes):
            messagebox.showwarning("Aviso", "Seleccione un lote valido.", parent=self)
            return

        try:
            cantidad = float((self.v_cantidad.get() or "0").replace(",", "."))
        except ValueError:
            messagebox.showwarning("Aviso", "Cantidad invalida.", parent=self)
            return

        if cantidad <= 0:
            messagebox.showwarning("Aviso", "La cantidad debe ser mayor a 0.", parent=self)
            return

        lote_sel = self._lotes[lote_idx]
        disponible = self._available_for_selected_lote(lote_sel)

        if disponible <= 0:
            messagebox.showwarning("Aviso", "No hay stock disponible para el lote seleccionado.", parent=self)
            return

        if cantidad > disponible:
            messagebox.showwarning("Aviso", f"Stock insuficiente. Disponible: {disponible}", parent=self)
            return

        nuevo_stock = disponible - cantidad
        if nuevo_stock < 0:
            messagebox.showwarning("Aviso", "La salida no puede dejar stock negativo.", parent=self)
            return

        tipo_salida_id = None
        for t in self._maestras["tipos_salida"]:
            if t.get("tipo_salida", "") == self.v_tipo_salida.get().strip():
                tipo_salida_id = t.get("id")
                break
        if tipo_salida_id is None:
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
            messagebox.showinfo("Exito", "Salida guardada correctamente.", parent=self)
        else:
            sal.actualizar(self._editing_id, record, usuario=self.username)
            messagebox.showinfo("Exito", "Salida actualizada correctamente.", parent=self)

        self._refresh_list()
        self._load_history_default()
        self._clear_form()

    def _clear_form(self):
        self._editing_id = None
        for v in [
            self.v_codigo,
            self.v_tipo_salida,
            self.v_nombre,
            self.v_propiedad,
            self.v_codigo_sistema,
            self.v_lote,
            self.v_disponible,
            self.v_nuevo_stock,
            self.v_unidad,
            self.v_cantidad,
            self.v_actividad,
        ]:
            v.set("")
        self._set_default_tipo_salida()
        self.txt_obs.delete("1.0", "end")
        self.cb_lote.configure(values=[])
        self._lotes = []
        self._current_sustancia = None
        self._rebuild_codigos_disponibles()

    def _refresh_list(self):
        self._rebuild_codigos_disponibles()

    def _load_history_default(self):
        rows = sal.ultimas_15(self._maestras)
        self._fill_history(rows)

    def _apply_filters(self):
        rows = sal.filtrar(
            fecha=self.h_fecha.get().strip(),
            fecha_desde=self.h_desde.get().strip(),
            fecha_hasta=self.h_hasta.get().strip(),
            codigo=self.h_codigo.get().strip(),
            lote=self.h_lote.get().strip(),
            maestras=self._maestras,
        )
        self._fill_history(rows)

    def _clear_filters(self):
        self.h_fecha.set("")
        self.h_desde.set("")
        self.h_hasta.set("")
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
                    r.get("fecha_salida", ""),
                    r.get("codigo", ""),
                    r.get("lote", ""),
                    r.get("cantidad", ""),
                    r.get("unidad_nombre", ""),
                    r.get("actividad", ""),
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

    def _cancel_selected(self):
        id_salida = self._selected_history_id()
        if id_salida is None:
            messagebox.showwarning("Aviso", "Seleccione una salida del historial.", parent=self)
            return
        if not messagebox.askyesno("Confirmar", "¿Anular la salida seleccionada?", parent=self):
            return

        sal.anular(id_salida, usuario=self.username)
        self._refresh_list()
        self._load_history_default()
