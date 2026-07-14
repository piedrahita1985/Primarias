from database import get_db, EPSILON_STOCK


def to_float(value):
    try:
        txt = str(value).replace(",", ".").strip()
        return float(txt) if txt else 0.0
    except (TypeError, ValueError):
        return 0.0


def map_by_id(rows):
    return {r["id"]: r for r in rows if "id" in r}


def texto_envases(cantidad_envases: float) -> str:
    """Desglosa una cantidad de envases (parte entera + iniciado) en texto,
    ej. '5 envases y 1 iniciado'. cantidad_envases ya debe venir en envases
    (no dividir de nuevo por presentacion)."""
    completos = int(cantidad_envases)
    fraccion = cantidad_envases - completos
    if fraccion > 0.001:
        if completos == 0:
            return "1 iniciado"
        elif completos == 1:
            return "1 envase y 1 iniciado"
        return f"{completos} envases y 1 iniciado"
    if completos == 0:
        return ""
    elif completos == 1:
        return "1 envase"
    return f"{completos} envases"


def map_sustancia_by_codigo(sustancias):
    out = {}
    for s in sustancias:
        codigo = str(s.get("codigo", "")).strip()
        if codigo:
            out[codigo] = s
    return out


def cargar_maestras():
    db = get_db()
    try:
        sustancias  = db.get_sustancias()
        unidades    = db.get_unidades()
        ubicaciones = db.get_ubicaciones()
        colores     = db.get_colores()
        condiciones = db.get_condiciones()
        fabricantes = db.get_fabricantes()
        tipos_entrada = db.get_tipos_entrada()
        tipos_salida  = db.get_tipos_salida()
    finally:
        db.close()

    def habilitados(rows):
        return [r for r in rows if r.get("estado", "HABILITADA") == "HABILITADA"]

    return {
        "sustancias":    habilitados(sustancias),
        "unidades":      habilitados(unidades),
        "ubicaciones":   habilitados(ubicaciones),
        "colores":       habilitados(colores),
        "condiciones":   habilitados(condiciones),
        "fabricantes":   habilitados(fabricantes),
        "tipos_entrada": habilitados(tipos_entrada),
        "tipos_salida":  habilitados(tipos_salida),
    }


def cargar_entradas():
    """Devuelve la lista de items de inventario (equivale al antiguo entradas.json)."""
    db = get_db()
    try:
        return db.get_inventario()
    finally:
        db.close()


def guardar_entradas(rows):
    """No-op: en DB el guardado se hace por registro individual."""
    pass


def cargar_salidas():
    db = get_db()
    try:
        return db.get_salidas()
    finally:
        db.close()


def guardar_salidas(rows):
    """No-op: en DB el guardado se hace por registro individual."""
    pass


def next_id(items):
    """Compatibilidad: genera un ID secuencial a partir de una lista."""
    return max((i.get("id", 0) for i in items), default=0) + 1


def stock_por_entrada(entradas, salidas):
    """
    Devuelve {id_inventario: cantidad_actual}.
    En DB ya tenemos cantidad_actual en cada item de inventario.
    """
    return {r["id"]: to_float(r.get("cantidad_actual", r.get("cantidad", 0)))
            for r in entradas}
