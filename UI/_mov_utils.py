import tkinter as tk
from tkinter import messagebox
from datetime import date
from datetime import datetime

from config.config import COLORS, WINDOW_HEIGHT, WINDOW_WIDTH

try:
    from tkcalendar import DateEntry
except Exception:  # pragma: no cover
    DateEntry = None


def upper_text_var(var: tk.StringVar):
    def _on_write(*_):
        value = var.get()
        up = value.upper()
        if value != up:
            var.set(up)
    var.trace_add("write", _on_write)


def only_numeric(event):
    # Permite teclas de edición/navegación para no bloquear Backspace/Delete.
    if event.keysym in {
        "BackSpace",
        "Delete",
        "Left",
        "Right",
        "Home",
        "End",
        "Tab",
        "Return",
        "KP_Enter",
    }:
        return

    ch = event.char
    if ch == "":
        return
    if ch.isdigit() or ch == ".":
        return
    return "break"


def attach_treeview_sorting(tree):
    sort_state = {}

    def _coerce(v):
        txt = str(v or "").strip()
        if txt == "":
            return ""
        try:
            return float(txt.replace(",", "."))
        except ValueError:
            return txt.upper()

    def _sort_by(col):
        reverse = sort_state.get(col, False)
        items = [(tree.set(k, col), k) for k in tree.get_children("")]
        items.sort(key=lambda x: _coerce(x[0]), reverse=reverse)
        for idx, (_, k) in enumerate(items):
            tree.move(k, "", idx)
        sort_state[col] = not reverse

    for col in tree["columns"]:
        tree.heading(col, command=lambda c=col: _sort_by(c))


def only_letters(event):
    ch = event.char
    if ch == "":
        return
    if ch.isalpha() or ch in " -_/().,":
        return
    return "break"


def draw_title(window, text):
    header = tk.Frame(window, bg=COLORS["primary"], height=54)
    header.pack(fill="x")
    header.pack_propagate(False)
    tk.Label(
        header,
        text=text,
        bg=COLORS["primary"],
        fg="white",
        font=("Segoe UI", 15, "bold"),
    ).pack(expand=True)


def apply_default_window(window, width=WINDOW_WIDTH, height=WINDOW_HEIGHT, min_width=1040, min_height=640):
    window.update_idletasks()
    screen_w = window.winfo_screenwidth()
    screen_h = window.winfo_screenheight()

    # Ajusta el tamaño inicial para que siempre quede visible el borde inferior.
    max_w = max(screen_w - 80, 800)
    max_h = max(screen_h - 120, 520)
    fit_w = min(width, max_w)
    fit_h = min(height, max_h)

    x = max((screen_w - fit_w) // 2, 0)
    y = max((screen_h - fit_h) // 2, 0)
    window.geometry(f"{fit_w}x{fit_h}+{x}+{y}")
    window.minsize(min(min_width, max_w), min(min_height, max_h))
    window.resizable(True, True)


def make_labeled_entry(parent, label, var, row, col, width=22, read_only=False):
    tk.Label(
        parent,
        text=label,
        bg=COLORS["secondary"],
        fg=COLORS["text_dark"],
        font=("Segoe UI", 9, "bold"),
    ).grid(row=row, column=col, sticky="w", padx=8, pady=(6, 2))

    state = "readonly" if read_only else "normal"
    entry = tk.Entry(
        parent,
        textvariable=var,
        state=state,
        width=width,
        bg=COLORS["surface"],
        fg=COLORS["text_dark"],
        font=("Segoe UI", 10),
        relief="flat",
        bd=0,
        highlightthickness=1,
        highlightbackground=COLORS["border_soft"],
        highlightcolor=COLORS["primary"],
    )
    entry.grid(row=row + 1, column=col, sticky="ew", padx=8, pady=(0, 8))
    return entry


def _add_placeholder_to_entry(entry, var, placeholder):
    """Agrega placeholder a un Entry normal."""
    def on_focus_in(event):
        if var.get() == placeholder:
            var.set("")
            entry.configure(fg=COLORS["text_dark"])

    def on_focus_out(event):
        if not var.get().strip():
            var.set(placeholder)
            entry.configure(fg=COLORS["text_muted"])

    if not var.get():
        var.set(placeholder)
        entry.configure(fg=COLORS["text_muted"])

    entry.bind("<FocusIn>", on_focus_in)
    entry.bind("<FocusOut>", on_focus_out)


def _add_placeholder_to_dateentry(widget, placeholder):
    """Agrega placeholder a DateEntry."""
    try:
        entry = widget.entry
        original_fg = entry.cget("fg")

        def on_focus_in(e):
            if entry.get() == placeholder:
                entry.delete(0, "end")
                entry.configure(fg=original_fg)

        def on_focus_out(e):
            if not entry.get():
                entry.insert(0, placeholder)
                entry.configure(fg=COLORS["text_muted"])

        if not entry.get():
            entry.insert(0, placeholder)
            entry.configure(fg=COLORS["text_muted"])

        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)
    except Exception:
        pass


def make_date_input(parent, row, col, label="Fecha", allow_past=True, empty_default=True,
                   placeholder="YYYY-MM-DD", required=False):
    if required:
        make_required_label(parent, label, row, col)
    else:
        tk.Label(
            parent,
            text=label,
            bg=COLORS["secondary"],
            fg=COLORS["text_dark"],
            font=("Segoe UI", 9, "bold"),
        ).grid(row=row, column=col, sticky="w", padx=8, pady=(6, 2))

    if DateEntry is not None:
        kwargs = {}
        if not allow_past:
            kwargs["mindate"] = date.today()
        widget = DateEntry(
            parent,
            date_pattern="yyyy-mm-dd",
            width=18,
            background=COLORS["primary"],
            foreground="white",
            borderwidth=0,
            font=("Segoe UI", 10),
            **kwargs,
        )
        if empty_default:
            try:
                widget.delete(0, "end")
            except Exception:
                pass
        _add_placeholder_to_dateentry(widget, placeholder)
    else:
        val = tk.StringVar(value="" if empty_default else date.today().isoformat())
        widget = tk.Entry(
            parent,
            textvariable=val,
            bg=COLORS["surface"],
            fg=COLORS["text_muted"],
            font=("Segoe UI", 10),
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["border_soft"],
            highlightcolor=COLORS["primary"],
            width=20,
        )
        _add_placeholder_to_entry(widget, val, placeholder)
        widget._fallback_var = val  # type: ignore[attr-defined]

    widget.grid(row=row + 1, column=col, sticky="ew", padx=8, pady=(0, 8))
    return widget


def get_date_value(widget):
    if DateEntry is not None and isinstance(widget, DateEntry):
        txt = widget.get().strip()
        if not txt:
            return ""
        try:
            return datetime.strptime(txt, "%Y-%m-%d").date().isoformat()
        except ValueError:
            return txt
    var = getattr(widget, "_fallback_var", None)
    if var is not None:
        return var.get().strip()
    return ""


def make_date_widget(parent, placeholder="YYYY-MM-DD"):
    """Widget de fecha sin etiqueta, para usar inline con pack."""
    if DateEntry is not None:
        widget = DateEntry(
            parent,
            date_pattern="yyyy-mm-dd",
            width=12,
            background=COLORS["primary"],
            foreground="white",
            borderwidth=0,
            font=("Segoe UI", 10),
        )
        try:
            widget.delete(0, "end")
        except Exception:
            pass
        _add_placeholder_to_dateentry(widget, placeholder)
    else:
        val = tk.StringVar()
        widget = tk.Entry(
            parent,
            textvariable=val,
            bg=COLORS["surface"],
            fg=COLORS["text_muted"],
            font=("Segoe UI", 10),
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["border_soft"],
            highlightcolor=COLORS["primary"],
            width=14,
        )
        _add_placeholder_to_entry(widget, val, placeholder)
        widget._fallback_var = val  # type: ignore[attr-defined]
    return widget


def make_required_label(parent, text, row, col, **kwargs):
    """Crea una etiqueta con asterisco rojo para campos obligatorios."""
    frame = tk.Frame(parent, bg=COLORS["secondary"])
    frame.grid(row=row, column=col, sticky="w", padx=8, pady=(6, 2))
    tk.Label(
        frame, text=text, bg=COLORS["secondary"],
        fg=COLORS["text_dark"], font=("Segoe UI", 9, "bold"),
    ).pack(side="left")
    tk.Label(
        frame, text=" *", bg=COLORS["secondary"],
        fg="#DC3545", font=("Segoe UI", 9, "bold"),
    ).pack(side="left")
    return frame


def highlight_required_field(entry, is_valid):
    """Resalta o quita el resaltado de un campo obligatorio."""
    if is_valid:
        try:
            entry.configure(highlightbackground=COLORS["border_soft"], highlightthickness=1)
        except Exception:
            pass
    else:
        try:
            entry.configure(highlightbackground="#DC3545", highlightthickness=2)
        except Exception:
            pass


def validate_required_fields(fields_dict, parent=None):
    """
    Valida campos obligatorios.
    fields_dict: {campo_nombre: (widget_entry, valor)}
    Retorna (bool, lista_campos_faltantes)
    """
    missing = []
    for name, (entry, value) in fields_dict.items():
        if not str(value).strip():
            missing.append(name)
            highlight_required_field(entry, False)
        else:
            highlight_required_field(entry, True)

    if missing and parent:
        messagebox.showwarning(
            "Campos obligatorios",
            "Los siguientes campos son obligatorios:\n• " + "\n• ".join(missing),
            parent=parent,
        )
    return len(missing) == 0, missing


def validate_today_or_future(date_text, parent=None, field_name="Fecha"):
    value = str(date_text or "").strip()
    try:
        value_date = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        messagebox.showwarning("Aviso", f"{field_name} invalida. Use formato YYYY-MM-DD.", parent=parent)
        return False

    if value_date < date.today():
        messagebox.showwarning("Aviso", f"{field_name} no puede ser anterior a hoy.", parent=parent)
        return False
    return True
