"""
_base_movimientos.py
Clase base para ventanas de Entradas y Salidas.
Proporciona: paginación, atajos de teclado, barra de progreso y mensajes de estado.
"""
import tkinter as tk
from tkinter import ttk

from config.config import COLORS


class MovimientosBase(tk.Toplevel):
    """Clase base para ventanas de movimientos con paginación y atajos."""

    def __init__(self, master, title):
        super().__init__(master)
        self.title(title)
        self.configure(bg=COLORS["secondary"])

        self.username = getattr(master, "username", "SISTEMA")

        # Estado de paginación
        self._current_page = 1
        self._page_size = 15
        self._total_records = 0
        self._total_pages = 0

        self._progress_bar = None
        self._tooltip = None

        self._build_shortcuts()

    # ------------------------------------------------------------------
    # Atajos de teclado
    # ------------------------------------------------------------------
    def _build_shortcuts(self):
        """Configura atajos de teclado globales para la ventana."""
        self.bind_all("<Control-g>", lambda e: self._save())
        self.bind_all("<Control-G>", lambda e: self._save())
        self.bind_all("<F5>", lambda e: self._refresh_all())
        self.bind_all("<Escape>", lambda e: self._on_escape())

    def _on_escape(self):
        """Cierra la ventana al presionar Escape (solo si no hay diálogos activos)."""
        try:
            self.destroy()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Barra de progreso
    # ------------------------------------------------------------------
    def _show_progress(self, start=True):
        """Muestra u oculta la barra de progreso indeterminada."""
        if start:
            if not hasattr(self, "_prog_frame") or not self._prog_frame.winfo_exists():
                self._prog_frame = tk.Frame(self, bg=COLORS["secondary"])
                self._prog_frame.pack(side="bottom", fill="x", padx=10, pady=2)
            else:
                for w in self._prog_frame.winfo_children():
                    w.destroy()

            self._progress_bar = ttk.Progressbar(
                self._prog_frame, mode="indeterminate", length=300
            )
            self._progress_bar.pack(pady=3)
            self._progress_bar.start(10)
            self.update_idletasks()
        else:
            if self._progress_bar and self._progress_bar.winfo_exists():
                self._progress_bar.stop()
                self._progress_bar.destroy()
                self._progress_bar = None
            if hasattr(self, "_prog_frame") and self._prog_frame.winfo_exists():
                self._prog_frame.destroy()

    # ------------------------------------------------------------------
    # Mensajes de estado
    # ------------------------------------------------------------------
    def _show_status(self, message, is_error=False, is_success=False):
        """Actualiza la etiqueta de estado con color e ícono apropiados."""
        if not hasattr(self, "lbl_status") or not self.lbl_status.winfo_exists():
            return
        if is_success:
            color = COLORS.get("success", "#2EAF62")
            icon = "✓ "
        elif is_error:
            color = COLORS.get("error", "#D94A4A")
            icon = "✗ "
        else:
            color = COLORS["text_muted"]
            icon = ""
        self.lbl_status.config(text=f"{icon}{message}", fg=color)
        self.after(3500, self._clear_status)

    def _clear_status(self):
        if hasattr(self, "lbl_status") and self.lbl_status.winfo_exists():
            self.lbl_status.config(text="Listo.", fg=COLORS["text_muted"])

    # ------------------------------------------------------------------
    # Paginación
    # ------------------------------------------------------------------
    def _build_pagination_controls(self, parent):
        """Construye y devuelve el frame con controles de paginación."""
        pag_frame = tk.Frame(parent, bg=COLORS["secondary"])

        btn_style = dict(
            bg=COLORS["primary"],
            fg="white",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            bd=0,
            padx=8,
            pady=3,
            cursor="hand2",
        )

        self.btn_pag_prev = tk.Button(
            pag_frame, text="◀ Anterior", command=self._prev_page, **btn_style
        )
        self.btn_pag_prev.pack(side="left", padx=2)

        self.lbl_page = tk.Label(
            pag_frame,
            text="Página 1 de 1",
            bg=COLORS["secondary"],
            fg=COLORS["text_dark"],
            font=("Segoe UI", 9),
        )
        self.lbl_page.pack(side="left", padx=10)

        self.btn_pag_next = tk.Button(
            pag_frame, text="Siguiente ▶", command=self._next_page, **btn_style
        )
        self.btn_pag_next.pack(side="left", padx=2)

        tk.Label(
            pag_frame,
            text="Mostrar:",
            bg=COLORS["secondary"],
            fg=COLORS["text_dark"],
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(15, 4))

        self.combo_page_size = ttk.Combobox(
            pag_frame,
            values=[10, 15, 25, 50],
            state="readonly",
            width=5,
            font=("Segoe UI", 9),
        )
        self.combo_page_size.set(str(self._page_size))
        self.combo_page_size.bind("<<ComboboxSelected>>", self._on_page_size_change)
        self.combo_page_size.pack(side="left", padx=2)

        self.lbl_total_records = tk.Label(
            pag_frame,
            text="",
            bg=COLORS["secondary"],
            fg=COLORS["text_muted"],
            font=("Segoe UI", 9, "italic"),
        )
        self.lbl_total_records.pack(side="left", padx=(12, 0))

        return pag_frame

    def _prev_page(self):
        if self._current_page > 1:
            self._current_page -= 1
            self._load_page()

    def _next_page(self):
        if self._current_page < self._total_pages:
            self._current_page += 1
            self._load_page()

    def _on_page_size_change(self, _event=None):
        try:
            self._page_size = int(self.combo_page_size.get())
            self._current_page = 1
            self._load_page()
        except ValueError:
            pass

    def _update_pagination_buttons(self):
        """Actualiza estado de botones e indicadores de paginación."""
        if not hasattr(self, "btn_pag_prev"):
            return
        self.btn_pag_prev.config(
            state=tk.NORMAL if self._current_page > 1 else tk.DISABLED
        )
        self.btn_pag_next.config(
            state=tk.NORMAL if self._current_page < self._total_pages else tk.DISABLED
        )
        self.lbl_page.config(
            text=f"Página {self._current_page} de {max(self._total_pages, 1)}"
        )
        if hasattr(self, "lbl_total_records"):
            self.lbl_total_records.config(
                text=f"({self._total_records} registros)"
            )

    # ------------------------------------------------------------------
    # Métodos a implementar por subclases
    # ------------------------------------------------------------------
    def _load_page(self):
        """Carga la página actual. Debe implementarse en la subclase."""
        pass

    def _refresh_all(self):
        """Refresca datos y maestras. Debe implementarse en la subclase."""
        pass

    def _save(self):
        """Guarda el formulario. Debe implementarse en la subclase."""
        pass

    def _clear_form(self):
        """Limpia el formulario. Debe implementarse en la subclase."""
        pass

    # ------------------------------------------------------------------
    # Tooltip simple
    # ------------------------------------------------------------------
    def _add_tooltip(self, widget, text):
        """Agrega un tooltip flotante a un widget."""
        def on_enter(e):
            try:
                self._tooltip = tk.Toplevel(widget)
                self._tooltip.wm_overrideredirect(True)
                self._tooltip.geometry(f"+{e.x_root + 10}+{e.y_root + 10}")
                tk.Label(
                    self._tooltip,
                    text=text,
                    bg="#FFFFE0",
                    fg="#202020",
                    relief="solid",
                    bd=1,
                    padx=4,
                    pady=2,
                    font=("Segoe UI", 8),
                ).pack()
            except Exception:
                pass

        def on_leave(_e):
            try:
                if self._tooltip and self._tooltip.winfo_exists():
                    self._tooltip.destroy()
                    self._tooltip = None
            except Exception:
                pass

        widget.bind("<Enter>", on_enter)
        widget.bind("<Leave>", on_leave)
