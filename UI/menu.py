import importlib
import tkinter as tk
from tkinter import messagebox

from PIL import Image, ImageOps, ImageTk

from app_paths import resource_path
from config.config import COLORS, PROJECT_NAME, WINDOW_HEIGHT, WINDOW_WIDTH
from UI._mov_utils import apply_default_window

MENU_IMAGE_PATH = resource_path("imagenes", "imagenmenu.jpg")
LOGO_IMAGE_PATH = resource_path("imagenes", "imagencecif.png")


class ScrollablePanel(tk.Frame):
	def __init__(self, parent, bg_color):
		super().__init__(parent, bg=bg_color)
		self.canvas = tk.Canvas(self, bg=bg_color, highlightthickness=0, bd=0)
		self.scrollbar = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
		self.inner = tk.Frame(self.canvas, bg=bg_color)

		self.inner.bind("<Configure>", lambda _: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
		self.canvas_window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
		self.canvas.configure(yscrollcommand=self.scrollbar.set)
		self.canvas.bind("<Configure>", self._resize_inner)

		self.canvas.pack(side="left", fill="both", expand=True)
		self.scrollbar.pack(side="right", fill="y")

		self.inner.bind("<Enter>", lambda _: self._bind_mousewheel())
		self.inner.bind("<Leave>", lambda _: self._unbind_mousewheel())

	def _bind_mousewheel(self):
		self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

	def _unbind_mousewheel(self):
		self.canvas.unbind_all("<MouseWheel>")

	def _resize_inner(self, event):
		self.canvas.itemconfigure(self.canvas_window, width=event.width)

	def _on_mousewheel(self, event):
		self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


class Card(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg="#DDE6F0")  # sombra más visible
        self.body = tk.Frame(self, bg=COLORS["surface"])
        self.body.pack(fill="both", expand=True, padx=1, pady=1)


class MenuApp(tk.Toplevel):
	def __init__(self, master, username="", user_record=None):
		super().__init__(master)
		self.username = username
		self.user_record = user_record or {}
		self.permisos = self.user_record.get("permisos", {}) if isinstance(self.user_record.get("permisos", {}), dict) else {}
		self.logout_requested = False
		self._images = {}

		self.title(f"{PROJECT_NAME} - Menu")
		self.configure(bg=COLORS["secondary"])

		apply_default_window(self, width=WINDOW_WIDTH, height=WINDOW_HEIGHT, min_width=1100, min_height=700)
		self._build_ui()

		self.protocol("WM_DELETE_WINDOW", self._on_close)

	def _build_ui(self):
		self.grid_rowconfigure(0, weight=0)
		self.grid_rowconfigure(1, weight=1)
		self.grid_columnconfigure(0, weight=1)

		topbar = tk.Frame(self, bg=COLORS["surface"], height=64)
		topbar.grid(row=0, column=0, sticky="nsew")
		topbar.grid_propagate(False)
		topbar.grid_columnconfigure(1, weight=1)

		logo_card = tk.Frame(topbar, bg=COLORS["surface_alt"])
		logo_card.grid(row=0, column=0, padx=(18, 12), pady=10, sticky="w")
		self._load_image(logo_card, LOGO_IMAGE_PATH, "logo", 150, 38, "CECIF")

		tk.Label(
			topbar,
			text=PROJECT_NAME,
			bg=COLORS["surface"],
			fg=COLORS["primary"],
			font=("Segoe UI", 15, "bold"),
		).grid(row=0, column=1, sticky="w")

		user_wrap = tk.Frame(topbar, bg=COLORS["surface"])
		user_wrap.grid(row=0, column=2, padx=(10, 18), pady=10, sticky="e")

		user_card = tk.Frame(user_wrap, bg=COLORS["primary"], bd=0)
		user_card.pack(side="left", padx=(0, 8))
		tk.Label(
    		user_card,
    		text=f"👤 {self.username}",
    		bg=COLORS["primary"],
    		fg="white",
    		font=("Segoe UI", 10, "bold"),
    		padx=14,
    		pady=6,
		).pack()

		tk.Button(
			user_wrap,
			text="Cerrar sesión",
			command=self._logout,
			cursor="hand2",
		).pack(side="left")

		tk.Button(
			user_wrap,
			text="Salir",
			command=self._on_close,
			cursor="hand2",
		).pack(side="left", padx=(6, 0))

		content = tk.Frame(self, bg=COLORS["secondary"])
		content.grid(row=1, column=0, sticky="nsew")
		content.grid_rowconfigure(0, weight=0)
		content.grid_rowconfigure(1, weight=1)
		content.grid_columnconfigure(0, weight=6)
		content.grid_columnconfigure(1, weight=4)

		hero_card = Card(content)
		hero_card.grid(row=0, column=0, columnspan=2, sticky="nsew", padx=18, pady=(18, 12))
		hero_card.body.grid_columnconfigure(0, weight=3)
		hero_card.body.grid_columnconfigure(1, weight=2)

		header_left = tk.Frame(hero_card.body, bg=COLORS["surface"])
		header_left.grid(row=0, column=0, sticky="nsew", padx=(18, 12), pady=14)

		tk.Label(
			header_left,
			text="Panel principal",
			bg=COLORS["surface"],
			fg=COLORS["primary_dark"],
			font=("Segoe UI", 18, "bold"),
		).pack(anchor="w")
		tk.Label(
			header_left,
			text="Interfaz moderna, clinica y profesional para gestionar inventario de laboratorio.",
			bg=COLORS["surface"],
			fg=COLORS["text_muted"],
			font=("Segoe UI", 10),
			wraplength=700,
			justify="left",
		).pack(anchor="w", pady=(4, 10))

		tk.Label(
			header_left,
			text="Movimientos  •  Reportes  •  Maestras",
			bg=COLORS["surface"],
			fg=COLORS["text_muted"],
			font=("Segoe UI", 10, "bold"),
		).pack(anchor="w", pady=(0, 2))

		header_right = tk.Frame(hero_card.body, bg=COLORS["surface"])
		header_right.grid(row=0, column=1, sticky="nsew", padx=(4, 18), pady=14)
		self._load_image(header_right, MENU_IMAGE_PATH, "menu_banner", 500, 180, "Imagen")

		self.mov_card = Card(content)
		self.mov_card.grid(row=1, column=0, sticky="nsew", padx=(18, 10), pady=(0, 18))
		self._build_movimientos_panel(self.mov_card.body)

		self.mae_card = Card(content)
		self.mae_card.grid(row=1, column=1, sticky="nsew", padx=(8, 18), pady=(0, 18))
		self._build_maestras_panel(self.mae_card.body)

	def _load_image(self, container, image_path, key, width, height, fallback_text):
		try:
			image = Image.open(image_path)
			image = ImageOps.fit(
				image,
				(max(10, width), max(10, height)),
				method=Image.LANCZOS,
				centering=(0.5, 0.5),
			)
			photo = ImageTk.PhotoImage(image)
			self._images[key] = photo
			tk.Label(container, image=photo, bd=0, bg=container.cget("bg")).pack(fill="both", expand=True)
		except Exception:
			tk.Label(
				container,
				text=fallback_text,
				bg=container.cget("bg"),
				fg=COLORS["text_dark"],
				font=("Segoe UI", 14, "bold"),
			).pack(fill="both", expand=True)

	def _action_card(self, parent, title, subtitle, command=None, enabled=True):
		if enabled:
			bg_card = COLORS["surface"]
			bg_hover = COLORS["primary_soft"]
			title_fg = COLORS["primary_dark"]
			sub_fg = COLORS["text_muted"]
			cursor = "hand2"
		else:
			bg_card = "#ECEFF3"
			bg_hover = "#ECEFF3"
			title_fg = COLORS["text_muted"]
			sub_fg = COLORS["text_muted"]
			cursor = "arrow"

		card = tk.Frame(
			parent,
			bg=bg_card,
			bd=0,
			highlightthickness=1,
			highlightbackground="#D0D7E2",
			cursor=cursor
		)

		inner = tk.Frame(card, bg=bg_card)
		inner.pack(fill="both", expand=True, padx=6, pady=6)

		lbl_title = tk.Label(
			inner,
			text=title,
			bg=bg_card,
			fg=title_fg,
			font=("Segoe UI", 11, "bold"),
			anchor="w"
		)
		lbl_title.pack(anchor="w")

		lbl_sub = tk.Label(
			inner,
			text=subtitle,
			bg=bg_card,
			fg=sub_fg,
			font=("Segoe UI", 9),
			anchor="w"
		)
		lbl_sub.pack(anchor="w")

		def on_enter(e):
			if not enabled:
				return
			card.configure(bg=bg_hover)
			inner.configure(bg=bg_hover)
			lbl_title.configure(bg=bg_hover, fg=COLORS["primary_dark"])
			lbl_sub.configure(bg=bg_hover, fg=COLORS["primary_dark"])

		def on_leave(e):
			card.configure(bg=bg_card)
			inner.configure(bg=bg_card)
			lbl_title.configure(bg=bg_card, fg=title_fg)
			lbl_sub.configure(bg=bg_card, fg=sub_fg)

		# eventos hover
		for widget in (card, inner, lbl_title, lbl_sub):
			widget.bind("<Enter>", on_enter)
			widget.bind("<Leave>", on_leave)

		# click
		if enabled and command is not None:
			for widget in (card, inner, lbl_title, lbl_sub):
				widget.bind("<Button-1>", lambda e: command())

		return card

	def _has_perm(self, key):
		if not key:
			return True
		if not self.permisos:
			return True
		return bool(self.permisos.get(key, False))
	
	def _show_pending_feature(self, title):
		messagebox.showinfo("Proximamente", f"{title} se habilitara en la siguiente etapa.")

	def _build_movimientos_panel(self, panel):
		panel.grid_rowconfigure(1, weight=1)
		panel.grid_columnconfigure(0, weight=1)

		tk.Label(
			panel,
			text="Movimientos y reportes",
			bg=COLORS["surface"],
			fg=COLORS["text_dark"],
			font=("Segoe UI", 14, "bold"),
		).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 6))

		scroll = ScrollablePanel(panel, COLORS["surface"])
		scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
		scroll.inner.grid_columnconfigure(0, weight=1)
		scroll.inner.grid_columnconfigure(1, weight=1)

		actions = [
			("Entradas", "Registro de ingresos", "entradas", lambda: self._open_master_module("UI.entradas", "entradas")),
			("Salidas", "Control de despachos", "salidas", lambda: self._open_master_module("UI.salidas", "salidas")),
			("Inventario", "Stock", "inventario", lambda: self._open_master_module("UI.inventario", "inventario")),
			("Bitacora", "Auditoria", "bitacora", lambda: self._open_master_module("UI.bitacora", "bitacora")),
			("Prestamos", "Gestión de préstamos", "prestamos", lambda: self._open_master_module("UI.prestamos", "prestamos")),
			("Recibidos", "Recepción y devolución", "recibidos", lambda: self._open_master_module("UI.recibidos", "recibidos")),
		]

		for index, (title, subtitle, perm_key, command) in enumerate(actions):
			row = index // 2
			col = index % 2
			enabled = self._has_perm(perm_key)
			btn = self._action_card(scroll.inner, title, subtitle, command=command, enabled=enabled)
			btn.grid(row=row, column=col, sticky="nsew", padx=8, pady=8)

	def _build_maestras_panel(self, panel):
		panel.grid_rowconfigure(1, weight=1)
		panel.grid_columnconfigure(0, weight=1)

		tk.Label(
			panel,
			text="Maestras",
			bg=COLORS["surface"],
			fg=COLORS["text_dark"],
			font=("Segoe UI", 14, "bold"),
		).grid(row=0, column=0, sticky="w", padx=16, pady=(16, 6))

		scroll = ScrollablePanel(panel, COLORS["surface"])
		scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
		scroll.inner.grid_columnconfigure(0, weight=1)
		scroll.inner.grid_columnconfigure(1, weight=1)

		maestras = [
			("Sustancias", "UI.sustancias", "sustancias"),
			("Tipos entrada", "UI.tipos_entrada", "tipos_entrada"),
			("Tipos salida", "UI.tipos_salida", "tipos_salida"),
			("Fabricantes", "UI.fabricantes", "fabricantes"),
			("Unidades", "UI.unidades", "unidades"),
			("Ubicaciones", "UI.ubicaciones", "ubicaciones"),
			("Condiciones", "UI.condiciones", "condiciones"),
			("Colores", "UI.colores", "colores"),
			("Usuarios", "UI.usuarios", "usuarios"),
		]

		for index, (title, module_name, perm_key) in enumerate(maestras):
			row = index // 2
			col = index % 2
			enabled = self._has_perm(perm_key)
			button = self._action_card(
				scroll.inner,
				title,
				"Añadir maestra",
				command=lambda mod=module_name, text=title: self._open_master_module(mod, text),
				enabled=enabled,
			)
			button.grid(row=row, column=col, sticky="nsew", padx=8, pady=8)

	def _open_master_module(self, module_name, title):
		try:
			module = importlib.import_module(module_name)
			if hasattr(module, "open_window"):
				module.open_window(self)
				return
			messagebox.showinfo("Modulo", f"Archivo {title}.py encontrado, aun sin implementacion.")
		except Exception as exc:
			messagebox.showerror("Error", f"No fue posible abrir {title}.py\n\n{exc}")

	def _on_close(self):
		self.logout_requested = False
		self.destroy()

	def _logout(self):
		if not messagebox.askyesno("Cerrar sesión", "¿Desea cerrar la sesión actual?", parent=self):
			return
		self.logout_requested = True
		self.destroy()
