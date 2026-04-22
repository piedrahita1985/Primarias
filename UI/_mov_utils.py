import tkinter as tk
from tkinter import messagebox
from datetime import date
from datetime import datetime

from config.config import COLORS

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
    ch = event.char
    if ch == "":
        return
    if ch.isdigit() or ch == ".":
        return
    return "break"


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


def make_date_input(parent, row, col, label="Fecha", allow_past=True, empty_default=True):
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
    else:
        val = tk.StringVar(value="" if empty_default else date.today().isoformat())
        widget = tk.Entry(
            parent,
            textvariable=val,
            bg=COLORS["surface"],
            fg=COLORS["text_dark"],
            font=("Segoe UI", 10),
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=COLORS["border_soft"],
            highlightcolor=COLORS["primary"],
            width=20,
        )
        widget._fallback_var = val  # type: ignore[attr-defined]

    widget.grid(row=row + 1, column=col, sticky="ew", padx=8, pady=(0, 8))
    if DateEntry is not None and empty_default:
        try:
            widget.delete(0, "end")
        except Exception:
            pass
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
