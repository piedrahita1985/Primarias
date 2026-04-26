from database import get_db


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
    db = get_db()
    try:
        return db.get_check_cecif()
    finally:
        db.close()


def guardar_cecif_nuevo(items, datos):
    """Append a new CECIF checklist record and persist. Returns the new record."""
    id_usuario = datos.get("id_usuario_verifico") or datos.get("id_usuario_aprobo") or 0
    db = get_db()
    try:
        nuevo_id = db.crear_check_cecif(datos, id_usuario)
        nuevo = {**datos, "id": nuevo_id}
        items.append(nuevo)
        return nuevo
    finally:
        db.close()


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
    db = get_db()
    try:
        return db.get_check_clientes()
    finally:
        db.close()


def guardar_cliente_nuevo(items, datos):
    """Append a new Cliente checklist record and persist. Returns the new record."""
    id_usuario = datos.get("id_usuario_verifico") or datos.get("id_usuario_reviso") or 0
    db = get_db()
    try:
        nuevo_id = db.crear_check_cliente(datos, id_usuario)
        nuevo = {**datos, "id": nuevo_id}
        items.append(nuevo)
        return nuevo
    finally:
        db.close()

