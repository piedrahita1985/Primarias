import tkinter as tk
from tkinter import messagebox

from config.config import COLORS


class MaestraBase(tk.Toplevel):
    """
    Clase base para todas las ventanas de maestras.

    Subclases deben definir los atributos de clase:
        TITLE        : str   - Titulo de la ventana
        LOGICA_MODULE: module - Modulo de logica correspondiente
        WINDOW_SIZE  : str   - Geometria inicial (default "1100x650")
        LIST_TITLE   : str   - Texto del LabelFrame izquierdo
        DETAIL_TITLE : str   - Texto del LabelFrame derecho

    Subclases deben implementar:
        _build_form(parent)       -> None   Construye widgets del formulario
        _get_form_data()          -> dict   Lee campos del formulario
        _set_form_data(r: dict)   -> None   Carga un registro en el formulario
        _clear_form()             -> None   Limpia todos los campos
        _list_label(r: dict)      -> str    Texto a mostrar en el listbox
        _validate(datos: dict)    -> (bool, str)  Valida antes de guardar
    """

    TITLE = "Maestra"
    LOGICA_MODULE = None
    WINDOW_SIZE = "1100x650"
    LIST_TITLE = "Registros"
    DETAIL_TITLE = "Detalle"
    _MSG_SIN_SELECCION = "Seleccione un registro de la lista."

    def __init__(self, master):
        super().__init__(master)
        self._logica = self.LOGICA_MODULE
        self._registros: list = []
        self._seleccionado_id = None
        self._modo = "ver"          # "ver" | "nuevo" | "actualizar"
        self._var_estado = tk.StringVar(value="HABILITADA")

        self.wm_title(self.TITLE)
        self.configure(bg=COLORS["secondary"])
        self.geometry(self.WINDOW_SIZE)
        self.minsize(900, 550)
        self.resizable(True, True)

        self._build_ui()
        self._update_estado_color()
        self._cargar_lista()

    # ──────────────────────────────────────────────────────
    # Construccion de la UI base
    # ──────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Header ──────────────────────────────────────
        header = tk.Frame(self, bg=COLORS["primary"], height=54)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header,
            text=self.TITLE,
            bg=COLORS["primary"],
            fg="white",
            font=("Segoe UI", 15, "bold"),
        ).pack(expand=True)

        # ── Separador ───────────────────────────────────
        tk.Frame(self, bg=COLORS["border_soft"], height=2).pack(fill="x")

        # ── Area de contenido ───────────────────────────
        content = tk.Frame(self, bg=COLORS["secondary"])
        content.pack(fill="both", expand=True, padx=14, pady=(10, 0))
        content.grid_columnconfigure(0, weight=3)
        content.grid_columnconfigure(1, weight=7)
        content.grid_rowconfigure(0, weight=1)

        # Panel izquierdo - lista
        left = tk.LabelFrame(
            content,
            text=f"  {self.LIST_TITLE}  ",
            bg=COLORS["secondary"],
            fg=COLORS["text_dark"],
            font=("Segoe UI", 9, "bold"),
            bd=1,
            relief="groove",
            padx=4,
            pady=4,
        )
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        left.grid_rowconfigure(0, weight=1)
        left.grid_columnconfigure(0, weight=1)

        sb = tk.Scrollbar(left, orient="vertical")
        self._listbox = tk.Listbox(
            left,
            yscrollcommand=sb.set,
            bg=COLORS["surface"],
            fg=COLORS["text_dark"],
            selectbackground=COLORS["primary"],
            selectforeground="white",
            font=("Segoe UI", 9),
            activestyle="none",
            relief="flat",
            bd=1,
        )
        sb.config(command=self._listbox.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self._listbox.grid(row=0, column=0, sticky="nsew")
        self._listbox.bind("<<ListboxSelect>>", self._on_select)

        # Panel derecho - formulario
        right = tk.LabelFrame(
            content,
            text=f"  {self.DETAIL_TITLE}  ",
            bg=COLORS["secondary"],
            fg=COLORS["text_dark"],
            font=("Segoe UI", 9, "bold"),
            bd=1,
            relief="groove",
            padx=12,
            pady=12,
        )
        right.grid(row=0, column=1, sticky="nsew")
        self._build_form(right)

        # ── Barra de botones ─────────────────────────────
        separator = tk.Frame(self, bg=COLORS["border_soft"], height=1)
        separator.pack(fill="x", padx=14)

        btn_bar = tk.Frame(self, bg=COLORS["secondary"])
        btn_bar.pack(fill="x", padx=14, pady=10)

        _btn(btn_bar, "Nuevo",       "#6C757D",        self._accion_nuevo).pack(side="left", padx=(0, 6))
        _btn(btn_bar, "Actualizar",  COLORS["primary"], self._accion_actualizar).pack(side="left", padx=(0, 6))
        _btn(btn_bar, "Habilitar",   COLORS["success"], self._accion_habilitar).pack(side="left", padx=(0, 6))
        _btn(btn_bar, "Inhabilitar", COLORS["error"],   self._accion_inhabilitar).pack(side="left")

        _btn(btn_bar, "Salir",   "#6C757D",        self.destroy).pack(side="right", padx=(6, 0))
        _btn(btn_bar, "Guardar", COLORS["primary"], self._accion_guardar).pack(side="right", padx=(6, 0))

    # ──────────────────────────────────────────────────────
    # Hooks - subclases deben implementar
    # ──────────────────────────────────────────────────────

    def _build_form(self, parent):
        pass  # Implemented by subclass

    def _get_form_data(self) -> dict:
        return {}  # Implemented by subclass

    def _set_form_data(self, record: dict):
        pass  # Implemented by subclass

    def _clear_form(self):
        pass  # Implemented by subclass

    def _list_label(self, record: dict) -> str:
        return str(record)

    def _validate(self, datos: dict):
        """Retorna (True, '') si es valido, o (False, 'mensaje') si hay error."""
        return True, ""

    # ──────────────────────────────────────────────────────
    # Logica de acciones
    # ──────────────────────────────────────────────────────

    def _cargar_lista(self):
        self._registros = self._logica.cargar()
        self._listbox.delete(0, "end")
        for r in self._registros:
            self._listbox.insert("end", self._list_label(r))

    def _on_select(self, event=None):
        sel = self._listbox.curselection()
        if not sel:
            return
        r = self._registros[sel[0]]
        self._seleccionado_id = r["id"]
        self._set_form_data(r)
        self._var_estado.set(r.get("estado", "HABILITADA"))
        self._update_estado_color()

    def _accion_nuevo(self):
        self._seleccionado_id = None
        self._modo = "nuevo"
        self._clear_form()
        self._var_estado.set("HABILITADA")
        self._update_estado_color()
        self._listbox.selection_clear(0, "end")

    def _accion_actualizar(self):
        if self._seleccionado_id is None:
            messagebox.showwarning("Aviso", self._MSG_SIN_SELECCION, parent=self)
            return
        self._modo = "actualizar"
        messagebox.showinfo(
            "Modo Actualizar",
            "Modifique los campos deseados y presione Guardar.",
            parent=self,
        )

    def _accion_habilitar(self):
        if self._seleccionado_id is None:
            messagebox.showwarning("Aviso", self._MSG_SIN_SELECCION, parent=self)
            return
        self._logica.habilitar(self._registros, self._seleccionado_id)
        self._var_estado.set("HABILITADA")
        self._update_estado_color()
        self._cargar_lista()

    def _accion_inhabilitar(self):
        if self._seleccionado_id is None:
            messagebox.showwarning("Aviso", self._MSG_SIN_SELECCION, parent=self)
            return
        if not messagebox.askyesno("Confirmar", "¿Desea inhabilitar este registro?", parent=self):
            return
        self._logica.inhabilitar(self._registros, self._seleccionado_id)
        self._var_estado.set("INHABILITADA")
        self._update_estado_color()
        self._cargar_lista()

    def _accion_guardar(self):
        if self._modo not in ("nuevo", "actualizar"):
            messagebox.showwarning(
                "Aviso",
                "Presione 'Nuevo' para agregar o seleccione un registro y presione 'Actualizar'.",
                parent=self,
            )
            return
        datos = self._get_form_data()
        valido, mensaje = self._validate(datos)
        if not valido:
            messagebox.showwarning("Aviso", mensaje, parent=self)
            return

        if self._modo == "nuevo":
            self._logica.agregar(self._registros, datos)
            messagebox.showinfo("Exito", "Registro guardado correctamente.", parent=self)
        else:
            self._logica.actualizar(self._registros, self._seleccionado_id, datos)
            messagebox.showinfo("Exito", "Registro actualizado correctamente.", parent=self)

        self._cargar_lista()
        self._clear_form()
        self._modo = "ver"
        self._seleccionado_id = None

    def _update_estado_color(self):
        if hasattr(self, "_lbl_estado"):
            estado = self._var_estado.get()
            self._lbl_estado.configure(
                fg=COLORS["success"] if estado == "HABILITADA" else COLORS["error"]
            )


# ──────────────────────────────────────────────────────────
# Utilidades compartidas para los formularios
# ──────────────────────────────────────────────────────────

def _btn(parent, text, bg, cmd, width=12):
    """Crea un boton estandar para la barra de acciones."""
    return tk.Button(
        parent,
        text=text,
        bg=bg,
        fg="white",
        font=("Segoe UI", 10, "bold"),
        relief="flat",
        cursor="hand2",
        width=width,
        padx=8,
        pady=6,
        bd=0,
        command=cmd,
        activeforeground="white",
        activebackground=bg,
    )


def form_label(parent, text, row, col, colspan=2):
    """Etiqueta descriptiva de campo en grid."""
    tk.Label(
        parent,
        text=text,
        bg=COLORS["secondary"],
        fg=COLORS["text_muted"],
        font=("Segoe UI", 9),
    ).grid(row=row, column=col, columnspan=colspan, sticky="w", padx=(0, 10), pady=(8, 0))


def form_entry(parent, var, row, col, colspan=2, show=""):
    """Entry estandar de formulario en grid."""
    e = tk.Entry(
        parent,
        textvariable=var,
        show=show,
        bg=COLORS["surface"],
        fg=COLORS["text_dark"],
        font=("Segoe UI", 10),
        relief="flat",
        bd=0,
        highlightthickness=1,
        highlightbackground=COLORS["border_soft"],
        highlightcolor=COLORS["primary"],
    )
    e.grid(row=row, column=col, columnspan=colspan, sticky="ew", padx=(0, 10), pady=(2, 6))
    return e


def form_estado(parent, var_estado, row, col, colspan=2):
    """Bloque de Estado (etiqueta + valor coloreado) en grid."""
    frame = tk.Frame(parent, bg=COLORS["secondary"])
    frame.grid(row=row, column=col, columnspan=colspan, rowspan=2, sticky="w", padx=(0, 10), pady=(8, 0))
    tk.Label(
        frame,
        text="Estado",
        bg=COLORS["secondary"],
        fg=COLORS["text_muted"],
        font=("Segoe UI", 9),
    ).pack(anchor="w")
    lbl = tk.Label(
        frame,
        textvariable=var_estado,
        bg=COLORS["secondary"],
        font=("Segoe UI", 13, "bold"),
        fg=COLORS["success"],
    )
    lbl.pack(anchor="w", pady=(2, 0))
    return lbl
