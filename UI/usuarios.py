import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox
from pathlib import Path
import shutil

import logica.usuarios_logica as _logica
from config.config import COLORS
from app_paths import resource_path
from UI._base_maestra import MaestraBase, form_label, form_entry, form_estado

_ROLES = ["administrador", "analista", "supervisor", "visualizador"]

_PERMISOS_MENU = [
    ("entradas", "Entradas"),
    ("salidas", "Salidas"),
    ("inventario", "Inventario"),
    ("bitacora", "Bitácora"),
    ("prestamos", "Préstamos"),
    ("recibidos", "Recibidos"),
    ("sustancias", "Sustancias"),
    ("tipos_entrada", "Tipos entrada"),
    ("tipos_salida", "Tipos salida"),
    ("fabricantes", "Fabricantes"),
    ("unidades", "Unidades"),
    ("ubicaciones", "Ubicaciones"),
    ("condiciones", "Condiciones"),
    ("colores", "Colores"),
    ("usuarios", "Usuarios"),
]

_PERMISOS_MOVIMIENTOS = [
    ("entradas", "Entradas"),
    ("salidas", "Salidas"),
    ("inventario", "Inventario"),
    ("bitacora", "Bitácora"),
    ("prestamos", "Préstamos"),
    ("recibidos", "Recibidos"),
]

_PERMISOS_MAESTRAS = [
    ("sustancias", "Sustancias"),
    ("tipos_entrada", "Tipos entrada"),
    ("tipos_salida", "Tipos salida"),
    ("fabricantes", "Fabricantes"),
    ("unidades", "Unidades"),
    ("ubicaciones", "Ubicaciones"),
    ("condiciones", "Condiciones"),
    ("colores", "Colores"),
    ("usuarios", "Usuarios"),
]


def open_window(master):
    UsuariosWindow(master)


class UsuariosWindow(MaestraBase):
    TITLE = "Maestra de Usuarios"
    LOGICA_MODULE = _logica
    WINDOW_SIZE = "1050x580"
    LIST_TITLE = "Usuarios registrados"
    DETAIL_TITLE = "Detalle del usuario"
    SHOW_UPDATE_BUTTON = False
    DIRECT_SAVE_ON_SELECTION = True
    CONFIRM_DIRECT_SAVE_MESSAGE = "¿Desea guardar los cambios del usuario seleccionado?"

    # ── Construccion del formulario ──────────────────────

    def _build_form(self, parent):
        self._v_usuario = tk.StringVar()
        self._v_contrasena = tk.StringVar()
        self._v_nombre = tk.StringVar()
        self._v_rol = tk.StringVar()
        self._v_firma_path = tk.StringVar()
        self._v_firma_password = tk.StringVar()
        self._show_pass = tk.BooleanVar(value=False)
        self._perm_vars = {
            "entradas": tk.BooleanVar(value=True),
            "salidas": tk.BooleanVar(value=True),
            "inventario": tk.BooleanVar(value=True),
            "bitacora": tk.BooleanVar(value=True),
            "prestamos": tk.BooleanVar(value=True),
            "recibidos": tk.BooleanVar(value=True),
            "sustancias": tk.BooleanVar(value=True),
            "tipos_entrada": tk.BooleanVar(value=True),
            "tipos_salida": tk.BooleanVar(value=True),
            "fabricantes": tk.BooleanVar(value=True),
            "unidades": tk.BooleanVar(value=True),
            "ubicaciones": tk.BooleanVar(value=True),
            "condiciones": tk.BooleanVar(value=True),
            "colores": tk.BooleanVar(value=True),
            "usuarios": tk.BooleanVar(value=True),
        }

        f = tk.Frame(parent, bg=COLORS["secondary"])
        f.pack(fill="both", expand=True)
        for i in range(6):
            f.grid_columnconfigure(i, weight=1)

        form_label(f, "Usuario", 0, 0, 2)
        form_entry(f, self._v_usuario, 1, 0, 2)

        form_label(f, "Contrasena", 0, 2, 2)
        self._entry_pass = form_entry(f, self._v_contrasena, 1, 2, 2, show="*")

        form_label(f, "Nombre completo", 0, 4, 2)
        form_entry(f, self._v_nombre, 1, 4, 2)

        # Toggle mostrar/ocultar contrasena
        self._btn_toggle = tk.Button(
            f,
            text="Mostrar",
            bg=COLORS["surface_alt"],
            fg=COLORS["primary"],
            font=("Segoe UI", 8),
            relief="flat",
            cursor="hand2",
            bd=0,
            command=self._toggle_password,
        )
        self._btn_toggle.grid(row=2, column=2, columnspan=2, sticky="e", padx=(0, 10))

        form_label(f, "Rol", 3, 0, 2)
        from tkinter import ttk
        self._combo_rol = ttk.Combobox(
            f,
            textvariable=self._v_rol,
            values=_ROLES,
            state="readonly",
            font=("Segoe UI", 10),
        )
        self._combo_rol.grid(row=4, column=0, columnspan=2, sticky="ew", padx=(0, 10), pady=(2, 6))

        form_label(f, "Firma Password", 3, 2, 2)
        form_entry(f, self._v_firma_password, 4, 2, 2, show="*")

        form_label(f, "Firma", 3, 4, 2)
        form_entry(f, self._v_firma_path, 4, 4, 2)
        tk.Button(
            f,
            text="Seleccionar firma",
            command=self._select_signature,
            bg=COLORS["surface_alt"],
            fg=COLORS["primary"],
            relief="flat",
            cursor="hand2",
            bd=0,
            font=("Segoe UI", 8),
        ).grid(row=5, column=4, columnspan=2, sticky="e", padx=(0, 10), pady=(0, 6))

        perms_box = tk.LabelFrame(
            f,
            text="  Permisos  ",
            bg=COLORS["secondary"],
            fg=COLORS["primary_dark"],
            font=("Segoe UI", 9, "bold"),
        )
        perms_box.grid(row=6, column=0, columnspan=6, sticky="ew", padx=(0, 10), pady=(6, 4))

        perms_box.grid_columnconfigure(0, weight=1)
        perms_box.grid_columnconfigure(1, weight=1)

        mov_box = tk.LabelFrame(
            perms_box,
            text="Movimientos",
            bg=COLORS["secondary"],
            fg=COLORS["primary_dark"],
            font=("Segoe UI", 9, "bold"),
            padx=8,
            pady=6,
        )
        mov_box.grid(row=0, column=0, sticky="nsew", padx=(8, 6), pady=8)

        mae_box = tk.LabelFrame(
            perms_box,
            text="Maestras",
            bg=COLORS["secondary"],
            fg=COLORS["primary_dark"],
            font=("Segoe UI", 9, "bold"),
            padx=8,
            pady=6,
        )
        mae_box.grid(row=0, column=1, sticky="nsew", padx=(6, 8), pady=8)

        for box in (mov_box, mae_box):
            box.grid_columnconfigure(0, weight=1)
            box.grid_columnconfigure(1, weight=1)

        for i, (key, label) in enumerate(_PERMISOS_MOVIMIENTOS):
            tk.Checkbutton(
                mov_box,
                text=label,
                variable=self._perm_vars[key],
                bg=COLORS["secondary"],
                fg=COLORS["text_dark"],
                font=("Segoe UI", 9),
                anchor="w",
                padx=2,
            ).grid(row=i // 2, column=i % 2, sticky="ew", padx=6, pady=3)

        for i, (key, label) in enumerate(_PERMISOS_MAESTRAS):
            tk.Checkbutton(
                mae_box,
                text=label,
                variable=self._perm_vars[key],
                bg=COLORS["secondary"],
                fg=COLORS["text_dark"],
                font=("Segoe UI", 9),
                anchor="w",
                padx=2,
            ).grid(row=i // 2, column=i % 2, sticky="ew", padx=6, pady=3)

        self._lbl_estado = form_estado(f, self._var_estado, 7, 0, 2)

    def _select_signature(self):
        if not self._v_contrasena.get().strip():
            messagebox.showwarning("Aviso", "Ingrese la contrasena del usuario antes de cargar la firma.", parent=self)
            return
        path = filedialog.askopenfilename(
            parent=self,
            title="Seleccione firma",
            filetypes=[("Imagenes", "*.png *.jpg *.jpeg *.bmp *.webp")],
        )
        if not path:
            return
        firmas_dir = Path(resource_path("firmas"))
        firmas_dir.mkdir(parents=True, exist_ok=True)
        src = Path(path)
        dst = firmas_dir / src.name
        shutil.copy2(src, dst)
        self._v_firma_path.set(str(dst))

    def _toggle_password(self):
        visible = not self._show_pass.get()
        self._show_pass.set(visible)
        self._entry_pass.configure(show="" if visible else "*")
        self._btn_toggle.configure(text="Ocultar" if visible else "Mostrar")

    # ── Interface ────────────────────────────────────────

    def _get_form_data(self) -> dict:
        permisos = {k: v.get() for k, v in self._perm_vars.items()}
        permisos["firma_path"] = self._v_firma_path.get().strip()
        permisos["firma_password"] = self._v_firma_password.get().strip()
        return {
            "usuario": self._v_usuario.get().strip(),
            "contrasena": self._v_contrasena.get().strip(),
            "nombre": self._v_nombre.get().strip(),
            "rol": self._v_rol.get().strip(),
            "permisos": permisos,
        }

    def _set_form_data(self, r: dict):
        self._v_usuario.set(r.get("usuario", ""))
        self._v_nombre.set(r.get("nombre", ""))
        self._v_contrasena.set(r.get("contrasena", ""))
        self._v_rol.set(r.get("rol", ""))
        permisos = r.get("permisos", {})
        for k, v in self._perm_vars.items():
            v.set(bool(permisos.get(k, False)))
        self._v_firma_path.set(permisos.get("firma_path", ""))
        self._v_firma_password.set(permisos.get("firma_password", ""))

    def _clear_form(self):
        self._v_usuario.set("")
        self._v_nombre.set("")
        self._v_contrasena.set("")
        self._v_rol.set("")
        self._v_firma_path.set("")
        self._v_firma_password.set("")
        for v in self._perm_vars.values():
            v.set(True)
        self._show_pass.set(False)
        self._entry_pass.configure(show="*")
        self._btn_toggle.configure(text="Mostrar")

    def _list_label(self, r: dict) -> str:
        estado = r.get("estado", "HABILITADA")
        return f"{r.get('usuario', '')} - {r.get('nombre', '')}  ({r.get('rol', '')})  [{estado}]"

    def _validate(self, datos: dict):
        if not datos.get("usuario"):
            return False, "El usuario es obligatorio."
        if not datos.get("nombre"):
            return False, "El nombre completo es obligatorio."
        if not datos.get("contrasena"):
            return False, "La contrasena es obligatoria."
        if not datos.get("rol"):
            return False, "Debe seleccionar un rol."
        return True, ""
