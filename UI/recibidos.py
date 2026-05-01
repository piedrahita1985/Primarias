import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from config.config import COLORS
from logica import movimientos_common as common
from logica import prestamos_logica as prest
from UI._mov_utils import attach_treeview_sorting, apply_default_window, draw_title


FILTROS = ["Todos", "Pendientes por recibir", "Pendientes devolver"]


def open_window(master):
    RecibidosWindow(master)


class RecibidosWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Sistema de Gestion - Recibidos")
        self.configure(bg=COLORS["secondary"])
        apply_default_window(self, min_width=1120, min_height=720)

        self._maestras = common.cargar_maestras()
        self._users = prest.usuarios_habilitados()
        self._user = self._resolve_current_user(master)
        self.v_filtro = tk.StringVar(value="Todos")
        self._row_meta = {}

        self._build_ui()
        self._refresh_all()

    def _resolve_current_user(self, master):
        user = getattr(master, "user_record", None)
        if isinstance(user, dict) and user.get("id"):
            return user

        username = str(getattr(master, "username", "")).strip()
        for row in self._users:
            if row.get("usuario") == username or row.get("nombre") == username:
                return row
        return {}

    def _build_ui(self):
        draw_title(self, "Sistema de Gestion - Recibidos")

        wrap = tk.Frame(self, bg=COLORS["secondary"])
        wrap.pack(fill="both", expand=True, padx=10, pady=10)
        wrap.grid_rowconfigure(1, weight=1)
        wrap.grid_columnconfigure(0, weight=1)

        top = tk.LabelFrame(
            wrap,
            text="  Pendientes del usuario  ",
            bg=COLORS["secondary"],
            fg=COLORS["text_dark"],
            font=("Segoe UI", 10, "bold"),
            padx=8,
            pady=8,
        )
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        tk.Label(top, text="Mostrar:", bg=COLORS["secondary"], fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
        cb = ttk.Combobox(top, textvariable=self.v_filtro, values=FILTROS, state="readonly", width=24, font=("Segoe UI", 10))
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda _e: self._refresh_all())

        tk.Label(top, text="Las filas vencidas se muestran en rojo.", bg=COLORS["secondary"], fg=COLORS["text_muted"], font=("Segoe UI", 9, "italic")).pack(side="left", padx=(16, 0))

        table_wrap = tk.Frame(wrap, bg=COLORS["secondary"])
        table_wrap.grid(row=1, column=0, sticky="nsew")
        table_wrap.grid_rowconfigure(0, weight=1)
        table_wrap.grid_columnconfigure(0, weight=1)

        cols = ("id", "fecha", "codigo", "nombre", "lote", "cantidad", "unidad", "prestador", "fecha_limite")
        self.tree = ttk.Treeview(table_wrap, columns=cols, show="headings", height=16)
        self.tree.grid(row=0, column=0, sticky="nsew")
        for key, title, width in [
            ("id", "ID", 55),
            ("fecha", "Fecha", 120),
            ("codigo", "Código", 75),
            ("nombre", "Nombre", 260),
            ("lote", "Lote", 110),
            ("cantidad", "Cantidad", 90),
            ("unidad", "Unidad", 90),
            ("prestador", "Prestador", 180),
            ("fecha_limite", "Fecha límite", 120),
        ]:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="center")
        attach_treeview_sorting(self.tree)
        self.tree.tag_configure("vencido", background="#FFD6D6", foreground="#8B0000")

        ysb = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ysb.set)
        ysb.grid(row=0, column=1, sticky="ns")

        bar = tk.Frame(wrap, bg=COLORS["secondary"])
        bar.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self._button(bar, "Aceptar", COLORS["success"], lambda: self._responder(True)).pack(side="left", padx=(0, 6))
        self._button(bar, "Rechazar", COLORS["error"], lambda: self._responder(False)).pack(side="left", padx=(0, 6))
        self._button(bar, "Registrar devolución", COLORS["primary"], self._devolver).pack(side="left")
        self._button(bar, "Actualizar", "#6C757D", self._refresh_all).pack(side="right")

        bottom = tk.Frame(self, bg=COLORS["secondary"])
        bottom.pack(side="bottom", fill="x", padx=10, pady=(0, 10))
        self._button(bottom, "Salir", "#6C757D", self.destroy).pack(side="right")

    def _button(self, parent, text, bg, cmd):
        return tk.Button(
            parent,
            text=text,
            command=cmd,
            bg=bg,
            fg="white",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            bd=0,
            cursor="hand2",
            padx=12,
            pady=6,
        )

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

    def _refresh_all(self):
        self._maestras = common.cargar_maestras()
        self._users = prest.usuarios_habilitados()
        self._user = self._resolve_current_user(self.master) or self._user

        self.tree.delete(*self.tree.get_children())
        self._row_meta.clear()

        my_id = self._user.get("id")
        if not my_id:
            return

        filtro = self.v_filtro.get().strip() or "Todos"
        rows = []
        if filtro in {"Todos", "Pendientes por recibir"}:
            for row in prest.recibidos_pendientes_para_usuario(my_id, self._maestras):
                rows.append({**row, "_tipo_fila": "recibir"})
        if filtro in {"Todos", "Pendientes devolver"}:
            for row in prest.devoluciones_pendientes_para_usuario(my_id, self._maestras):
                rows.append({**row, "_tipo_fila": "devolver"})

        rows.sort(key=lambda row: (str(row.get("fecha_limite") or "9999-99-99"), -(int(row.get("id") or 0))))

        today = __import__("datetime").date.today().isoformat()
        for row in rows:
            fecha_limite = str(row.get("fecha_limite") or "").strip()
            item_id = self.tree.insert(
                "",
                "end",
                values=(
                    row.get("id_prestamo") or row.get("id"),
                    row.get("fecha_recepcion") or row.get("fecha_prestamo", ""),
                    row.get("codigo", ""),
                    row.get("nombre", ""),
                    row.get("lote", ""),
                    row.get("cantidad", ""),
                    row.get("unidad", ""),
                    row.get("usuario_presta_nombre", ""),
                    fecha_limite,
                ),
                tags=("vencido",) if fecha_limite and fecha_limite < today else (),
            )
            self._row_meta[item_id] = row

    def _selected_row(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self._row_meta.get(sel[0])

    def _responder(self, aceptar):
        row = self._selected_row()
        if row is None:
            messagebox.showwarning("Aviso", "Seleccione un préstamo pendiente.", parent=self)
            return
        if row.get("_tipo_fila") != "recibir":
            messagebox.showwarning("Aviso", "La fila seleccionada corresponde a una devolución pendiente.", parent=self)
            return

        titulo = "Aceptar recibido" if aceptar else "Rechazar recibido"
        prompt = "Observación de recibido (opcional):" if aceptar else "Motivo del rechazo (opcional):"
        if not messagebox.askyesno(titulo, "¿Desea procesar el préstamo seleccionado?", parent=self):
            return

        if not self._ask_firma_password_current_user():
            return

        obs = simpledialog.askstring(titulo, prompt, parent=self)
        ok, msg = prest.responder_prestamo(
            id_prestamo=row.get("id_prestamo") or row.get("id"),
            id_usuario_recibe=self._user.get("id"),
            aceptar=aceptar,
            observacion_recibo=obs or "",
            usuario_accion=self._user.get("usuario") or self._user.get("nombre", "SISTEMA"),
        )
        if ok:
            messagebox.showinfo("Recibidos", msg, parent=self)
            self._refresh_all()
        else:
            messagebox.showwarning("Recibidos", msg, parent=self)

    def _devolver(self):
        row = self._selected_row()
        if row is None:
            messagebox.showwarning("Aviso", "Seleccione un préstamo pendiente.", parent=self)
            return
        if row.get("_tipo_fila") != "devolver":
            messagebox.showwarning("Aviso", "La fila seleccionada todavía está pendiente por recibir.", parent=self)
            return

        if not messagebox.askyesno("Registrar devolución", "¿Desea registrar la devolución del préstamo seleccionado?", parent=self):
            return

        if not self._ask_firma_password_current_user():
            return

        obs = simpledialog.askstring("Registrar devolución", "Observación de devolución (opcional):", parent=self)
        ok, msg = prest.devolver_prestamo(
            id_prestamo=row.get("id_prestamo") or row.get("id"),
            id_usuario_devuelve=self._user.get("id"),
            observacion_devolucion=obs or "",
            usuario_accion=self._user.get("usuario") or self._user.get("nombre", "SISTEMA"),
        )
        if ok:
            messagebox.showinfo("Recibidos", msg, parent=self)
            self._refresh_all()
        else:
            messagebox.showwarning("Recibidos", msg, parent=self)