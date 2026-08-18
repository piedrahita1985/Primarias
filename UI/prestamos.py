"""UI/prestamos.py
Control y Seguimiento de Sustancias de Referencia Primarias (CECIF LE-FC009/04).

Flujo de estados:
    SOLICITADO  ->  PRESTADO  ->  DEVUELTO (historial)
"""
import os
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from pathlib import Path

from PIL import Image, ImageTk

from app_paths import writable_base_path
from config.config import COLORS
from logica import movimientos_common as common
from logica import prestamos_logica as prest
from logica import salidas_mov_logica as sal
from logica import usuarios_logica as usr
from UI._mov_utils import (
    apply_default_window,
    attach_treeview_sorting,
    draw_title,
    get_date_value,
    make_date_widget,
)
from UI._searchable_treeview import SearchableTreeview


def open_window(master):
    PrestamosWindow(master)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _resolve_firma_path(path_value):
    raw = str(path_value or "").strip()
    if not raw:
        return None
    p = Path(raw)
    candidates = [p]
    if not p.is_absolute():
        base = writable_base_path()
        candidates.append(base / p)
        candidates.append(base / raw.replace("\\", "/"))
    for c in candidates:
        try:
            if c.is_file():
                return str(c)
        except Exception:
            continue
    return None


def _btn(parent, text, bg, cmd, **kw):
    return tk.Button(
        parent, text=text, command=cmd,
        bg=bg, fg="white", font=("Segoe UI", 10, "bold"),
        relief="flat", bd=0, cursor="hand2", padx=12, pady=6,
        **kw,
    )


def _lbl(parent, text, bold=False, muted=False, **kw):
    font = ("Segoe UI", 9, "bold") if bold else ("Segoe UI", 9)
    fg = COLORS["text_muted"] if muted else COLORS["text_dark"]
    return tk.Label(parent, text=text, bg=COLORS["secondary"], fg=fg, font=font, **kw)


def _entry_ro(parent, textvariable, width=None, **kw):
    opts = dict(
        textvariable=textvariable, state="readonly",
        readonlybackground=COLORS["surface"], fg=COLORS["text_dark"],
        font=("Segoe UI", 10), relief="flat", bd=0,
        highlightthickness=1,
        highlightbackground=COLORS["border_soft"],
        highlightcolor=COLORS["primary"],
    )
    if width:
        opts["width"] = width
    opts.update(kw)
    return tk.Entry(parent, **opts)


def _entry_rw(parent, textvariable, width=None, **kw):
    opts = dict(
        textvariable=textvariable,
        bg=COLORS["surface"], fg=COLORS["text_dark"],
        font=("Segoe UI", 10), relief="flat", bd=0,
        highlightthickness=1,
        highlightbackground=COLORS["border_soft"],
        highlightcolor=COLORS["primary"],
    )
    if width:
        opts["width"] = width
    opts.update(kw)
    return tk.Entry(parent, **opts)


# ─────────────────────────────────────────────────────────────────────────────
# FirmaBox: shows a user combo + signature image for signing
# ─────────────────────────────────────────────────────────────────────────────

class FirmaBox(tk.Frame):
    """Selector de firma reutilizable (semejante al de check_cecif)."""

    def __init__(self, parent, label, usuarios, bg=None, read_only=False,
                 solo_rol=None, excluir_rol=None, **kw):
        bg = bg or COLORS["surface"]
        super().__init__(parent, bg=bg, highlightthickness=1,
                         highlightbackground=COLORS["border_soft"], **kw)
        self._usuarios = usuarios
        self._selected_id = None
        self._firma_img = None
        self._read_only = read_only
        self._solo_rol = solo_rol.lower() if solo_rol else None
        self._excluir_rol = excluir_rol.lower() if excluir_rol else None
        self.bg = bg

        tk.Label(self, text=label, bg=bg, fg=COLORS["text_dark"],
                 font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=8, pady=(8, 2))

        if not read_only:
            self.var = tk.StringVar()
            self.combo = ttk.Combobox(self, textvariable=self.var, state="readonly",
                                      font=("Segoe UI", 10))
            self.combo.pack(fill="x", padx=8, pady=(0, 4))
            self.combo.bind("<<ComboboxSelected>>", self._on_select)
            self._refresh()

        self.lbl_firma = tk.Label(self, bg=bg, relief="flat",
                                  highlightthickness=0, pady=4,
                                  text="(Sin firma)", fg=COLORS["text_muted"],
                                  font=("Segoe UI", 9, "italic"))
        self.lbl_firma.pack(padx=8, pady=(0, 8))

    def _refresh(self):
        nombres = []
        for u in self._usuarios:
            if u.get("estado") != "HABILITADA":
                continue
            if not u.get("permisos", {}).get("firma_path", ""):
                continue
            rol = str(u.get("rol") or "").lower().strip()
            if self._solo_rol and rol != self._solo_rol:
                continue
            if self._excluir_rol and rol == self._excluir_rol:
                continue
            nombres.append(u["nombre"])
        self.combo.configure(values=nombres)

    def _on_select(self, _=None):
        # Clear any path override from DB – user is making an interactive selection
        self._path_override = None
        nombre = self.var.get()
        user = next((u for u in self._usuarios if u["nombre"] == nombre), None)
        if user and self._validate_pwd(user):
            self._selected_id = user["id"]
            self._load_firma(user.get("permisos", {}).get("firma_path", ""))
        else:
            self._selected_id = None
            self.var.set("")
            self._clear_firma()

    def _validate_pwd(self, user):
        pwd = str(user.get("permisos", {}).get("firma_password", "") or "").strip()
        if not pwd:
            messagebox.showwarning("Firma",
                "El usuario no tiene contraseña de firma configurada.",
                parent=self.winfo_toplevel())
            return False
        ingresada = simpledialog.askstring(
            "Validar firma",
            f"Contraseña de firma de {user.get('nombre', '')}:",
            show="*", parent=self.winfo_toplevel(),
        )
        if ingresada is None:
            return False
        if not usr.verificar_firma_password(user, str(ingresada).strip()):
            messagebox.showerror("Firma", "Contraseña incorrecta.",
                                 parent=self.winfo_toplevel())
            return False
        return True

    def _load_firma(self, path):
        self._clear_firma()
        resolved = _resolve_firma_path(path)
        if not resolved:
            self.lbl_firma.configure(image="", text="(Sin firma)",
                                     fg=COLORS["text_muted"],
                                     font=("Segoe UI", 9, "italic"))
            return
        try:
            img = Image.open(resolved)
            img.thumbnail((380, 110), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            self._firma_img = photo
            self.lbl_firma.configure(image=photo, text="",
                                     width=photo.width(), height=photo.height())
        except Exception:
            self.lbl_firma.configure(image="", text="Error al cargar firma",
                                     fg=COLORS["error"], font=("Segoe UI", 9))

    def _clear_firma(self):
        self._firma_img = None
        self.lbl_firma.configure(image="", text="(Sin firma)",
                                 fg=COLORS["text_muted"],
                                 font=("Segoe UI", 9, "italic"))

    def set_from_path(self, user_id, user_nombre, firma_path):
        """Carga firma desde BD (modo lectura o ya firmado). Guarda la ruta original."""
        self._selected_id = user_id
        self._path_override = firma_path or ""  # preserve exact path stored in DB
        if not self._read_only and hasattr(self, "var"):
            self.var.set(user_nombre or "")
        self._load_firma(firma_path)

    def get_id(self):
        return self._selected_id

    def get_path(self):
        # If loaded from DB via set_from_path, return the stored path directly
        if getattr(self, "_path_override", None):
            return self._path_override
        if self._selected_id is None:
            return ""
        user = next((u for u in self._usuarios
                     if u.get("id") == self._selected_id), None)
        if user:
            return user.get("permisos", {}).get("firma_path", "")
        return ""


# ─────────────────────────────────────────────────────────────────────────────
# Detail/Edit window
# ─────────────────────────────────────────────────────────────────────────────

class PrestamoDetalleWindow(tk.Toplevel):
    """Ventana de detalle para un préstamo (nueva solicitud o existente)."""

    ESTADO_COLOR = {
        "SOLICITADO": "#F0A500",
        "PRESTADO":   "#2196F3",
        "DEVUELTO":   "#4CAF50",
    }

    def __init__(self, master, prestamo: dict, usuarios: list,
                 current_user: dict, on_saved=None):
        super().__init__(master)
        self._prestamo = dict(prestamo)
        self._usuarios = usuarios
        self._user = current_user
        self._on_saved = on_saved
        self._build()

    def _build(self):
        estado = str(self._prestamo.get("estado", "SOLICITADO")).upper()
        self.title(f"Detalle de Préstamo  –  {estado}")
        self.configure(bg=COLORS["secondary"])
        self.resizable(True, True)
        self.grab_set()

        canvas = tk.Canvas(self, bg=COLORS["secondary"], highlightthickness=0)
        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(canvas, bg=COLORS["secondary"])
        win_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_resize(e):
            canvas.itemconfig(win_id, width=e.width)
        canvas.bind("<Configure>", _on_resize)

        def _on_frame_configure(_):
            canvas.configure(scrollregion=canvas.bbox("all"))
        inner.bind("<Configure>", _on_frame_configure)

        # ── Header (estándar info) ──
        self._build_header(inner)
        # ── Detail section ──
        self._build_detail(inner)
        # ── Buttons ──
        self._build_buttons(inner)

        self.minsize(760, 560)
        self.update_idletasks()
        w, h = min(900, self.winfo_screenwidth() - 40), min(700, self.winfo_screenheight() - 80)
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_header(self, parent):
        estado = str(self._prestamo.get("estado", "SOLICITADO")).upper()
        est_color = self.ESTADO_COLOR.get(estado, COLORS["primary"])

        hdr = tk.Frame(parent, bg=COLORS["secondary"])
        hdr.pack(fill="x", padx=16, pady=(12, 0))

        tk.Label(hdr, text="Control y Seguimiento de Sustancias de Referencia Primarias",
                 bg=COLORS["secondary"], fg=COLORS["primary"],
                 font=("Segoe UI", 12, "bold")).pack(side="left")
        tk.Label(hdr, text=f"  [{estado}]", bg=COLORS["secondary"],
                 fg=est_color, font=("Segoe UI", 11, "bold")).pack(side="left")

        card = tk.LabelFrame(parent, text="  Información del Estándar  ",
                             bg=COLORS["secondary"], fg=COLORS["text_dark"],
                             font=("Segoe UI", 10, "bold"), padx=8, pady=8)
        card.pack(fill="x", padx=16, pady=(8, 0))
        for c in range(5):
            card.grid_columnconfigure(c, weight=1)

        p = self._prestamo
        fields = [
            ("Código Interno",    p.get("codigo", "")),
            ("Nombre del Estándar", p.get("nombre", "")),
            ("Lote",              p.get("lote", "")),
            ("Fecha Vencimiento", p.get("fecha_vencimiento", "")),
            ("Pureza / Potencia", p.get("potencia", "")),
            ("Propiedad",         p.get("propiedad", "")),
            ("Fabricante",        p.get("fabricante_nombre", "")),
            ("Ubicación",         p.get("ubicacion", "")),
            ("No. Caja",          p.get("no_caja", "")),
            ("Cantidad Prestada", f"{p.get('cantidad', '')} {p.get('unidad', '')}"),
        ]
        for idx, (lbl, val) in enumerate(fields):
            row, col = divmod(idx, 5)
            tk.Label(card, text=lbl, bg=COLORS["secondary"], fg=COLORS["text_muted"],
                     font=("Segoe UI", 8)).grid(row=row*2, column=col, sticky="w",
                                                 padx=6, pady=(4, 0))
            tk.Label(card, text=val or "–", bg=COLORS["surface"], fg=COLORS["text_dark"],
                     font=("Segoe UI", 9, "bold"), relief="flat",
                     anchor="w", padx=4).grid(row=row*2+1, column=col,
                                               sticky="ew", padx=6, pady=(0, 6))

    def _build_detail(self, parent):
        estado = str(self._prestamo.get("estado", "SOLICITADO")).upper()
        p = self._prestamo

        det = tk.LabelFrame(parent, text="  Detalle de Uso  ",
                            bg=COLORS["secondary"], fg=COLORS["text_dark"],
                            font=("Segoe UI", 10, "bold"), padx=8, pady=8)
        det.pack(fill="x", padx=16, pady=8)

        # ── Row 0: Entregado por ──────────────────────────────────────────
        frm_e = tk.Frame(det, bg=COLORS["secondary"])
        frm_e.pack(fill="x", pady=(0, 6))
        tk.Label(frm_e, text="Entregado por", bg=COLORS["secondary"],
                 fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 8))
        already_signed = bool(p.get("firma_entregado_por"))
        self._firma_entrega = FirmaBox(
            det, "Firma – Entregado por",
            self._usuarios, bg=COLORS["secondary"],
            read_only=(estado != "SOLICITADO"),
            excluir_rol="analista",
        )
        self._firma_entrega.pack(fill="x", pady=(0, 8))
        if already_signed:
            self._firma_entrega.set_from_path(
                p.get("id_usuario_entregador"),
                p.get("usuario_entregador_nombre", ""),
                p.get("firma_entregado_por", ""),
            )

        # ── Row 1: Fecha ensayo / No Control / Análisis ───────────────────
        row1 = tk.Frame(det, bg=COLORS["secondary"])
        row1.pack(fill="x", pady=(0, 6))
        row1.grid_columnconfigure(0, weight=1)
        row1.grid_columnconfigure(1, weight=1)
        row1.grid_columnconfigure(2, weight=2)

        rw = (estado == "PRESTADO")

        tk.Label(row1, text="Fecha de Ensayo", bg=COLORS["secondary"],
                 fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold")).grid(
                     row=0, column=0, sticky="w", padx=6)
        self.w_fecha_ensayo = make_date_widget(row1)
        self.w_fecha_ensayo.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 6))
        if p.get("fecha_ensayo"):
            try:
                self.w_fecha_ensayo.delete(0, "end")
                self.w_fecha_ensayo.insert(0, p.get("fecha_ensayo"))
            except Exception:
                pass

        tk.Label(row1, text="No. Control o Actividad", bg=COLORS["secondary"],
                 fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold")).grid(
                     row=0, column=1, sticky="w", padx=6)
        self.v_no_control = tk.StringVar(value=p.get("no_control_actividad", ""))
        e_no_control = _entry_rw(row1, self.v_no_control) if rw else _entry_ro(row1, self.v_no_control)
        e_no_control.grid(row=1, column=1, sticky="ew", padx=6, pady=(0, 6))

        tk.Label(row1, text="Análisis Realizado", bg=COLORS["secondary"],
                 fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold")).grid(
                     row=0, column=2, sticky="w", padx=6)
        self.v_analisis = tk.StringVar(value=p.get("analisis_realizado", ""))
        e_analisis = _entry_rw(row1, self.v_analisis) if rw else _entry_ro(row1, self.v_analisis)
        e_analisis.grid(row=1, column=2, sticky="ew", padx=6, pady=(0, 6))

        # ── Row 2: Cantidad consumida (unidad dinámica) ───────────────────
        unidad = str(p.get("unidad") or "unid")
        cantidad_prestada = p.get("cantidad", "")

        row2 = tk.Frame(det, bg=COLORS["secondary"])
        row2.pack(fill="x", pady=(0, 6))

        tk.Label(row2, text=f"Cantidad consumida ({unidad})",
                 bg=COLORS["secondary"], fg=COLORS["text_dark"],
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
        self.v_cantidad_mg = tk.StringVar(value=str(p.get("cantidad_mg", "") or ""))
        e_mg = _entry_rw(row2, self.v_cantidad_mg, width=14) if rw else _entry_ro(row2, self.v_cantidad_mg, width=14)
        e_mg.pack(side="left", padx=(0, 4))
        tk.Label(row2, text=f"  (de {cantidad_prestada} {unidad} prestados – el resto vuelve al stock)",
                 bg=COLORS["secondary"], fg=COLORS["text_muted"],
                 font=("Segoe UI", 8, "italic")).pack(side="left")

        # ── Row 3: Analista Responsable ────────────────────────────────────
        self._firma_analista = FirmaBox(
            det, "Firma – Analista Responsable",
            self._usuarios, bg=COLORS["secondary"],
            read_only=(estado != "PRESTADO"),
            solo_rol="analista",
        )
        self._firma_analista.pack(fill="x", pady=(0, 8))
        if p.get("firma_analista"):
            self._firma_analista.set_from_path(
                p.get("id_usuario_analista"),
                p.get("usuario_analista_nombre", ""),
                p.get("firma_analista", ""),
            )

        # ── Row 4: Fecha Devolución / Verificado ──────────────────────────
        row4 = tk.Frame(det, bg=COLORS["secondary"])
        row4.pack(fill="x", pady=(0, 6))

        tk.Label(row4, text="Fecha de Devolución", bg=COLORS["secondary"],
                 fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 6))
        self.w_fecha_dev = make_date_widget(row4)
        self.w_fecha_dev.pack(side="left", padx=(0, 20))
        if p.get("fecha_devolucion"):
            try:
                self.w_fecha_dev.delete(0, "end")
                self.w_fecha_dev.insert(0, p.get("fecha_devolucion"))
            except Exception:
                pass
        if estado != "PRESTADO":
            self.w_fecha_dev.configure(state="readonly" if hasattr(self.w_fecha_dev, "configure") else "disabled")

        self._firma_verificado = FirmaBox(
            det, "Firma – Verificado el Recibido",
            self._usuarios, bg=COLORS["secondary"],
            read_only=(estado != "PRESTADO"),
            excluir_rol="analista",
        )
        self._firma_verificado.pack(fill="x", pady=(0, 8))
        if p.get("firma_verificador"):
            self._firma_verificado.set_from_path(
                p.get("id_usuario_verificador"),
                p.get("usuario_verificador_nombre", ""),
                p.get("firma_verificador", ""),
            )

        # ── Row 5: Observaciones ──────────────────────────────────────────
        tk.Label(det, text="Observaciones", bg=COLORS["secondary"],
                 fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold")).pack(
                     anchor="w", pady=(4, 2))
        obs_bg = COLORS["surface"] if rw else COLORS["secondary"]
        self.txt_obs = tk.Text(det, height=3, bg=obs_bg, fg=COLORS["text_dark"],
                               font=("Segoe UI", 10), relief="flat", bd=0,
                               highlightthickness=1,
                               highlightbackground=COLORS["border_soft"],
                               highlightcolor=COLORS["primary"])
        if not rw:
            self.txt_obs.configure(state="disabled")
        self.txt_obs.pack(fill="x", pady=(0, 6))
        if p.get("observaciones_prestamo"):
            self.txt_obs.configure(state="normal")
            self.txt_obs.insert("1.0", p.get("observaciones_prestamo", ""))
            if not rw:
                self.txt_obs.configure(state="disabled")

    def _build_buttons(self, parent):
        estado = str(self._prestamo.get("estado", "SOLICITADO")).upper()

        bar = tk.Frame(parent, bg=COLORS["secondary"])
        bar.pack(fill="x", padx=16, pady=(4, 14))

        _btn(bar, "Cerrar", "#6C757D", self.destroy).pack(side="right", padx=(6, 0))

        if estado == "SOLICITADO":
            _btn(bar, "Registrar Entrega", COLORS["primary"],
                 self._save_entrega).pack(side="right", padx=(6, 0))

        if estado == "PRESTADO":
            _btn(bar, "Guardar Detalle", COLORS["primary_dark"],
                 self._save_detalle).pack(side="right", padx=(6, 0))
            _btn(bar, "Registrar Devolución", COLORS["success"],
                 self._save_devolucion).pack(side="right", padx=(6, 0))

    # ── Actions ──────────────────────────────────────────────────────────────

    def _save_entrega(self):
        id_entregador = self._firma_entrega.get_id()
        if id_entregador is None:
            messagebox.showwarning("Aviso",
                "Seleccione la firma de quien entrega el estándar.", parent=self)
            return
        if not messagebox.askyesno(
            "Confirmar entrega",
            "¿Desea registrar la entrega del estándar con la firma seleccionada?",
            parent=self,
        ):
            return
        firma_path = self._firma_entrega.get_path()
        ok, msg = prest.firmar_entrega(
            id_prestamo=self._prestamo["id"],
            id_usuario_entregador=id_entregador,
            firma_path=firma_path,
            usuario_accion=self._user.get("usuario") or self._user.get("nombre", "SISTEMA"),
        )
        if ok:
            messagebox.showinfo("Préstamos", msg, parent=self)
            if self._on_saved:
                self._on_saved()
            self.destroy()
        else:
            messagebox.showwarning("Préstamos", msg, parent=self)

    def _save_detalle(self):
        datos = {
            "fecha_ensayo":        get_date_value(self.w_fecha_ensayo),
            "no_control_actividad": self.v_no_control.get().strip(),
            "analisis_realizado":  self.v_analisis.get().strip(),
            "cantidad_mg":         None,
            "firma_analista":      self._firma_analista.get_path(),
            "id_usuario_analista": self._firma_analista.get_id(),
            "observaciones_prestamo": self.txt_obs.get("1.0", "end-1c").strip(),
        }
        mg_str = self.v_cantidad_mg.get().strip().replace(",", ".")
        if mg_str:
            try:
                datos["cantidad_mg"] = float(mg_str)
            except ValueError:
                messagebox.showwarning("Aviso", "Cantidad consumida inválida.", parent=self)
                return
        ok, msg = prest.actualizar_detalle(
            id_prestamo=self._prestamo["id"],
            datos=datos,
            usuario_accion=self._user.get("usuario") or self._user.get("nombre", "SISTEMA"),
        )
        if ok:
            messagebox.showinfo("Préstamos", msg, parent=self)
            if self._on_saved:
                self._on_saved()
        else:
            messagebox.showwarning("Préstamos", msg, parent=self)

    def _save_devolucion(self):
        fecha_dev = get_date_value(self.w_fecha_dev)
        if not fecha_dev:
            messagebox.showwarning("Aviso",
                "Ingrese la Fecha de Devolución.", parent=self)
            return
        id_verif = self._firma_verificado.get_id()
        if id_verif is None:
            messagebox.showwarning("Aviso",
                "Seleccione la firma de quien verifica el recibido.", parent=self)
            return
        if not messagebox.askyesno(
            "Confirmar devolución",
            "¿Desea registrar la devolución del estándar con la firma seleccionada?",
            parent=self,
        ):
            return
        firma_verif = self._firma_verificado.get_path()
        ok, msg = prest.completar_devolucion(
            id_prestamo=self._prestamo["id"],
            fecha_devolucion=fecha_dev,
            id_usuario_verificador=id_verif,
            firma_verificador=firma_verif,
            usuario_accion=self._user.get("usuario") or self._user.get("nombre", "SISTEMA"),
        )
        if ok:
            messagebox.showinfo("Préstamos", msg, parent=self)
            if self._on_saved:
                self._on_saved()
            self.destroy()
        else:
            messagebox.showwarning("Préstamos", msg, parent=self)


# ─────────────────────────────────────────────────────────────────────────────
# Nueva Solicitud window
# ─────────────────────────────────────────────────────────────────────────────

class NuevaSolicitudWindow(tk.Toplevel):
    """Formulario para crear una nueva solicitud de préstamo."""

    def __init__(self, master, maestras, current_user, on_saved=None):
        super().__init__(master)
        self._maestras = maestras
        self._user = current_user
        self._on_saved = on_saved
        self._lotes = []
        self._current_sustancia = None

        self._sustancias_by_codigo = common.map_sustancia_by_codigo(
            maestras.get("sustancias", [])
        )
        self._codigos_con_stock = sal.codigos_con_stock_disponible(maestras)

        self.title("Nueva Solicitud de Préstamo")
        self.configure(bg=COLORS["secondary"])
        self.resizable(False, False)
        self.grab_set()

        self._vars()
        self._build()

        self.update_idletasks()
        w, h = 640, 480
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _vars(self):
        self.v_codigo    = tk.StringVar()
        self.v_nombre    = tk.StringVar()
        self.v_lote      = tk.StringVar()
        self.v_disp      = tk.StringVar()
        self.v_unidad    = tk.StringVar()
        self.v_cantidad  = tk.StringVar()

    def _build(self):
        tk.Label(self, text="Nueva Solicitud de Préstamo",
                 bg=COLORS["secondary"], fg=COLORS["primary"],
                 font=("Segoe UI", 13, "bold")).pack(padx=16, pady=(16, 12))

        card = tk.Frame(self, bg=COLORS["secondary"])
        card.pack(fill="both", expand=True, padx=16)
        for c in range(4):
            card.grid_columnconfigure(c, weight=1)

        def lbl(text, r, c):
            tk.Label(card, text=text, bg=COLORS["secondary"], fg=COLORS["text_dark"],
                     font=("Segoe UI", 9, "bold")).grid(row=r, column=c, sticky="w",
                                                         padx=6, pady=(6, 2))

        # Código
        lbl("Código del Estándar", 0, 0)
        self.cb_codigo = ttk.Combobox(card, textvariable=self.v_codigo,
                                       values=self._codigos_con_stock,
                                       state="normal", font=("Segoe UI", 10), width=18)
        self.cb_codigo.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 8))
        self.cb_codigo.bind("<KeyRelease>", self._on_codigo_key)
        self.cb_codigo.bind("<<ComboboxSelected>>", self._on_codigo_selected)
        self.cb_codigo.bind("<FocusOut>", self._on_codigo_focusout)

        # Nombre (RO)
        lbl("Nombre", 0, 1)
        _entry_ro(card, self.v_nombre).grid(row=1, column=1, columnspan=3,
                                             sticky="ew", padx=6, pady=(0, 8))

        # Lote
        lbl("Lote", 2, 0)
        self.cb_lote = ttk.Combobox(card, textvariable=self.v_lote,
                                     state="readonly", font=("Segoe UI", 10))
        self.cb_lote.grid(row=3, column=0, sticky="ew", padx=6, pady=(0, 8))
        self.cb_lote.bind("<<ComboboxSelected>>", self._on_lote_selected)

        # Disponible
        lbl("Disponible", 2, 1)
        _entry_ro(card, self.v_disp).grid(row=3, column=1, sticky="ew", padx=6, pady=(0, 8))

        # Unidad
        lbl("Unidad", 2, 2)
        _entry_ro(card, self.v_unidad).grid(row=3, column=2, sticky="ew", padx=6, pady=(0, 8))

        # Cantidad
        lbl("Cantidad a prestar", 2, 3)
        _entry_rw(card, self.v_cantidad).grid(row=3, column=3, sticky="ew", padx=6, pady=(0, 8))

        # Observación
        lbl("Observación (opcional)", 4, 0)
        self.txt_obs = tk.Text(card, height=3, bg=COLORS["surface"], fg=COLORS["text_dark"],
                               font=("Segoe UI", 10), relief="flat", bd=0,
                               highlightthickness=1,
                               highlightbackground=COLORS["border_soft"],
                               highlightcolor=COLORS["primary"])
        self.txt_obs.grid(row=5, column=0, columnspan=4, sticky="ew", padx=6, pady=(0, 8))

        # Buttons
        bar = tk.Frame(self, bg=COLORS["secondary"])
        bar.pack(side="bottom", fill="x", padx=16, pady=(0, 14))
        _btn(bar, "Cancelar", "#6C757D", self.destroy).pack(side="right", padx=(6, 0))
        _btn(bar, "Registrar Solicitud", COLORS["primary"], self._guardar).pack(side="right")

    # ── Combobox helpers ──────────────────────────────────────────────────────

    def _ordered_codes(self, typed):
        txt = str(typed or "").strip()
        if not txt:
            return list(self._codigos_con_stock)
        return sorted(
            self._codigos_con_stock,
            key=lambda code: (
                txt not in code,
                code.find(txt) if txt in code else 10**9,
                len(code), code,
            ),
        )

    def _on_codigo_key(self, event=None):
        typed = self.v_codigo.get().strip()
        ordered = self._ordered_codes(typed)
        self.cb_codigo.configure(values=ordered)
        if not typed:
            self._clear_stock_fields()
            return
        if not any(typed in c for c in self._codigos_con_stock):
            self._clear_stock_fields()
            return
        match = next((c for c in ordered if typed in c), None)
        if match and event and event.keysym not in {"BackSpace", "Left", "Right", "Up", "Down"}:
            self.v_codigo.set(match)
            self.cb_codigo.icursor(len(typed))
            self.cb_codigo.selection_range(len(typed), len(match))
        if match == typed:
            self._on_codigo_selected()

    def _on_codigo_selected(self, _=None):
        codigo = self.v_codigo.get().strip()
        sust = self._sustancias_by_codigo.get(codigo)
        self._current_sustancia = sust
        if sust is None:
            self._clear_stock_fields()
            return
        self.v_nombre.set(sust.get("nombre", ""))
        self._lotes = prest.lotes_disponibles(sust.get("id"))
        labels = [f"{l.get('lote', '')}  (Disp: {l.get('disponible', 0)})"
                  for l in self._lotes]
        self.cb_lote.configure(values=labels)
        self.v_lote.set("")
        self.v_disp.set("")
        self.v_unidad.set("")

    def _on_codigo_focusout(self, _=None):
        codigo = self.v_codigo.get().strip()
        if codigo in self._sustancias_by_codigo:
            self._on_codigo_selected()
            return
        if codigo:
            self.v_codigo.set("")
        self._clear_stock_fields()

    def _on_lote_selected(self, _=None):
        idx = self.cb_lote.current()
        if idx < 0 or idx >= len(self._lotes):
            return
        lote = self._lotes[idx]
        self.v_disp.set(str(lote.get("disponible", 0)))
        uni = common.map_by_id(self._maestras["unidades"]).get(
            lote.get("id_unidad"), {}
        ).get("unidad", "")
        self.v_unidad.set(uni)

    def _clear_stock_fields(self):
        self._current_sustancia = None
        self._lotes = []
        self.v_nombre.set("")
        self.cb_lote.configure(values=[])
        self.v_lote.set("")
        self.v_disp.set("")
        self.v_unidad.set("")

    # ── Save ──────────────────────────────────────────────────────────────────

    def _guardar(self):
        if self._current_sustancia is None:
            messagebox.showwarning("Aviso", "Seleccione un código válido.", parent=self)
            return
        lote_idx = self.cb_lote.current()
        if lote_idx < 0 or lote_idx >= len(self._lotes):
            messagebox.showwarning("Aviso", "Seleccione un lote.", parent=self)
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
            messagebox.showwarning("Aviso",
                f"Stock insuficiente. Disponible: {disponible}", parent=self)
            return

        datos = {
            "id_inventario": lote.get("id_entrada") or lote.get("id"),
            "id_usuario":    self._user.get("id"),
            "id_unidad":     lote.get("id_unidad"),
            "cantidad":      cantidad,
            "observacion":   self.txt_obs.get("1.0", "end-1c").strip(),
        }
        result = prest.crear_solicitud(
            datos,
            usuario_accion=self._user.get("usuario") or self._user.get("nombre", "SISTEMA"),
        )
        messagebox.showinfo("Préstamos", "Solicitud registrada correctamente.", parent=self)
        if self._on_saved:
            self._on_saved()
        self.destroy()


# ─────────────────────────────────────────────────────────────────────────────
# Main window
# ─────────────────────────────────────────────────────────────────────────────

class PrestamosWindow(tk.Toplevel):
    ACTIVOS_COLS = [
        ("id",               "ID",           50),
        ("fecha_prestamo",   "Fecha",        100),
        ("codigo",           "Código",        80),
        ("nombre",           "Nombre",       220),
        ("lote",             "Lote",          90),
        ("fecha_vencimiento","F. Venc.",       90),
        ("potencia",         "Pureza",         80),
        ("propiedad",        "Propiedad",     100),
        ("fabricante_nombre","Fabricante",    130),
        ("ubicacion",        "Ubicación",    100),
        ("no_caja",          "No. Caja",      70),
        ("estado",           "Estado",        90),
    ]

    HIST_COLS = [
        ("id",               "ID",            50),
        ("fecha_prestamo",   "Fecha Solicitud",110),
        ("codigo",           "Código",         80),
        ("nombre",           "Nombre",        200),
        ("lote",             "Lote",           90),
        ("fecha_devolucion", "F. Devolución", 110),
        ("cantidad",         "Cantidad",       80),
        ("unidad",           "Unidad",         80),
        ("analisis_realizado","Análisis",      200),
        ("cantidad_mg",      "mg Usados",      80),
        ("usuario_presta_nombre","Solicitante",130),
    ]

    ESTADO_TAGS = {
        "SOLICITADO": ("#FFF3CD", "#856404"),
        "PRESTADO":   ("#D1ECF1", "#0C5460"),
        "DEVUELTO":   ("#D4EDDA", "#155724"),
    }

    def __init__(self, master):
        super().__init__(master)
        self.title("Préstamos de Estándares de Referencia")
        self.configure(bg=COLORS["secondary"])
        apply_default_window(self, min_width=1140, min_height=700)

        self._maestras     = common.cargar_maestras()
        self._users        = prest.usuarios_habilitados()
        self._current_user = self._resolve_current_user(master)

        draw_title(self, "Control y Seguimiento – Estándares de Referencia")
        self._build_ui()
        self._refresh_activos()

    def _resolve_current_user(self, master):
        try:
            return master.current_user
        except AttributeError:
            pass
        try:
            return master.master.current_user
        except AttributeError:
            pass
        return {}

    def _build_ui(self):
        wrap = tk.Frame(self, bg=COLORS["secondary"])
        wrap.pack(fill="both", expand=True, padx=10, pady=6)

        self.nb = ttk.Notebook(wrap)
        self.nb.pack(fill="both", expand=True)

        tab_act  = tk.Frame(self.nb, bg=COLORS["secondary"])
        tab_hist = tk.Frame(self.nb, bg=COLORS["secondary"])
        self.nb.add(tab_act,  text="  Activos  ")
        self.nb.add(tab_hist, text="  Historial  ")
        self.nb.bind("<<NotebookTabChanged>>", self._on_tab_change)

        self._build_activos_tab(tab_act)
        self._build_historial_tab(tab_hist)

        bottom = tk.Frame(self, bg=COLORS["secondary"])
        bottom.pack(side="bottom", fill="x", padx=10, pady=(0, 10))
        _btn(bottom, "Salir", "#6C757D", self.destroy).pack(side="right")

    def _build_activos_tab(self, parent):
        parent.grid_rowconfigure(1, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        top = tk.Frame(parent, bg=COLORS["secondary"])
        top.grid(row=0, column=0, sticky="ew", padx=6, pady=(8, 4))
        _btn(top, "+ Nueva Solicitud", COLORS["primary"],
             self._nueva_solicitud).pack(side="left")
        _btn(top, "Actualizar", "#6C757D",
             self._refresh_activos).pack(side="left", padx=(8, 0))
        tk.Label(top, text="  Doble clic en una fila para ver o actualizar el detalle.",
                 bg=COLORS["secondary"], fg=COLORS["text_muted"],
                 font=("Segoe UI", 9, "italic")).pack(side="left", padx=12)

        cols = [c[0] for c in self.ACTIVOS_COLS]
        self.tree_act = SearchableTreeview(
            parent, columns=cols,
            search_columns=["codigo", "nombre", "lote"],
            height=18,
        )
        self.tree_act.grid(row=1, column=0, sticky="nsew", padx=6)

        for key, title, width in self.ACTIVOS_COLS:
            self.tree_act.heading(key, text=title)
            self.tree_act.column(key, width=width, anchor="center")
        attach_treeview_sorting(self.tree_act.tree)

        for estado, (bg, fg) in self.ESTADO_TAGS.items():
            self.tree_act.tree.tag_configure(estado, background=bg, foreground=fg)

        self.tree_act.tree.bind("<Double-1>", self._on_activos_dbl)

    def _build_historial_tab(self, parent):
        parent.grid_rowconfigure(1, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        top = tk.Frame(parent, bg=COLORS["secondary"])
        top.grid(row=0, column=0, sticky="ew", padx=6, pady=(8, 4))
        _btn(top, "Actualizar", "#6C757D", self._refresh_historial).pack(side="left")

        cols = [c[0] for c in self.HIST_COLS]
        self.tree_hist = SearchableTreeview(
            parent, columns=cols,
            search_columns=["codigo", "nombre", "lote", "analisis_realizado"],
            height=18,
        )
        self.tree_hist.grid(row=1, column=0, sticky="nsew", padx=6)

        for key, title, width in self.HIST_COLS:
            self.tree_hist.heading(key, text=title)
            self.tree_hist.column(key, width=width, anchor="center")
        attach_treeview_sorting(self.tree_hist.tree)

        self.tree_hist.tree.bind("<Double-1>", self._on_hist_dbl)

    # ── Data refresh ──────────────────────────────────────────────────────────

    def _refresh_activos(self):
        self.tree_act.clear()
        rows = prest.todos_prestamos_activos(self._maestras)
        for r in rows:
            estado = str(r.get("estado", "")).upper()
            self.tree_act.insert(
                "", "end",
                values=tuple(r.get(c[0], "") for c in self.ACTIVOS_COLS),
                tags=(estado,),
            )

    def _refresh_historial(self):
        self.tree_hist.clear()
        rows = prest.prestamos_completados(self._maestras)
        for idx, r in enumerate(rows):
            self.tree_hist.insert(
                "", "end",
                values=tuple(r.get(c[0], "") for c in self.HIST_COLS),
                tags=("par" if idx % 2 == 0 else "impar",),
            )

    def _on_tab_change(self, _=None):
        idx = self.nb.index(self.nb.select())
        if idx == 1:
            self._refresh_historial()

    # ── Actions ───────────────────────────────────────────────────────────────

    def _nueva_solicitud(self):
        NuevaSolicitudWindow(
            self, self._maestras, self._current_user,
            on_saved=self._refresh_activos,
        )

    def _on_activos_dbl(self, _=None):
        sel = self.tree_act.tree.selection()
        if not sel:
            return
        values = self.tree_act.tree.item(sel[0], "values")
        if not values:
            return
        try:
            id_prestamo = int(values[0])
        except (ValueError, TypeError):
            return

        from database import get_db
        db = get_db()
        try:
            prestamo_raw = next(
                (p for p in db.get_prestamos() if p.get("id") == id_prestamo), None
            )
        finally:
            db.close()

        if prestamo_raw is None:
            messagebox.showwarning("Aviso", "No se encontró el préstamo.", parent=self)
            return

        PrestamoDetalleWindow(
            self, prestamo_raw, self._users,
            self._current_user,
            on_saved=self._refresh_activos,
        )

    def _on_hist_dbl(self, _=None):
        sel = self.tree_hist.tree.selection()
        if not sel:
            return
        values = self.tree_hist.tree.item(sel[0], "values")
        if not values:
            return
        try:
            id_prestamo = int(values[0])
        except (ValueError, TypeError):
            return

        from database import get_db
        db = get_db()
        try:
            prestamo_raw = next(
                (p for p in db.get_prestamos() if p.get("id") == id_prestamo), None
            )
        finally:
            db.close()

        if prestamo_raw is None:
            return

        PrestamoDetalleWindow(
            self, prestamo_raw, self._users,
            self._current_user,
            on_saved=None,
        )
