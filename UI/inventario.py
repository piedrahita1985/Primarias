import tkinter as tk
from tkinter import ttk

from config.config import COLORS
from logica import inventario_mov_logica as inv
from UI._mov_utils import apply_default_window, attach_treeview_sorting, draw_title
from UI._searchable_treeview import SearchableTreeview


COLUMNS = [
    ("codigo", "Codigo", 90),
    ("propiedad", "Propiedad", 120),
    ("tipo_muestras", "Tipo Muestras", 130),
    ("uso_previsto", "Uso Previsto", 130),
    ("no_caja", "No Caja", 80),
    ("ubicacion", "Ubicacion", 90),
    ("condicion_alm", "Cond. Almacenamiento", 220),
    ("nombre", "Nombre", 170),
    ("potencia", "Potencia", 90),
    ("lote", "Lote", 90),
    ("catalogo", "Catalogo", 110),
    ("fecha_ingreso", "Fecha Ingreso", 105),
    ("fecha_vencimiento", "Fecha Vencimiento", 115),
    ("alarma_fv", "Alarma FV", 120),
    ("unidad", "Unidad", 70),
    ("presentacion", "Presentacion", 95),
    ("cantidad_minima", "Cant. Min", 85),
    ("color_refuerzo", "Color Refuerzo", 110),
    ("certificado_anl", "Certificado", 90),
    ("ficha_seguridad", "Ficha Seguridad", 110),
    ("factura_compra", "Factura Compra", 110),
    ("codigo_sistema", "Codigo Sistema", 120),
    ("alarma_stock", "Alarma Stock", 170),
    ("stock", "Stock", 80),
]


def open_window(master):
    InventarioWindow(master)


class InventarioWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Sistema de Gestion - Inventario")
        self.configure(bg=COLORS["secondary"])
        apply_default_window(self, min_width=1100, min_height=700)
        self._tooltip = None
        self._refresh_job = None
        self._all_rows = []
        self._current_page = 1
        self._page_size = 50
        self._total_pages = 1
        self._total_records = 0

        draw_title(self, "Sistema de Gestion - Inventario")

        wrap = tk.Frame(self, bg=COLORS["secondary"])
        wrap.pack(fill="both", expand=True, padx=10, pady=10)

        top = tk.Frame(wrap, bg=COLORS["secondary"])
        top.pack(fill="x", pady=(0, 6))

        tk.Label(top, text="Vista consolidada de inventario (entradas - salidas)", bg=COLORS["secondary"], fg=COLORS["text_dark"], font=("Segoe UI", 10, "bold")).pack(side="left")

        legend = tk.Frame(top, bg=COLORS["secondary"])
        legend.pack(side="left", padx=(18, 0))
        tk.Label(legend, text="  VENCIDO  ", bg="#FFD6D6", fg="#8B0000", font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 6))
        tk.Label(legend, text="  PROXIMO A VENCER  ", bg="#FFF3CD", fg="#7A5D00", font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 6))
        tk.Label(legend, text="  OK  ", bg="#DFF7E2", fg="#1E6B2A", font=("Segoe UI", 8, "bold")).pack(side="left")
        tk.Label(legend, text="  BAJO MINIMO  ", bg="#EBD8FF", fg="#5B2A86", font=("Segoe UI", 8, "bold")).pack(side="left", padx=(6, 0))

        tk.Button(top, text="Actualizar", bg=COLORS["primary"], fg="white", font=("Segoe UI", 9, "bold"), relief="flat", bd=0, padx=10, pady=5, cursor="hand2", command=self._load_data).pack(side="right", padx=(0, 6))
        tk.Button(top, text="Salir", bg="#6C757D", fg="white", font=("Segoe UI", 9, "bold"), relief="flat", bd=0, padx=10, pady=5, cursor="hand2", command=self.destroy).pack(side="right", padx=(0, 6))

        table_frame = tk.Frame(wrap, bg=COLORS["secondary"])
        table_frame.pack(fill="both", expand=True)
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        self.tree = SearchableTreeview(
            table_frame,
            columns=[c[0] for c in COLUMNS],
            search_columns=["codigo", "nombre", "lote", "ubicacion"],
        )
        self.tree.pack(fill="both", expand=True)

        style = ttk.Style(self)
        style.configure("Treeview", rowheight=25, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

        for key, title, width in COLUMNS:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="center")
        attach_treeview_sorting(self.tree.tree)

        self.tree.tag_configure("vencido", background="#FFD6D6")
        self.tree.tag_configure("proximo", background="#FFF3CD")
        self.tree.tag_configure("ok", background="#DFF7E2")
        self.tree.tag_configure("stock_bajo", background="#EBD8FF")

        self.tree.tree.bind("<Motion>", self._on_tree_motion)
        self.tree.tree.bind("<Leave>", lambda _e: self._hide_tooltip())
        self.bind("<Destroy>", self._on_destroy)

        # Pagination controls (built before first _load_data call)
        pag_frame = tk.Frame(wrap, bg=COLORS["secondary"])
        pag_frame.pack(fill="x", pady=(4, 0))

        btn_style = dict(bg=COLORS["primary"], fg="white", font=("Segoe UI", 9, "bold"),
                         relief="flat", bd=0, padx=8, pady=3, cursor="hand2")
        self.btn_pag_prev = tk.Button(pag_frame, text="< Anterior",
                                      command=self._prev_page, **btn_style)
        self.btn_pag_prev.pack(side="left", padx=2)
        self.lbl_page = tk.Label(pag_frame, text="Pagina 1 de 1", bg=COLORS["secondary"],
                                 fg=COLORS["text_dark"], font=("Segoe UI", 9))
        self.lbl_page.pack(side="left", padx=10)
        self.btn_pag_next = tk.Button(pag_frame, text="Siguiente >",
                                      command=self._next_page, **btn_style)
        self.btn_pag_next.pack(side="left", padx=2)
        tk.Label(pag_frame, text="Mostrar:", bg=COLORS["secondary"], fg=COLORS["text_dark"],
                 font=("Segoe UI", 9)).pack(side="left", padx=(15, 4))
        self.combo_page_size = ttk.Combobox(pag_frame, values=[25, 50, 100, 200],
                                            state="readonly", width=6, font=("Segoe UI", 9))
        self.combo_page_size.set("50")
        self.combo_page_size.bind("<<ComboboxSelected>>", self._on_page_size_change)
        self.combo_page_size.pack(side="left", padx=2)
        self.lbl_total_inv = tk.Label(pag_frame, text="", bg=COLORS["secondary"],
                                      fg=COLORS["text_muted"], font=("Segoe UI", 9, "italic"))
        self.lbl_total_inv.pack(side="left", padx=(12, 0))

        self._load_data()
        self._schedule_refresh()

    def _load_data(self):
        """Carga todos los datos, almacena snapshot y muestra la pagina actual."""
        self._all_rows = []
        for row in inv.cargar_snapshot():
            tag = ""
            if row.get("alarma_stock") == "BAJO MINIMO":
                tag = "stock_bajo"
            elif row.get("alarma_fv") == "VENCIDO":
                tag = "vencido"
            elif row.get("alarma_fv") == "PROXIMO A VENCER":
                tag = "proximo"
            elif row.get("alarma_fv") == "OK":
                tag = "ok"
            self._all_rows.append((row, tag))

        self._total_records = len(self._all_rows)
        self._total_pages = max(1, -(-self._total_records // self._page_size))
        if self._current_page > self._total_pages:
            self._current_page = self._total_pages
        self._render_page()

    def _render_page(self):
        """Muestra la pagina actual del snapshot ya cargado."""
        self.tree.clear()
        start = (self._current_page - 1) * self._page_size
        page_rows = self._all_rows[start:start + self._page_size]
        for row, tag in page_rows:
            values = [row.get(c[0], "") for c in COLUMNS]
            self.tree.insert("", "end", values=values, tags=(tag,) if tag else ())
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
        if hasattr(self, "lbl_total_inv"):
            self.lbl_total_inv.config(text=f"({self._total_records} registros)")

    def _on_tree_motion(self, event):
        row_id = self.tree.tree.identify_row(event.y)
        col_id = self.tree.tree.identify_column(event.x)
        if not row_id or not col_id:
            self._hide_tooltip()
            return

        col_idx = int(col_id.replace("#", "")) - 1
        if col_idx < 0 or col_idx >= len(COLUMNS):
            self._hide_tooltip()
            return

        key = COLUMNS[col_idx][0]
        if key not in {"nombre", "condicion_alm"}:
            self._hide_tooltip()
            return

        values = self.tree.item(row_id, "values")
        if col_idx >= len(values):
            self._hide_tooltip()
            return

        text = str(values[col_idx])
        if len(text) < 26:
            self._hide_tooltip()
            return

        self._show_tooltip(event.x_root + 12, event.y_root + 12, text)

    def _show_tooltip(self, x, y, text):
        if self._tooltip is not None:
            lbl = getattr(self._tooltip, "_lbl", None)
            if lbl is not None and lbl.cget("text") == text:
                self._tooltip.geometry(f"+{x}+{y}")
                return
            self._hide_tooltip()

        tip = tk.Toplevel(self)
        tip.wm_overrideredirect(True)
        tip.attributes("-topmost", True)
        tip.geometry(f"+{x}+{y}")
        lbl = tk.Label(
            tip,
            text=text,
            justify="left",
            bg="#FFFFE0",
            fg="#202020",
            relief="solid",
            bd=1,
            padx=6,
            pady=4,
            wraplength=520,
            font=("Segoe UI", 9),
        )
        lbl.pack()
        tip._lbl = lbl
        self._tooltip = tip

    def _hide_tooltip(self):
        if self._tooltip is not None:
            self._tooltip.destroy()
            self._tooltip = None

    def _schedule_refresh(self):
        self._refresh_job = self.after(3000, self._refresh_tick)

    def _refresh_tick(self):
        self._refresh_job = None
        if not self.winfo_exists():
            return
        self._load_data()
        self._schedule_refresh()

    def _on_destroy(self, _event=None):
        if self._refresh_job is not None:
            try:
                self.after_cancel(self._refresh_job)
            except Exception:
                pass
            self._refresh_job = None