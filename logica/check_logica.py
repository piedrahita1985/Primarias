import json
from datetime import datetime

from app_paths import resource_path
from logica.movimientos_common import next_id

_CECIF_PATH = resource_path("data", "checkCECIF.json")
_CLIENTES_PATH = resource_path("data", "checkClientes.json")

_KEY_CECIF = "checkCECIF"
_KEY_CLIENTES = "checkClientes"


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _load(path, key):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f).get(key, [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save(path, key, items):
    records = [
        "  " + json.dumps(item, ensure_ascii=False, separators=(", ", ": "))
        for item in items
    ]
    with open(path, "w", encoding="utf-8") as f:
        if records:
            f.write('{ "' + key + '": [\n')
            f.write(",\n".join(records))
            f.write("\n] }\n")
        else:
            f.write('{ "' + key + '": [] }\n')


# ---------------------------------------------------------------------------
# CECIF checklist
# ---------------------------------------------------------------------------

VERIFICACION_CECIF_CAMPOS = [
    ("nombre", "Nombre"),
    ("no_lote", "No. de Lote"),
    ("cantidad", "Cantidad"),
    ("rotulo_identificacion", "Rótulo de Identificación"),
    ("fecha_fabricacion", "Fecha de Fabricación"),
    ("fecha_vencimiento", "Fecha de Vencimiento"),
    ("fabricante", "Fabricante"),
    ("rotulos_seguridad", "Rótulos de seguridad, sellos y precintos"),
    ("ficha_seguridad", "Ficha de Seguridad"),
    ("certificado_calidad", "Certificado de Calidad"),
    ("golpes_roturas", "Se evidencian Golpes, Roturas u Otros"),
    ("cumple_especificaciones", "Cumple con las especificaciones requeridas"),
]


def cargar_cecif():
    return _load(_CECIF_PATH, _KEY_CECIF)


def guardar_cecif_nuevo(items, datos):
    """Append a new CECIF checklist record and persist. Returns the new record."""
    nuevo = {
        "id": next_id(items),
        "fecha_creacion": datetime.now().isoformat(timespec="seconds"),
        "fecha_recepcion": datos.get("fecha_recepcion", ""),
        "id_proveedor": datos.get("id_proveedor"),
        "no_orden_compra": datos.get("no_orden_compra", ""),
        "id_sustancia": datos.get("id_sustancia"),
        "lote": datos.get("lote", ""),
        "cantidad": datos.get("cantidad", ""),
        "observacion_producto": datos.get("observacion_producto", ""),
        "verificacion": datos.get("verificacion", {}),
        "observaciones": datos.get("observaciones", ""),
        "id_usuario_aprobo": datos.get("id_usuario_aprobo"),
        "id_usuario_verifico": datos.get("id_usuario_verifico"),
    }
    items.append(nuevo)
    _save(_CECIF_PATH, _KEY_CECIF, items)
    return nuevo


# ---------------------------------------------------------------------------
# Cliente checklist
# ---------------------------------------------------------------------------

VERIFICACION_NUEVAS_CAMPOS = [
    ("nombre", "Nombre"),
    ("no_lote", "No. de Lote"),
    ("cantidad", "Cantidad"),
    ("rotulo_identificacion", "Rótulo de Identificación"),
    ("fecha_fabricacion", "Fecha de Fabricación"),
    ("fecha_vencimiento", "Fecha de Vencimiento"),
    ("fabricante", "Fabricante"),
    ("rotulos_seguridad", "Rótulos de seguridad"),
    ("ficha_seguridad", "Ficha de Seguridad"),
    ("certificado_calidad", "Certificado de Calidad"),
    ("golpes_roturas", "Se evidencian Golpes, Roturas u Otros"),
    ("cumple_especificaciones", "Cumple con las especificaciones requeridas"),
]

VERIFICACION_DESTAPADAS_CAMPOS = [
    ("nombre", "Nombre"),
    ("no_lote", "No. de Lote"),
    ("rotulo_identificacion", "Rótulo de Identificación"),
    ("fecha_vencimiento", "Fecha de Vencimiento"),
    ("certificado_calidad", "Certificado de Calidad"),
    ("ficha_seguridad", "Ficha de Seguridad"),
    ("golpes_roturas", "Se evidencian Golpes, Roturas u Otros"),
    ("condiciones_almacenamiento", "¿Cumple condiciones de Almacenamiento?"),
    ("carta_correo", "Carta o correo de envío por parte del cliente"),
]


def cargar_clientes():
    return _load(_CLIENTES_PATH, _KEY_CLIENTES)


def guardar_cliente_nuevo(items, datos):
    """Append a new Cliente checklist record and persist. Returns the new record."""
    nuevo = {
        "id": next_id(items),
        "fecha_creacion": datetime.now().isoformat(timespec="seconds"),
        "fecha_recepcion": datos.get("fecha_recepcion", ""),
        "nombre_cliente": datos.get("nombre_cliente", ""),
        "id_sustancia": datos.get("id_sustancia"),
        "cantidad": datos.get("cantidad", ""),
        "observacion_producto": datos.get("observacion_producto", ""),
        "verificacion_nuevas": datos.get("verificacion_nuevas", {}),
        "verificacion_destapadas": datos.get("verificacion_destapadas", {}),
        "observaciones": datos.get("observaciones", ""),
        "id_usuario_reviso": datos.get("id_usuario_reviso"),
        "id_usuario_verifico": datos.get("id_usuario_verifico"),
    }
    items.append(nuevo)
    _save(_CLIENTES_PATH, _KEY_CLIENTES, items)
    return nuevo
