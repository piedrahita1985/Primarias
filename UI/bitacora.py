import tkinter as tk
from tkinter import ttk

from config.config import COLORS
from logica import bitacora_logica as bit
from UI._mov_utils import apply_default_window, attach_treeview_sorting, draw_title, get_date_value, make_date_input


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

        cols = ("fecha_hora", "usuario", "operacion", "accion", "id_registro", "campo", "valor_anterior", "valor_nuevo")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings")
        for key, title, width in [
            ("fecha_hora", "Fecha/Hora", 150),
            ("usuario", "Usuario", 110),
            ("operacion", "Operación", 130),
            ("accion", "Acción", 110),
            ("id_registro", "ID Registro", 95),
            ("campo", "Campo", 160),
            ("valor_anterior", "Valor Anterior", 250),
            ("valor_nuevo", "Valor Nuevo", 250),
        ]:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, anchor="center")
        attach_treeview_sorting(self.tree)

        self.tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        ysb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ysb.set)
        ysb.place(relx=0.995, rely=0.2, relheight=0.74, anchor="ne")

        bottom = tk.Frame(self, bg=COLORS["secondary"])
        bottom.pack(fill="x", padx=10, pady=(0, 10))
        self._button(bottom, "Actualizar", COLORS["primary"], self._load_default).pack(side="right", padx=(6, 0))
        self._button(bottom, "Salir", "#6C757D", self.destroy).pack(side="right")

    def _button(self, parent, text, bg, cmd):
        return tk.Button(parent, text=text, bg=bg, fg="white", font=("Segoe UI", 9, "bold"), relief="flat", bd=0, padx=10, pady=5, cursor="hand2", command=cmd)

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

    def _fill(self, rows):
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            operacion, accion = self._split_tipo_operacion(r.get("tipo_operacion", ""))
            self.tree.insert(
                "",
                "end",
                values=(
                    r.get("fecha_hora", ""),
                    r.get("usuario", ""),
                    operacion,
                    accion,
                    r.get("id_registro", ""),
                    r.get("campo", ""),
                    r.get("valor_anterior", ""),
                    r.get("valor_nuevo", ""),
                ),
            )

    def _load_default(self):
        self._fill(bit.ultimos_200())

    def _apply_filters(self):
        rows = bit.filtrar(
            desde=get_date_value(self.w_desde) if self._desde_habilitada else "",
            hasta=get_date_value(self.w_hasta) if self._hasta_habilitada else "",
            usuario=self.v_usuario.get().strip(),
            tipo_operacion=self.v_tipo_operacion.get().strip(),
            id_registro=self.v_id_registro.get().strip(),
        )
        self._fill(rows)

    def _clear_filters(self):
        self._clear_date("desde")
        self._clear_date("hasta")
        self.v_usuario.set("")
        self.v_tipo_operacion.set("")
        self.v_id_registro.set("")
        self._load_default()
