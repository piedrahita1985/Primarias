# UI/_smart_combobox.py
import tkinter as tk
from tkinter import ttk
from config.config import COLORS


class SmartCodeCombobox(ttk.Combobox):
    """Combobox con autocompletado que muestra código + nombre."""

    def __init__(self, parent, sustancias_by_codigo, **kwargs):
        super().__init__(parent, **kwargs)
        self._sustancias = sustancias_by_codigo
        self._display_values = self._build_display_values()
        self.configure(values=self._display_values)
        self.bind("<KeyRelease>", self._on_key_release)
        self.bind("<<ComboboxSelected>>", self._on_select)
        self._current_codigo = ""

    def _build_display_values(self):
        """Construye lista de valores para mostrar: 'CODIGO - Nombre'."""
        values = []
        for s in self._sustancias.values():
            codigo = s.get("codigo", "")
            nombre = s.get("nombre", "")[:50]
            if codigo:
                values.append(f"{codigo} - {nombre}")
        return sorted(values, key=lambda x: (len(x.split(" - ")[0]), x))

    def _on_key_release(self, event):
        if event.keysym in ("Up", "Down", "Left", "Right", "Return", "Tab"):
            return

        typed = self.get().strip()
        if not typed:
            self.configure(values=self._display_values)
            return

        # Filtrar valores que contengan el texto tipeado
        filtered = [v for v in self._display_values if typed.upper() in v.upper()]
        self.configure(values=filtered)

        # Si solo hay una coincidencia exacta al inicio, autocompletar
        if (
            filtered
            and len(filtered) == 1
            and filtered[0].upper().startswith(typed.upper())
        ):
            self.set(filtered[0])
            self.icursor(len(typed))
            self.selection_range(len(typed), len(filtered[0]))

    def _on_select(self, event):
        """Cuando se selecciona un valor, emitir evento con el código."""
        selected = self.get()
        if " - " in selected:
            codigo = selected.split(" - ")[0].strip()
            self._current_codigo = codigo
            self.event_generate("<<SmartCodeSelected>>")

    def get_codigo(self):
        """Devuelve solo el código, no el texto completo."""
        value = self.get()
        if " - " in value:
            return value.split(" - ")[0].strip()
        return value.strip()

    def set_by_codigo(self, codigo):
        """Selecciona por código."""
        for v in self._display_values:
            if v.startswith(codigo + " - "):
                self.set(v)
                self._current_codigo = codigo
                return
        # Si no se encuentra en display, poner el código tal cual
        self.set(codigo)
        self._current_codigo = codigo
