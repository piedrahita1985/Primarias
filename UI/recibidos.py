import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from config.config import COLORS
from logica import movimientos_common as common
from logica import prestamos_logica as prest
from UI._mov_utils import attach_treeview_sorting, apply_default_window, draw_title


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
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_rowconfigure(1, weight=1)

        self._build_pendientes_recibir(wrap)
        self._build_pendientes_devolver(wrap)

        bottom = tk.Frame(self, bg=COLORS["secondary"])
        bottom.pack(side="bottom", fill="x", padx=10, pady=(0, 10))
        self._button(bottom, "Salir", "#6C757D", self.destroy).pack(side="right")

    def _build_pendientes_recibir(self, parent):
        sec = tk.LabelFrame(
            parent,
            text="  Pendientes por recibir  ",
            bg=COLORS["secondary"],
            fg=COLORS["text_dark"],
            font=("Segoe UI", 10, "bold"),
            padx=8,
            pady=8,
        )
        sec.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        sec.grid_rowconfigure(0, weight=1)
        sec.grid_columnconfigure(0, weight=1)

        cols = ("id", "fecha", "codigo", "nombre", "lote", "cantidad", "unidad", "prestador")
        self.tree_recibir = ttk.Treeview(sec, columns=cols, show="headings", height=10)
        self.tree_recibir.grid(row=0, column=0, sticky="nsew")
        for key, title, width in [
            ("id", "ID", 55),
            ("fecha", "Fecha", 110),
            ("codigo", "Código", 70),
            ("nombre", "Nombre", 240),
            ("lote", "Lote", 110),
            ("cantidad", "Cantidad", 90),
            ("unidad", "Unidad", 90),
            ("prestador", "Prestador", 180),
        ]:
            self.tree_recibir.heading(key, text=title)
            self.tree_recibir.column(key, width=width, anchor="center")
        attach_treeview_sorting(self.tree_recibir)

        ysb = ttk.Scrollbar(sec, orient="vertical", command=self.tree_recibir.yview)
        self.tree_recibir.configure(yscrollcommand=ysb.set)
        ysb.grid(row=0, column=1, sticky="ns")

        bar = tk.Frame(sec, bg=COLORS["secondary"])
        bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self._button(bar, "Aceptar", COLORS["success"], lambda: self._responder(True)).pack(side="left", padx=(0, 6))
        self._button(bar, "Rechazar", COLORS["error"], lambda: self._responder(False)).pack(side="left")
        self._button(bar, "Actualizar", "#6C757D", self._refresh_all).pack(side="right")

    def _build_pendientes_devolver(self, parent):
        sec = tk.LabelFrame(
            parent,
            text="  Pendientes por devolver  ",
            bg=COLORS["secondary"],
            fg=COLORS["text_dark"],
            font=("Segoe UI", 10, "bold"),
            padx=8,
            pady=8,
        )
        sec.grid(row=1, column=0, sticky="nsew")
        sec.grid_rowconfigure(0, weight=1)
        sec.grid_columnconfigure(0, weight=1)

        cols = ("id", "fecha", "codigo", "nombre", "lote", "cantidad", "unidad", "prestador")
        self.tree_devolver = ttk.Treeview(sec, columns=cols, show="headings", height=10)
        self.tree_devolver.grid(row=0, column=0, sticky="nsew")
        for key, title, width in [
            ("id", "ID", 55),
            ("fecha", "Fecha recibido", 130),
            ("codigo", "Código", 70),
            ("nombre", "Nombre", 240),
            ("lote", "Lote", 110),
            ("cantidad", "Cantidad", 90),
            ("unidad", "Unidad", 90),
            ("prestador", "Prestador", 180),
        ]:
            self.tree_devolver.heading(key, text=title)
            self.tree_devolver.column(key, width=width, anchor="center")
        attach_treeview_sorting(self.tree_devolver)

        ysb = ttk.Scrollbar(sec, orient="vertical", command=self.tree_devolver.yview)
        self.tree_devolver.configure(yscrollcommand=ysb.set)
        ysb.grid(row=0, column=1, sticky="ns")

        bar = tk.Frame(sec, bg=COLORS["secondary"])
        bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        self._button(bar, "Registrar devolución", COLORS["primary"], self._devolver).pack(side="left")
        self._button(bar, "Actualizar", "#6C757D", self._refresh_all).pack(side="right")

    def _button(self, parent, text, bg, cmd):
        return tk.Button(parent, text=text, command=cmd, bg=bg, fg="white", font=("Segoe UI", 10, "bold"), relief="flat", bd=0, cursor="hand2", padx=12, pady=6)

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
        self._refresh_recibir()
        self._refresh_devolver()

    def _refresh_recibir(self):
        self.tree_recibir.delete(*self.tree_recibir.get_children())
        my_id = self._user.get("id")
        if not my_id:
            return
        rows = prest.recibidos_pendientes_para_usuario(my_id, self._maestras)
        for row in rows:
            self.tree_recibir.insert(
                "",
                "end",
                values=(
                    row.get("id_prestamo"),
                    row.get("fecha_recepcion") or row.get("fecha_prestamo", ""),
                    row.get("codigo", ""),
                    row.get("nombre", ""),
                    row.get("lote", ""),
                    row.get("cantidad", ""),
                    row.get("unidad", ""),
                    row.get("usuario_presta_nombre", ""),
                ),
            )

    def _refresh_devolver(self):
        self.tree_devolver.delete(*self.tree_devolver.get_children())
        my_id = self._user.get("id")
        if not my_id:
            return
        rows = prest.devoluciones_pendientes_para_usuario(my_id, self._maestras)
        for row in rows:
            self.tree_devolver.insert(
                "",
                "end",
                values=(
                    row.get("id_prestamo"),
                    row.get("fecha_recepcion", ""),
                    row.get("codigo", ""),
                    row.get("nombre", ""),
                    row.get("lote", ""),
                    row.get("cantidad", ""),
                    row.get("unidad", ""),
                    row.get("usuario_presta_nombre", ""),
                ),
            )

    def _selected_prestamo_id(self, tree):
        sel = tree.selection()
        if not sel:
            return None
        values = tree.item(sel[0], "values")
        if not values:
            return None
        try:
            return int(values[0])
        except (TypeError, ValueError):
            return None

    def _responder(self, aceptar):
        id_prestamo = self._selected_prestamo_id(self.tree_recibir)
        if id_prestamo is None:
            messagebox.showwarning("Aviso", "Seleccione un préstamo pendiente por recibir.", parent=self)
            return

        titulo = "Aceptar recibido" if aceptar else "Rechazar recibido"
        prompt = "Observación de recibido (opcional):" if aceptar else "Motivo del rechazo (opcional):"
        mensaje = "¿Desea procesar el préstamo seleccionado?"
        if not messagebox.askyesno(titulo, mensaje, parent=self):
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
            messagebox.showinfo("Recibidos", msg, parent=self)
            self._refresh_all()
        else:
            messagebox.showwarning("Recibidos", msg, parent=self)

    def _devolver(self):
        id_prestamo = self._selected_prestamo_id(self.tree_devolver)
        if id_prestamo is None:
            messagebox.showwarning("Aviso", "Seleccione un préstamo pendiente por devolver.", parent=self)
            return

        if not messagebox.askyesno("Registrar devolución", "¿Desea registrar la devolución del préstamo seleccionado?", parent=self):
            return

        if not self._ask_firma_password_current_user():
            return

        obs = simpledialog.askstring("Registrar devolución", "Observación de devolución (opcional):", parent=self)
        ok, msg = prest.devolver_prestamo(
            id_prestamo=id_prestamo,
            id_usuario_devuelve=self._user.get("id"),
            observacion_devolucion=obs or "",
            usuario_accion=self._user.get("usuario") or self._user.get("nombre", "SISTEMA"),
        )
        if ok:
            messagebox.showinfo("Recibidos", msg, parent=self)
            self._refresh_all()
        else:
            messagebox.showwarning("Recibidos", msg, parent=self)