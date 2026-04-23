import tkinter as tk
from tkinter import messagebox
from tkinter import ttk

from PIL import Image, ImageTk

from app_paths import resource_path
from config.config import COLORS, PROJECT_NAME, WINDOW_HEIGHT, WINDOW_WIDTH
from logica import usuarios_logica as usr
from UI._mov_utils import apply_default_window

IMAGE_PATH = resource_path("imagenes", "imagenlogin.jpg")


def cargar_usuarios():
	return usr.cargar()


class LoginApp(tk.Tk):
	def __init__(self):
		super().__init__()
		self.title(PROJECT_NAME)
		self.resizable(True, True)
		self.configure(bg=COLORS["secondary"])

		self._var_usuario = tk.StringVar()
		self._var_password = tk.StringVar()
		self._var_show_password = tk.BooleanVar(value=False)
		self._photo = None
		self._entry_usuario = None
		self._entry_password = None

		apply_default_window(self, width=WINDOW_WIDTH, height=WINDOW_HEIGHT, min_width=1040, min_height=640)
		self._build_ui()

	def _build_ui(self):
		self.grid_rowconfigure(0, weight=1)
		self.grid_columnconfigure(0, weight=6)
		self.grid_columnconfigure(1, weight=5)

		left_panel = tk.Frame(self, bg=COLORS["surface"])
		left_panel.grid(row=0, column=0, sticky="nsew")
		self._build_image_panel(left_panel)

		right_wrap = tk.Frame(self, bg=COLORS["secondary"])
		right_wrap.grid(row=0, column=1, sticky="nsew")
		right_wrap.grid_rowconfigure(0, weight=1)
		right_wrap.grid_columnconfigure(0, weight=1)

		card_shadow = tk.Frame(right_wrap, bg="#E3EAF4")
		card_shadow.grid(row=0, column=0, padx=(34, 38), pady=34, sticky="nsew")

		right_panel = tk.Frame(card_shadow, bg=COLORS["surface"])
		right_panel.pack(fill="both", expand=True, padx=1, pady=1)
		self._build_form_panel(right_panel)

	def _build_image_panel(self, panel):
		panel.grid_rowconfigure(0, weight=1)
		panel.grid_columnconfigure(0, weight=1)
		try:
			image = Image.open(IMAGE_PATH)
			image = image.resize((680, 600), Image.LANCZOS)

			self._photo = ImageTk.PhotoImage(image)

			tk.Label(panel, image=self._photo).grid(row=0, column=0, sticky="nsew")

		except Exception as e:
			print("Error cargando imagen:", e)

	def _build_form_panel(self, panel):
		panel.grid_columnconfigure(0, weight=1)
		field_width = 390

		tk.Label(
			panel,
			text=PROJECT_NAME,
			bg=COLORS["surface"],
			fg=COLORS["primary"],
			font=("Segoe UI", 18, "bold"),
			justify="center",
			wraplength=field_width,
		).grid(row=0, column=0, pady=(64, 10), padx=30)

		tk.Label(
			panel,
			text="Acceso institucional",
			bg=COLORS["surface"],
			fg=COLORS["text_muted"],
			font=("Segoe UI", 11),
		).grid(row=1, column=0, pady=(0, 28))

		tk.Label(
			panel,
			text="Usuario",
			bg=COLORS["surface"],
			fg=COLORS["text_dark"],
			font=("Segoe UI", 10, "bold"),
		).grid(row=2, column=0, sticky="w", padx=58)

		entry_usuario = tk.Entry(
			panel,
			textvariable=self._var_usuario,
			font=("Segoe UI", 11),
			bd=0,
			relief="flat",
			fg=COLORS["text_dark"],
			bg="white",
			highlightthickness=2,
			highlightbackground=COLORS["border_soft"],
			highlightcolor=COLORS["primary"],
			insertbackground=COLORS["primary"],
		)
		entry_usuario.grid(row=3, column=0, pady=(8, 20), ipadx=16, ipady=10)
		entry_usuario.configure(width=34)
		self._bind_field_focus(entry_usuario)
		self._entry_usuario = entry_usuario

		tk.Label(
			panel,
			text="Contrasena",
			bg=COLORS["surface"],
			fg=COLORS["text_dark"],
			font=("Segoe UI", 10, "bold"),
		).grid(row=4, column=0, sticky="w", padx=58)

		entry_password = tk.Entry(
			panel,
			textvariable=self._var_password,
			show="*",
			font=("Segoe UI", 11),
			bd=0,
			relief="flat",
			fg=COLORS["text_dark"],
			bg="white",
			highlightthickness=2,
			highlightbackground=COLORS["border_soft"],
			highlightcolor=COLORS["primary"],
			insertbackground=COLORS["primary"],
		)
		entry_password.grid(row=5, column=0, pady=(8, 24), ipadx=16, ipady=10)
		entry_password.configure(width=34)
		self._bind_field_focus(entry_password)
		entry_password.bind("<Return>", lambda _: self._login())
		self._entry_password = entry_password

		ttk.Checkbutton(
			panel,
			text="Ver contraseña",
			variable=self._var_show_password,
			command=self._toggle_password,
		).grid(row=6, column=0, sticky="w", padx=58, pady=(0, 16))

		btn_ingresar = tk.Button(
			panel,
			text="Ingresar",
			command=self._login,
			font=("Segoe UI", 11, "bold"),
			bg=COLORS["primary"],
			fg=COLORS["text_light"],
			activebackground=COLORS["button_hover"],
			activeforeground=COLORS["text_light"],
			relief="flat",
			bd=0,
			cursor="hand2",
		)
		btn_ingresar.grid(row=7, column=0, pady=(0, 16), ipadx=36, ipady=10)
		btn_ingresar.bind("<Enter>", lambda _: btn_ingresar.configure(bg=COLORS["button_hover"]))
		btn_ingresar.bind("<Leave>", lambda _: btn_ingresar.configure(bg=COLORS["primary"]))

		lbl_cambiar = tk.Label(
			panel,
			text="Cambiar contrasena",
			bg=COLORS["surface"],
			fg=COLORS["primary"],
			font=("Segoe UI", 9, "underline"),
			cursor="hand2",
		)
		lbl_cambiar.grid(row=8, column=0, pady=(2, 8))
		lbl_cambiar.bind(
			"<Button-1>",
			lambda _: messagebox.showinfo(
				"Cambiar contrasena",
				"Contacte al administrador para restablecer su contrasena.",
			),
		)

		entry_usuario.focus_set()

	def _toggle_password(self):
		if self._entry_password is None:
			return
		self._entry_password.configure(show="" if self._var_show_password.get() else "*")

	@staticmethod
	def _bind_field_focus(entry_widget):
		entry_widget.bind("<FocusIn>", lambda _: entry_widget.configure(bg="#F5F9FF"))
		entry_widget.bind("<FocusOut>", lambda _: entry_widget.configure(bg="white"))

	def _login(self):
		username = self._var_usuario.get().strip()
		password = self._var_password.get().strip()

		if not username or not password:
			messagebox.showwarning("Campos vacios", "Ingrese usuario y contrasena.")
			return

		users = cargar_usuarios()
		valid_user = next(
			(
				user
				for user in users
				if (user.get("usuario") or user.get("nombre")) == username
				and (user.get("contrasena") or user.get("contraseña")) == password
				and user.get("estado", "HABILITADA") == "HABILITADA"
			),
			None,
		)

		if not valid_user:
			messagebox.showerror("Acceso denegado", "Usuario o contrasena incorrectos.")
			return

		from UI.menu import MenuApp

		self.withdraw()
		menu = MenuApp(
			self,
			username=valid_user.get("usuario") or valid_user.get("nombre", ""),
			user_record=valid_user,
		)
		self.wait_window(menu)
		if getattr(menu, "logout_requested", False):
			self._var_usuario.set("")
			self._var_password.set("")
			self._var_show_password.set(False)
			self._toggle_password()
			self.deiconify()
			if self._entry_usuario is not None:
				self._entry_usuario.focus_set()
			return
		self.destroy()
