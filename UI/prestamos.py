import os
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from PIL import Image, ImageTk

from config.config import COLORS
from logica import movimientos_common as common
from logica import prestamos_logica as prest
from UI._mov_utils import attach_treeview_sorting, apply_default_window, draw_title, get_date_value, make_date_widget
from UI._searchable_treeview import SearchableTreeview


def open_window(master):
    PrestamosWindow(master)


class PrestamosWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Sistema de Gestion - Prestamos")
        self.configure(bg=COLORS["secondary"])
        apply_default_window(self, min_width=1120, min_height=720)

        self._maestras = common.cargar_maestras()
        self._sustancias_by_codigo = common.map_sustancia_by_codigo(self._maestras["sustancias"])
        self._sustancias_codigos = sorted(self._sustancias_by_codigo.keys(), key=lambda x: (len(x), x))
        self._users = prest.usuarios_habilitados()
        self._users_by_id = common.map_by_id(self._users)

        self._user = self._resolve_current_user(master)
        self._current_sustancia = None
        self._lotes = []
        self._destino_users = []
        self._firma_img = None

        self._emit_all_rows = []
        self._emit_page = 1
        self._emit_page_size = 15
        self._emit_total = 0

        self._vars()
        self._build_ui()
        self._load_signature()
        self._refresh_all()

    def _resolve_current_user(self, master):
        user = getattr(master, "user_record", None)
        if isinstance(user, dict) and user.get("id"):
            return user

        username = str(getattr(master, "username", "")).strip()
        if not username:
            return {}

        for u in self._users:
            if u.get("usuario") == username or u.get("nombre") == username:
                return u
        return {}

    def _vars(self):
        self.v_codigo = tk.StringVar()
        self.v_nombre = tk.StringVar()
        self.v_lote = tk.StringVar()
        self.v_disponible = tk.StringVar(value="0")
        self.v_unidad = tk.StringVar()
        self.v_cantidad = tk.StringVar()
        self.v_destino = tk.StringVar()
        self.v_mes_historial = tk.StringVar()
        self.v_hist_codigo = tk.StringVar()
        self.v_hist_lote = tk.StringVar()
        self.v_hist_destino = tk.StringVar()
        self.v_hist_estado = tk.StringVar()

    def _build_ui(self):
        draw_title(self, "Sistema de Gestion - Prestamos")

        wrap = tk.Frame(self, bg=COLORS["secondary"])
        wrap.pack(fill="both", expand=True, padx=10, pady=10)
        wrap.grid_rowconfigure(1, weight=1)
        wrap.grid_columnconfigure(0, weight=1)

        self._build_registro(wrap)
        self._build_emitidos(wrap)

        bottom = tk.Frame(self, bg=COLORS["secondary"])
        bottom.pack(side="bottom", fill="x", padx=10, pady=(0, 10))
        self._button(bottom, "Salir", "#6C757D", self.destroy).pack(side="right")

    def _build_registro(self, parent):
        sec = tk.LabelFrame(
            parent,
            text="  Registrar préstamo  ",
            bg=COLORS["secondary"],
            fg=COLORS["text_dark"],
            font=("Segoe UI", 10, "bold"),
            padx=8,
            pady=8,
        )
        sec.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        for c in range(4):
            sec.grid_columnconfigure(c, weight=1)

        tk.Label(sec, text="Código", bg=COLORS["secondary"], fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold")).grid(row=0, column=0, sticky="w", padx=8, pady=(6, 2))
        self.cb_codigo = ttk.Combobox(sec, textvariable=self.v_codigo, state="normal", font=("Segoe UI", 10))
        self.cb_codigo.grid(row=1, column=0, sticky="ew", padx=8, pady=(0, 8))
        self.cb_codigo.bind("<KeyRelease>", self._on_codigo_key)
        self.cb_codigo.bind("<<ComboboxSelected>>", self._on_codigo_selected)
        self.cb_codigo.bind("<FocusOut>", self._on_codigo_focusout)

        self._entry_ro(sec, "Nombre", self.v_nombre, 0, 1)

        tk.Label(sec, text="Lote", bg=COLORS["secondary"], fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold")).grid(row=0, column=2, sticky="w", padx=8, pady=(6, 2))
        self.cb_lote = ttk.Combobox(sec, textvariable=self.v_lote, state="readonly", font=("Segoe UI", 10))
        self.cb_lote.grid(row=1, column=2, sticky="ew", padx=8, pady=(0, 8))
        self.cb_lote.bind("<<ComboboxSelected>>", self._on_lote_selected)

        self._entry_ro(sec, "Disponible", self.v_disponible, 0, 3)

        self._entry_ro(sec, "Unidad", self.v_unidad, 2, 0)
        self._entry(sec, "Cantidad a prestar", self.v_cantidad, 2, 1)

        tk.Label(sec, text="Usuario destino", bg=COLORS["secondary"], fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold")).grid(row=2, column=2, sticky="w", padx=8, pady=(6, 2))
        self.cb_destino = ttk.Combobox(sec, textvariable=self.v_destino, state="readonly", font=("Segoe UI", 10))
        self.cb_destino.grid(row=3, column=2, sticky="ew", padx=8, pady=(0, 8))

        tk.Label(sec, text="Fecha limite", bg=COLORS["secondary"], fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold")).grid(row=2, column=3, sticky="w", padx=8, pady=(6, 2))
        self.w_fecha_limite = make_date_widget(sec)
        self.w_fecha_limite.grid(row=3, column=3, sticky="ew", padx=8, pady=(0, 8))

        tk.Label(sec, text="Observación", bg=COLORS["secondary"], fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold")).grid(row=4, column=0, columnspan=4, sticky="w", padx=8, pady=(4, 2))
        self.txt_obs = tk.Text(sec, height=3, bg=COLORS["surface"], fg=COLORS["text_dark"], font=("Segoe UI", 10), relief="flat", bd=0, highlightthickness=1, highlightbackground=COLORS["border_soft"], highlightcolor=COLORS["primary"])
        self.txt_obs.grid(row=5, column=0, columnspan=4, sticky="ew", padx=8, pady=(0, 8))

        firma_card = tk.Frame(sec, bg=COLORS["surface"], highlightthickness=1, highlightbackground=COLORS["border_soft"])
        firma_card.grid(row=6, column=0, columnspan=4, sticky="ew", padx=8, pady=(2, 8))
        tk.Label(firma_card, text="Firma del usuario prestador", bg=COLORS["surface"], fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=8, pady=(8, 4))
        self.lbl_firma = tk.Label(firma_card, bg=COLORS["surface"], fg=COLORS["text_muted"], font=("Segoe UI", 9, "italic"), text="Sin firma registrada")
        self.lbl_firma.pack(fill="x", padx=8, pady=(0, 8))

        bar = tk.Frame(sec, bg=COLORS["secondary"])
        bar.grid(row=7, column=0, columnspan=4, sticky="ew", padx=8, pady=(0, 4))
        self._button(bar, "Nuevo", "#6C757D", self._clear_form).pack(side="left")
        self._button(bar, "Registrar préstamo", COLORS["primary"], self._crear_prestamo).pack(side="right")

    def _build_pendientes(self, parent):
        sec = tk.LabelFrame(
            parent,
            text="  Préstamos pendientes para mí  ",
            bg=COLORS["secondary"],
            fg=COLORS["text_dark"],
            font=("Segoe UI", 10, "bold"),
            padx=8,
            pady=8,
        )
        sec.grid(row=1, column=0, sticky="nsew", padx=(0, 5))
        sec.grid_rowconfigure(0, weight=1)
        sec.grid_columnconfigure(0, weight=1)

        cols = ("id", "fecha", "codigo", "nombre", "lote", "cantidad", "unidad", "prestador")
        self.tree_pend = ttk.Treeview(sec, columns=cols, show="headings", height=11)
        self.tree_pend.grid(row=0, column=0, sticky="nsew")
        for key, title, width in [
            ("id", "ID", 55),
            ("fecha", "Fecha", 110),
            ("codigo", "Código", 70),
            ("nombre", "Nombre", 190),
            ("lote", "Lote", 100),
            ("cantidad", "Cantidad", 80),
            ("unidad", "Unidad", 90),
            ("prestador", "Prestador", 150),
        ]:
            self.tree_pend.heading(key, text=title)
            self.tree_pend.column(key, width=width, anchor="center")

        ysb = ttk.Scrollbar(sec, orient="vertical", command=self.tree_pend.yview)
        self.tree_pend.configure(yscrollcommand=ysb.set)
        ysb.grid(row=0, column=1, sticky="ns")

        bar = tk.Frame(sec, bg=COLORS["secondary"])
        bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self._button(bar, "Aceptar", COLORS["success"], lambda: self._responder(True)).pack(side="left", padx=(0, 6))
        self._button(bar, "Rechazar", COLORS["error"], lambda: self._responder(False)).pack(side="left")
        self._button(bar, "Actualizar", "#6C757D", self._refresh_all).pack(side="right")

    def _build_emitidos(self, parent):
        sec = tk.LabelFrame(
            parent,
            text="  Historial de préstamos emitidos  ",
            bg=COLORS["secondary"],
            fg=COLORS["text_dark"],
            font=("Segoe UI", 10, "bold"),
            padx=8,
            pady=8,
        )
        sec.grid(row=1, column=0, sticky="nsew")
        sec.grid_rowconfigure(1, weight=1)
        sec.grid_columnconfigure(0, weight=1)

        top = tk.Frame(sec, bg=COLORS["secondary"])
        top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))

        _e_style = dict(font=("Segoe UI", 10), bg=COLORS["surface"], fg=COLORS["text_dark"],
                        relief="flat", bd=0, highlightthickness=1,
                        highlightbackground=COLORS["border_soft"], highlightcolor=COLORS["primary"])
        def _lbl(t):
            return tk.Label(top, text=t, bg=COLORS["secondary"], fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold"))

        _lbl("Desde:").pack(side="left", padx=(0, 3))
        self.w_hist_desde = make_date_widget(top)
        self.w_hist_desde.pack(side="left", padx=(0, 10))
        _lbl("Hasta:").pack(side="left", padx=(0, 3))
        self.w_hist_hasta = make_date_widget(top)
        self.w_hist_hasta.pack(side="left", padx=(0, 10))
        _lbl("Código:").pack(side="left", padx=(0, 3))
        tk.Entry(top, textvariable=self.v_hist_codigo, width=8, **_e_style).pack(side="left", padx=(0, 10))
        _lbl("Lote:").pack(side="left", padx=(0, 3))
        tk.Entry(top, textvariable=self.v_hist_lote, width=8, **_e_style).pack(side="left", padx=(0, 10))
        _lbl("Destino:").pack(side="left", padx=(0, 3))
        tk.Entry(top, textvariable=self.v_hist_destino, width=10, **_e_style).pack(side="left", padx=(0, 10))
        _lbl("Estado:").pack(side="left", padx=(0, 3))
        tk.Entry(top, textvariable=self.v_hist_estado, width=8, **_e_style).pack(side="left", padx=(0, 10))
        _lbl("Mes:").pack(side="left", padx=(0, 3))
        self.cb_mes_historial = ttk.Combobox(top, textvariable=self.v_mes_historial, values=[], state="readonly", width=9, font=("Segoe UI", 10))
        self.cb_mes_historial.pack(side="left", padx=(0, 6))
        self._button(top, "Filtrar", COLORS["primary_dark"], self._refresh_emitidos).pack(side="left", padx=(0, 6))
        self._button(top, "Limpiar", "#6C757D", self._clear_emitidos_filters).pack(side="left")

        cols = ("id", "fecha", "codigo", "nombre", "lote", "cantidad", "destino", "estado")
        self.tree_emit = SearchableTreeview(
            sec, columns=cols,
            search_columns=["codigo", "nombre", "lote", "destino"],
            height=11,
        )
        self.tree_emit.grid(row=1, column=0, sticky="nsew")
        for key, title, width in [
            ("id", "ID", 55),
            ("fecha", "Fecha", 110),
            ("codigo", "Código", 70),
            ("nombre", "Nombre", 190),
            ("lote", "Lote", 100),
            ("cantidad", "Cantidad", 80),
            ("destino", "Destino", 150),
            ("estado", "Estado", 100),
        ]:
            self.tree_emit.heading(key, text=title)
            self.tree_emit.column(key, width=width, anchor="center")
        attach_treeview_sorting(self.tree_emit.tree)

        # Pagination controls
        pag_frame = tk.Frame(sec, bg=COLORS["secondary"])
        pag_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        btn_style = dict(bg=COLORS["primary"], fg="white", font=("Segoe UI", 9, "bold"),
                 relief="flat", bd=0, padx=8, pady=3, cursor="hand2")
        self.btn_emit_prev = tk.Button(pag_frame, text="< Anterior",
                           command=self._emit_prev_page, **btn_style)
        self.btn_emit_prev.pack(side="left", padx=2)
        self.lbl_emit_page = tk.Label(pag_frame, text="Pagina 1 de 1",
                          bg=COLORS["secondary"], fg=COLORS["text_dark"], font=("Segoe UI", 9))
        self.lbl_emit_page.pack(side="left", padx=10)
        self.btn_emit_next = tk.Button(pag_frame, text="Siguiente >",
                           command=self._emit_next_page, **btn_style)
        self.btn_emit_next.pack(side="left", padx=2)
        tk.Label(pag_frame, text="Mostrar:", bg=COLORS["secondary"], fg=COLORS["text_dark"],
             font=("Segoe UI", 9)).pack(side="left", padx=(15, 4))
        self.combo_emit_page_size = ttk.Combobox(pag_frame, values=[15, 25, 50, 100],
                              state="readonly", width=6, font=("Segoe UI", 9))
        self.combo_emit_page_size.set("15")
        self.combo_emit_page_size.bind("<<ComboboxSelected>>", self._emit_on_page_size_change)
        self.combo_emit_page_size.pack(side="left", padx=2)
        self.lbl_emit_total = tk.Label(pag_frame, text="", bg=COLORS["secondary"],
                           fg=COLORS["text_muted"], font=("Segoe UI", 9, "italic"))
        self.lbl_emit_total.pack(side="left", padx=(12, 0))

    def _entry(self, parent, label, var, row, col):
        tk.Label(parent, text=label, bg=COLORS["secondary"], fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold")).grid(row=row, column=col, sticky="w", padx=8, pady=(6, 2))
        tk.Entry(parent, textvariable=var, font=("Segoe UI", 10), bg=COLORS["surface"], fg=COLORS["text_dark"], relief="flat", bd=0, highlightthickness=1, highlightbackground=COLORS["border_soft"], highlightcolor=COLORS["primary"]).grid(row=row + 1, column=col, sticky="ew", padx=8, pady=(0, 8))

    def _entry_ro(self, parent, label, var, row, col):
        tk.Label(parent, text=label, bg=COLORS["secondary"], fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold")).grid(row=row, column=col, sticky="w", padx=8, pady=(6, 2))
        tk.Entry(parent, textvariable=var, state="readonly", readonlybackground=COLORS["surface"], fg=COLORS["text_dark"], font=("Segoe UI", 10), relief="flat", bd=0, highlightthickness=1, highlightbackground=COLORS["border_soft"], highlightcolor=COLORS["primary"]).grid(row=row + 1, column=col, sticky="ew", padx=8, pady=(0, 8))

    def _button(self, parent, text, bg, cmd):
        return tk.Button(parent, text=text, command=cmd, bg=bg, fg="white", font=("Segoe UI", 10, "bold"), relief="flat", bd=0, cursor="hand2", padx=12, pady=6)

    def _clear_date_widget(self, widget):
        try:
            widget.delete(0, "end")
            return
        except Exception:
            pass
        var = getattr(widget, "_fallback_var", None)
        if var is not None:
            var.set("")

    def _load_signature(self):
        firma_path = self._user.get("permisos", {}).get("firma_path", "") if isinstance(self._user.get("permisos", {}), dict) else ""
        if not firma_path or not os.path.isfile(firma_path):
            self.lbl_firma.configure(text="Sin firma registrada", image="")
            self._firma_img = None
            return

        try:
            img = Image.open(firma_path)
            img.thumbnail((420, 120), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self._firma_img = photo
            self.lbl_firma.configure(image=photo, text="")
        except Exception:
            self.lbl_firma.configure(text="Error cargando firma", image="")
            self._firma_img = None

    def _refresh_all(self):
        self._refresh_codigos()
        self._refresh_destinos()
        self._refresh_meses_historial()
        self._refresh_emitidos()

    def _refresh_meses_historial(self):
        my_id = self._user.get("id")
        if not my_id:
            self.cb_mes_historial.configure(values=[])
            self.v_mes_historial.set("")
            return
        meses = prest.meses_prestamos_emitidos(my_id)
        self.cb_mes_historial.configure(values=meses)
        if self.v_mes_historial.get() and self.v_mes_historial.get() not in meses:
            self.v_mes_historial.set("")

    def _apply_month_filter(self):
        self._refresh_emitidos()

    def _clear_month_filter(self):
        self.v_mes_historial.set("")
        self._refresh_emitidos()

    def _clear_emitidos_filters(self):
        self.v_mes_historial.set("")
        self._clear_date_widget(self.w_hist_desde)
        self._clear_date_widget(self.w_hist_hasta)
        self.v_hist_codigo.set("")
        self.v_hist_lote.set("")
        self.v_hist_destino.set("")
        self.v_hist_estado.set("")
        self._refresh_emitidos()

    def _refresh_codigos(self):
        # Mostrar maestras completas en el combo para permitir navegación y autocompletado.
        self.cb_codigo.configure(values=self._sustancias_codigos)
        codigo_actual = self.v_codigo.get().strip()
        if codigo_actual and codigo_actual in self._sustancias_by_codigo:
            self._on_codigo_selected()
        elif codigo_actual:
            self.v_codigo.set("")
            self._clear_stock_fields()

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

    def _on_codigo_key(self, event=None):
        typed = self.v_codigo.get().strip()
        ordered = self._ordered_codes(typed)
        self.cb_codigo.configure(values=ordered)

        if not typed:
            self._clear_stock_fields()
            return

        if not any(typed in c for c in self._sustancias_codigos):
            self.v_codigo.set("")
            self._clear_stock_fields()
            return

        match = next((c for c in ordered if typed in c), None)
        if match is None:
            return

        if event and event.keysym not in {"BackSpace", "Left", "Right", "Up", "Down"}:
            self.v_codigo.set(match)
            self.cb_codigo.icursor(len(typed))
            self.cb_codigo.selection_range(len(typed), len(match))

        if typed == match:
            self._on_codigo_selected()

    def _on_codigo_focusout(self, _event=None):
        codigo = self.v_codigo.get().strip()
        if codigo in self._sustancias_by_codigo:
            self._on_codigo_selected()
            return
        if codigo:
            self.v_codigo.set("")
        self._clear_stock_fields()

    def _refresh_destinos(self):
        my_id = self._user.get("id")
        self._destino_users = [
            u for u in self._users
            if u.get("id") != my_id
            and bool(u.get("permisos", {}).get("prestamos", False))
        ]
        nombres = [u.get("usuario") or u.get("nombre", "") for u in self._destino_users]
        self.cb_destino.configure(values=nombres)
        if self.v_destino.get() not in nombres:
            self.v_destino.set("")

    def _on_codigo_selected(self, _event=None):
        codigo = self.v_codigo.get().strip()
        sust = self._sustancias_by_codigo.get(codigo)
        self._current_sustancia = sust
        if sust is None:
            self._clear_stock_fields()
            return

        self.v_nombre.set(sust.get("nombre", ""))
        self._lotes = prest.lotes_disponibles(sust.get("id"))
        labels = [f"{l.get('lote', '')}  (Disp: {l.get('disponible', 0)})" for l in self._lotes]
        self.cb_lote.configure(values=labels)
        self.v_lote.set("")
        self.v_disponible.set("0")
        self.v_unidad.set("")

    def _on_lote_selected(self, _event=None):
        idx = self.cb_lote.current()
        if idx < 0 or idx >= len(self._lotes):
            self.v_disponible.set("0")
            self.v_unidad.set("")
            return

        lote = self._lotes[idx]
        self.v_disponible.set(str(lote.get("disponible", 0)))
        unidad = common.map_by_id(self._maestras["unidades"]).get(lote.get("id_unidad"), {}).get("unidad", "")
        self.v_unidad.set(unidad)

    def _clear_stock_fields(self):
        self._current_sustancia = None
        self._lotes = []
        self.v_nombre.set("")
        self.cb_lote.configure(values=[])
        self.v_lote.set("")
        self.v_disponible.set("0")
        self.v_unidad.set("")

    def _selected_destino(self):
        name = self.v_destino.get().strip()
        return next((u for u in self._destino_users if (u.get("usuario") or u.get("nombre", "")) == name), None)

    def _ask_firma_password_current_user(self):
        firma_pass = str(self._user.get("permisos", {}).get("firma_password", "") or "").strip()
        if not firma_pass:
            messagebox.showwarning("Firma", "El usuario no tiene contraseña de firma configurada.", parent=self)
            return False

        ingresada = simpledialog.askstring(
            "Validar firma",
            "Ingrese su contraseña de firma:",
            show="*",
            parent=self,
        )
        if ingresada is None:
            return False
        if str(ingresada).strip() != firma_pass:
            messagebox.showerror("Firma", "Contraseña de firma incorrecta.", parent=self)
            return False
        return True

    def _crear_prestamo(self):
        if not self._user.get("id"):
            messagebox.showerror("Error", "No se pudo identificar el usuario autenticado.", parent=self)
            return

        if self._firma_img is None:
            messagebox.showwarning("Aviso", "El usuario prestador no tiene firma registrada.", parent=self)
            return

        if not self._ask_firma_password_current_user():
            return

        if self._current_sustancia is None:
            messagebox.showwarning("Aviso", "Seleccione un código válido.", parent=self)
            return

        lote_idx = self.cb_lote.current()
        if lote_idx < 0 or lote_idx >= len(self._lotes):
            messagebox.showwarning("Aviso", "Seleccione un lote válido.", parent=self)
            return

        destino = self._selected_destino()
        if destino is None:
            messagebox.showwarning("Aviso", "Seleccione el usuario destino del préstamo.", parent=self)
            return

        try:
            cantidad = float((self.v_cantidad.get() or "0").replace(",", "."))
        except ValueError:
            messagebox.showwarning("Aviso", "Cantidad inválida.", parent=self)
            return

        if cantidad <= 0:
            messagebox.showwarning("Aviso", "La cantidad debe ser mayor a cero.", parent=self)
            return

        lote = self._lotes[lote_idx]
        disponible = common.to_float(lote.get("disponible"))
        if cantidad > disponible:
            messagebox.showwarning("Aviso", f"Stock insuficiente. Disponible: {disponible}", parent=self)
            return

        datos = {
            "id_sustancia": self._current_sustancia.get("id"),
            "id_entrada": lote.get("id_entrada"),
            "id_unidad": lote.get("id_unidad"),
            "cantidad": cantidad,
            "id_usuario_presta": self._user.get("id"),
            "id_usuario_destino": destino.get("id"),
            "firma_presta_path": self._user.get("permisos", {}).get("firma_path", ""),
            "fecha_limite": get_date_value(self.w_fecha_limite),
            "observacion": self.txt_obs.get("1.0", "end-1c").strip(),
        }

        prest.crear_prestamo(datos, usuario_presta=self._user.get("usuario") or self._user.get("nombre", "SISTEMA"))
        messagebox.showinfo("Éxito", "Préstamo registrado correctamente.", parent=self)
        self._clear_form()
        self._refresh_all()

    def _clear_form(self):
        self.v_codigo.set("")
        self.v_nombre.set("")
        self.v_lote.set("")
        self.v_disponible.set("0")
        self.v_unidad.set("")
        self.v_cantidad.set("")
        self.v_destino.set("")
        self.txt_obs.delete("1.0", "end")
        self._clear_date_widget(self.w_fecha_limite)
        self._current_sustancia = None
        self._lotes = []
        self.cb_lote.configure(values=[])

    def _refresh_pendientes(self):
        self.tree_pend.delete(*self.tree_pend.get_children())
        my_id = self._user.get("id")
        if not my_id:
            return

        rows = prest.prestamos_pendientes_para_usuario(my_id, self._maestras)
        for r in rows:
            self.tree_pend.insert(
                "",
                "end",
                values=(
                    r.get("id"),
                    r.get("fecha_prestamo", ""),
                    r.get("codigo", ""),
                    r.get("nombre", ""),
                    r.get("lote", ""),
                    r.get("cantidad", ""),
                    r.get("unidad", ""),
                    r.get("usuario_presta_nombre", ""),
                ),
            )

    def _refresh_emitidos(self):
        my_id = self._user.get("id")
        if not my_id:
            self._emit_all_rows = []
            self._emit_page = 1
            self._emit_total = 0
            self._emit_render_page()
            return

        mes = self.v_mes_historial.get().strip()
        rows = prest.prestamos_emitidos_por_usuario(
            my_id,
            self._maestras,
            mes=mes,
            limit=None,
        )

        desde_q = get_date_value(self.w_hist_desde)
        hasta_q = get_date_value(self.w_hist_hasta)
        codigo_q = self.v_hist_codigo.get().strip().upper()
        lote_q = self.v_hist_lote.get().strip().upper()
        destino_q = self.v_hist_destino.get().strip().upper()
        estado_q = self.v_hist_estado.get().strip().upper()

        if desde_q:
            rows = [r for r in rows if str(r.get("fecha_prestamo", "")).strip() >= desde_q]
        if hasta_q:
            rows = [r for r in rows if str(r.get("fecha_prestamo", "")).strip() <= hasta_q]
        if codigo_q:
            rows = [r for r in rows if codigo_q in str(r.get("codigo", "")).upper()]
        if lote_q:
            rows = [r for r in rows if lote_q in str(r.get("lote", "")).upper()]
        if destino_q:
            rows = [r for r in rows if destino_q in str(r.get("usuario_destino_nombre", "")).upper()]
        if estado_q:
            rows = [r for r in rows if estado_q in str(r.get("estado", "")).upper()]

        self._emit_all_rows = rows
        self._emit_total = len(rows)
        self._emit_page = 1
        self._emit_total_pages = max(1, -(-self._emit_total // self._emit_page_size))
        self._emit_render_page()

    def _emit_render_page(self):
        self.tree_emit.clear()
        start = (self._emit_page - 1) * self._emit_page_size
        for r in self._emit_all_rows[start:start + self._emit_page_size]:
            self.tree_emit.insert(
                "",
                "end",
                values=(
                    r.get("id"),
                    r.get("fecha_prestamo", ""),
                    r.get("codigo", ""),
                    r.get("nombre", ""),
                    r.get("lote", ""),
                    r.get("cantidad", ""),
                    r.get("usuario_destino_nombre", ""),
                    r.get("estado", ""),
                ),
            )
        self._emit_update_pag_buttons()

    def _emit_prev_page(self):
        if self._emit_page > 1:
            self._emit_page -= 1
            self._emit_render_page()

    def _emit_next_page(self):
        total_pages = getattr(self, "_emit_total_pages", 1)
        if self._emit_page < total_pages:
            self._emit_page += 1
            self._emit_render_page()

    def _emit_on_page_size_change(self, _event=None):
        try:
            self._emit_page_size = int(self.combo_emit_page_size.get())
            self._emit_page = 1
            self._emit_total_pages = max(1, -(-self._emit_total // self._emit_page_size))
            self._emit_render_page()
        except ValueError:
            pass

    def _emit_update_pag_buttons(self):
        if not hasattr(self, "btn_emit_prev"):
            return
        total_pages = getattr(self, "_emit_total_pages", 1)
        self.btn_emit_prev.config(state=tk.NORMAL if self._emit_page > 1 else tk.DISABLED)
        self.btn_emit_next.config(state=tk.NORMAL if self._emit_page < total_pages else tk.DISABLED)
        self.lbl_emit_page.config(text=f"Pagina {self._emit_page} de {total_pages}")
        if hasattr(self, "lbl_emit_total"):
            self.lbl_emit_total.config(text=f"({self._emit_total} registros)")

    def _selected_prestamo_id(self):
        sel = self.tree_pend.selection()
        if not sel:
            return None
        values = self.tree_pend.item(sel[0], "values")
        if not values:
            return None
        try:
            return int(values[0])
        except (TypeError, ValueError):
            return None

    def _responder(self, aceptar):
        id_prestamo = self._selected_prestamo_id()
        if id_prestamo is None:
            messagebox.showwarning("Aviso", "Seleccione un préstamo pendiente.", parent=self)
            return

        if aceptar:
            prompt = "Observación de recibido (opcional):"
            titulo = "Aceptar préstamo"
            ok_msg = "¿Desea aceptar el préstamo seleccionado?"
        else:
            prompt = "Motivo del rechazo (opcional):"
            titulo = "Rechazar préstamo"
            ok_msg = "¿Desea rechazar el préstamo seleccionado?"

        if not messagebox.askyesno(titulo, ok_msg, parent=self):
            return

        if not self._ask_firma_password_current_user():
            return

        obs = simpledialog.askstring(titulo, prompt, parent=self)
        ok, msg = prest.responder_prestamo(
            id_prestamo=id_prestamo,
            id_usuario_recibe=self._user.get("id"),
            aceptar=aceptar,
            observacion_recibo=obs or "",
            usuario_accion=self._user.get("usuario") or self._user.get("nombre", "SISTEMA"),
        )
        if ok:
            messagebox.showinfo("Préstamos", msg, parent=self)
            self._refresh_all()
        else:
            messagebox.showwarning("Préstamos", msg, parent=self)
