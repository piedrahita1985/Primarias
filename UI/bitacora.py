import tkinter as tk
from tkinter import ttk

from config.config import COLORS
from logica import bitacora_logica as bit
from UI._mov_utils import apply_default_window, attach_treeview_sorting, draw_title, get_date_value, make_date_input
from UI._searchable_treeview import SearchableTreeview


def open_window(master):
    BitacoraWindow(master)


class BitacoraWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Sistema de Gestion - Bitacora")
        self.configure(bg=COLORS["secondary"])
        apply_default_window(self)

        self.v_modulo = tk.StringVar()
        self.v_tipo_operacion = tk.StringVar()
        self.v_usuario = tk.StringVar()
        self.v_id_registro = tk.StringVar()
        self._desde_habilitada = False
        self._hasta_habilitada = False

        # Pagination state
        self._all_rows = []
        self._current_page = 1
        self._page_size = 25
        self._total_pages = 1
        self._total_records = 0

        draw_title(self, "Sistema de Gestion - Bitacora")
        self._build_ui()
        self._load_default()

    @staticmethod
    def _split_tipo_operacion(tipo_operacion):
        text = str(tipo_operacion or "").strip().upper()
        if not text:
            return "", ""
        if "-" in text:
            op, accion = text.split("-", 1)
            return op, accion
        return text, ""

    def _build_ui(self):
        wrap = tk.LabelFrame(
            self,
            text="  Auditoria de movimientos  ",
            bg=COLORS["secondary"],
            fg=COLORS["primary_dark"],
            font=("Segoe UI", 10, "bold"),
        )
        wrap.pack(fill="both", expand=True, padx=10, pady=10)

        top = tk.Frame(wrap, bg=COLORS["secondary"])
        top.pack(fill="x", padx=8, pady=8)

        frame_desde = tk.Frame(top, bg=COLORS["secondary"])
        frame_desde.pack(side="left", padx=(0, 8))
        self.w_desde = make_date_input(frame_desde, 0, 0, "Desde")
        self.w_desde.bind("<<DateEntrySelected>>", lambda _e: self._toggle_date_filter("desde", True))
        self._button(frame_desde, "Limpiar", "#B0B0B0", lambda: self._clear_date("desde")).grid(row=1, column=1, padx=(0, 8), pady=(0, 8))

        frame_hasta = tk.Frame(top, bg=COLORS["secondary"])
        frame_hasta.pack(side="left", padx=(0, 8))
        self.w_hasta = make_date_input(frame_hasta, 0, 0, "Hasta")
        self.w_hasta.bind("<<DateEntrySelected>>", lambda _e: self._toggle_date_filter("hasta", True))
        self._button(frame_hasta, "Limpiar", "#B0B0B0", lambda: self._clear_date("hasta")).grid(row=1, column=1, padx=(0, 8), pady=(0, 8))

        tk.Label(top, text="Usuario:", bg=COLORS["secondary"], font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        tk.Entry(top, textvariable=self.v_usuario, width=10).pack(side="left", padx=(0, 8))
        tk.Label(top, text="Tipo Operacion:", bg=COLORS["secondary"], font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        tk.Entry(top, textvariable=self.v_tipo_operacion, width=14).pack(side="left", padx=(0, 8))
        tk.Label(top, text="ID Registro:", bg=COLORS["secondary"], font=("Segoe UI", 9)).pack(side="left", padx=(0, 4))
        tk.Entry(top, textvariable=self.v_id_registro, width=8).pack(side="left", padx=(0, 8))

        self._button(top, "Filtrar", COLORS["primary"], self._apply_filters).pack(side="left", padx=(0, 6))
        self._button(top, "Borrar filtros", "#B0B0B0", self._clear_filters).pack(side="left")

        # Table in a frame with proper scrollbar
        tbl_frame = tk.Frame(wrap, bg=COLORS["secondary"])
        tbl_frame.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        tbl_frame.grid_rowconfigure(0, weight=1)
        tbl_frame.grid_columnconfigure(0, weight=1)

        cols = ("fecha_hora", "usuario", "operacion", "accion", "id_registro", "campo", "valor_anterior", "valor_nuevo")
        self.tree = SearchableTreeview(
            tbl_frame, columns=cols,
            search_columns=["usuario", "operacion", "accion", "campo"],
        )
        self.tree.pack(fill="both", expand=True)

        for key, title, width in [
            ("fecha_hora", "Fecha/Hora", 150),
            ("usuario", "Usuario", 110),
            ("operacion", "Operacion", 130),
            ("accion", "Accion", 110),
            ("id_registro", "ID Registro", 95),
            ("campo", "Campo", 160),
            ("valor_anterior", "Valor Anterior", 250),
            ("valor_nuevo", "Valor Nuevo", 250),
        ]:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="center")
        attach_treeview_sorting(self.tree.tree)

        # Pagination controls
        pag_frame = tk.Frame(wrap, bg=COLORS["secondary"])
        pag_frame.pack(fill="x", padx=8, pady=(0, 4))

        btn_style = dict(bg=COLORS["primary"], fg="white", font=("Segoe UI", 9, "bold"),
                         relief="flat", bd=0, padx=8, pady=3, cursor="hand2")
        self.btn_pag_prev = tk.Button(pag_frame, text="< Anterior", command=self._prev_page, **btn_style)
        self.btn_pag_prev.pack(side="left", padx=2)
        self.lbl_page = tk.Label(pag_frame, text="Pagina 1 de 1", bg=COLORS["secondary"],
                                 fg=COLORS["text_dark"], font=("Segoe UI", 9))
        self.lbl_page.pack(side="left", padx=10)
        self.btn_pag_next = tk.Button(pag_frame, text="Siguiente >", command=self._next_page, **btn_style)
        self.btn_pag_next.pack(side="left", padx=2)
        tk.Label(pag_frame, text="Mostrar:", bg=COLORS["secondary"], fg=COLORS["text_dark"],
                 font=("Segoe UI", 9)).pack(side="left", padx=(15, 4))
        self.combo_page_size = ttk.Combobox(pag_frame, values=[25, 50, 100, 200],
                                            state="readonly", width=6, font=("Segoe UI", 9))
        self.combo_page_size.set("25")
        self.combo_page_size.bind("<<ComboboxSelected>>", self._on_page_size_change)
        self.combo_page_size.pack(side="left", padx=2)
        self.lbl_total_bit = tk.Label(pag_frame, text="", bg=COLORS["secondary"],
                                      fg=COLORS["text_muted"], font=("Segoe UI", 9, "italic"))
        self.lbl_total_bit.pack(side="left", padx=(12, 0))

        bottom = tk.Frame(self, bg=COLORS["secondary"])
        bottom.pack(fill="x", padx=10, pady=(0, 10))
        self._button(bottom, "Actualizar", COLORS["primary"], self._load_default).pack(side="right", padx=(6, 0))
        self._button(bottom, "Salir", "#6C757D", self.destroy).pack(side="right")

    def _button(self, parent, text, bg, cmd):
        return tk.Button(parent, text=text, bg=bg, fg="white", font=("Segoe UI", 9, "bold"),
                         relief="flat", bd=0, padx=10, pady=5, cursor="hand2", command=cmd)

    def _toggle_date_filter(self, which, enabled):
        if which == "desde":
            self._desde_habilitada = enabled
        else:
            self._hasta_habilitada = enabled

    def _clear_date(self, which):
        self._toggle_date_filter(which, False)
        widget = self.w_desde if which == "desde" else self.w_hasta
        var = getattr(widget, "_fallback_var", None)
        if var is not None:
            var.set("")
            return
        try:
            widget.delete(0, "end")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------
    def _load_default(self):
        self._all_rows = bit.filtrar(desde="", hasta="", usuario="", tipo_operacion="", id_registro="")
        self._current_page = 1
        self._total_records = len(self._all_rows)
        self._total_pages = max(1, -(-self._total_records // self._page_size))
        self._render_page()

    def _apply_filters(self):
        self._all_rows = bit.filtrar(
            desde=get_date_value(self.w_desde) if self._desde_habilitada else "",
            hasta=get_date_value(self.w_hasta) if self._hasta_habilitada else "",
            usuario=self.v_usuario.get().strip(),
            tipo_operacion=self.v_tipo_operacion.get().strip(),
            id_registro=self.v_id_registro.get().strip(),
        )
        self._current_page = 1
        self._total_records = len(self._all_rows)
        self._total_pages = max(1, -(-self._total_records // self._page_size))
        self._render_page()

    def _render_page(self):
        self.tree.clear()
        start = (self._current_page - 1) * self._page_size
        page_rows = self._all_rows[start:start + self._page_size]
        for r in page_rows:
            operacion, accion = self._split_tipo_operacion(r.get("tipo_operacion", ""))
            self.tree.insert("", "end", values=(
                r.get("fecha_hora", ""),
                r.get("usuario", ""),
                operacion,
                accion,
                r.get("id_registro", ""),
                r.get("campo", ""),
                r.get("valor_anterior", ""),
                r.get("valor_nuevo", ""),
            ))
        self._update_pagination_buttons()

    def _prev_page(self):
        if self._current_page > 1:
            self._current_page -= 1
            self._render_page()

    def _next_page(self):
        if self._current_page < self._total_pages:
            self._current_page += 1
            self._render_page()

    def _on_page_size_change(self, _event=None):
        try:
            self._page_size = int(self.combo_page_size.get())
            self._current_page = 1
            self._total_pages = max(1, -(-self._total_records // self._page_size))
            self._render_page()
        except ValueError:
            pass

    def _update_pagination_buttons(self):
        if not hasattr(self, "btn_pag_prev"):
            return
        self.btn_pag_prev.config(state=tk.NORMAL if self._current_page > 1 else tk.DISABLED)
        self.btn_pag_next.config(state=tk.NORMAL if self._current_page < self._total_pages else tk.DISABLED)
        self.lbl_page.config(text=f"Pagina {self._current_page} de {max(self._total_pages, 1)}")
        if hasattr(self, "lbl_total_bit"):
            self.lbl_total_bit.config(text=f"({self._total_records} registros)")

    def _clear_filters(self):
        self._clear_date("desde")
        self._clear_date("hasta")
        self.v_usuario.set("")
        self.v_tipo_operacion.set("")
        self.v_id_registro.set("")
        self._load_default()