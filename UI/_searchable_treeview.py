# UI/_searchable_treeview.py
import tkinter as tk
from tkinter import ttk
from config.config import COLORS


class SearchableTreeview(tk.Frame):
    """Treeview con barra de búsqueda integrada."""

    def __init__(self, parent, columns, search_columns=None, height=15, **kwargs):
        super().__init__(parent, bg=COLORS["secondary"])

        self.search_columns = search_columns or list(columns)
        self._original_items = {}  # {item_id: (search_text, values, kwargs)}
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search)

        # Frame para la barra de búsqueda
        search_frame = tk.Frame(self, bg=COLORS["secondary"], height=32)
        search_frame.pack(fill="x", pady=(0, 4))
        search_frame.pack_propagate(False)

        tk.Label(
            search_frame,
            text="🔍 Buscar:",
            bg=COLORS["secondary"],
            fg=COLORS["text_dark"],
            font=("Segoe UI", 9, "bold"),
        ).pack(side="left", padx=(5, 5))

        self._search_entry = tk.Entry(
            search_frame,
            textvariable=self._search_var,
            bg=COLORS["surface"],
            font=("Segoe UI", 10),
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["border_soft"],
        )
        self._search_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        # Botón limpiar
        self._clear_btn = tk.Button(
            search_frame,
            text="✖",
            command=self._clear_search,
            bg=COLORS["surface"],
            fg=COLORS["text_muted"],
            font=("Segoe UI", 9),
            relief="flat",
            cursor="hand2",
        )
        self._clear_btn.pack(side="right", padx=5)

        # Frame para el treeview y scrollbar vertical
        tree_frame = tk.Frame(self, bg=COLORS["secondary"])
        tree_frame.pack(fill="both", expand=True)

        # Treeview
        self.tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", height=height, **kwargs
        )
        self.tree.pack(side="left", fill="both", expand=True)

        # Scrollbar vertical
        ysb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        ysb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=ysb.set)

        # Scrollbar horizontal
        xsb = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        xsb.pack(fill="x")
        self.tree.configure(xscrollcommand=xsb.set)

    # ------------------------------------------------------------------
    # Proxy methods
    # ------------------------------------------------------------------
    def heading(self, column, **kwargs):
        return self.tree.heading(column, **kwargs)

    def column(self, column, **kwargs):
        return self.tree.column(column, **kwargs)

    def tag_configure(self, tag, **kwargs):
        return self.tree.tag_configure(tag, **kwargs)

    def insert(self, parent, index, values, **kwargs):
        """Inserta un item y lo guarda en caché para búsqueda."""
        item_id = self.tree.insert(parent, index, values=values, **kwargs)
        # Construir texto de búsqueda solo con las columnas especificadas
        search_parts = []
        col_list = list(self.tree["columns"])
        for col in self.search_columns:
            if col in col_list:
                col_index = col_list.index(col)
                if col_index < len(values):
                    search_parts.append(str(values[col_index]).lower())
        search_text = " ".join(search_parts)
        self._original_items[item_id] = (search_text, values, kwargs)
        return item_id

    def delete(self, *items):
        """Proxy para delete del treeview."""
        for item in items:
            self._original_items.pop(item, None)
        if items:
            return self.tree.delete(*items)

    def get_children(self, item=""):
        return self.tree.get_children(item)

    def selection(self):
        return self.tree.selection()

    def item(self, item, **kwargs):
        return self.tree.item(item, **kwargs)

    def set(self, item, column=None, value=None):
        return self.tree.set(item, column, value)

    def clear(self):
        """Limpia todos los items (visible + caché)."""
        self.tree.delete(*self.tree.get_children())
        self._original_items.clear()

    # ------------------------------------------------------------------
    # Search logic
    # ------------------------------------------------------------------
    def _on_search(self, *args):
        """Filtra items según texto de búsqueda."""
        search_text = self._search_var.get().strip().lower()

        if not search_text:
            # Restaurar todos desde caché
            current_ids = set(self.tree.get_children())
            for item_id, (_, values, kw) in self._original_items.items():
                if item_id not in current_ids:
                    self.tree.insert("", "end", iid=item_id, values=values, **kw)
            return

        visible_items = set()
        current_ids = set(self.tree.get_children())

        for item_id, (text, values, kw) in self._original_items.items():
            if search_text in text:
                if item_id not in current_ids:
                    self.tree.insert("", "end", iid=item_id, values=values, **kw)
                visible_items.add(item_id)

        # Ocultar los que no coinciden (sin modificar _original_items)
        for item_id in list(self.tree.get_children()):
            if item_id not in visible_items:
                self.tree.delete(item_id)
                # Re-add to _original_items since tree.delete was called directly
                # (not through our proxy), so _original_items is still intact

    def _clear_search(self):
        self._search_var.set("")
        self._search_entry.focus_set()
