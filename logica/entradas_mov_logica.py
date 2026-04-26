from database import get_db
from logica import movimientos_common as common
from logica import bitacora_logica as bit


def _normalize_text(value):
    txt = str(value or "").replace("\n", " ").strip()
    while "  " in txt:
        txt = txt.replace("  ", " ")
    return txt.upper()


def _normalize_record_fields(record):
    out = dict(record)
    for key in ["lote", "catalogo", "potencia", "factura", "observaciones"]:
        if key in out:
            out[key] = _normalize_text(out.get(key))
    return out


def cargar():
    return common.cargar_entradas()


def agregar(record, usuario="SISTEMA"):
    record = _normalize_record_fields(record)
    db = get_db()
    try:
        nuevo_id = db.crear_inventario(record)
        bit.registrar_campos(
            tipo_operacion="ENTRADAS-CREAR",
            id_registro=nuevo_id,
            usuario=usuario,
            cambios=[{"campo": "REGISTRO", "valor_anterior": "", "valor_nuevo": "CREADO"}],
        )
        return {**record, "id": nuevo_id, "estado": "ACTIVA"}
    finally:
        db.close()


def actualizar(id_entrada, cambios, usuario="SISTEMA"):
    cambios = _normalize_record_fields(cambios)
    db = get_db()
    try:
        rows = db.get_inventario()
        old = next((r for r in rows if r.get("id") == id_entrada), None)
        db.actualizar_inventario(id_entrada, cambios)
        updated = {**(old or {}), **cambios}
        cambios_log = []
        if old:
            for k in sorted(set(old.keys()) | set(cambios.keys())):
                ov = old.get(k)
                nv = cambios.get(k, ov)
                if str(ov) != str(nv):
                    cambios_log.append({"campo": k, "valor_anterior": ov, "valor_nuevo": nv})
        bit.registrar_campos("ENTRADAS-EDITAR", id_entrada, usuario=usuario, cambios=cambios_log)
    finally:
        db.close()


def anular(id_entrada, usuario="SISTEMA"):
    db = get_db()
    try:
        db.anular_inventario(id_entrada)
        # Anular salidas asociadas
        salidas = db.get_salidas()
        for s in salidas:
            if s.get("id_inventario") == id_entrada or s.get("id_entrada") == id_entrada:
                if s.get("estado", "ACTIVA") == "ACTIVA":
                    db.anular_salida(s["id"])
        bit.registrar_campos(
            "ENTRADAS-ANULAR",
            id_entrada,
            usuario=usuario,
            cambios=[
                {"campo": "estado", "valor_anterior": "ACTIVA", "valor_nuevo": "ANULADA"},
                {"campo": "salidas_asociadas", "valor_anterior": "ACTIVAS", "valor_nuevo": "ANULADAS"},
            ],
        )
    finally:
        db.close()


def ultimas_15(maestras):
    db = get_db()
    try:
        rows = db.get_inventario()
    finally:
        db.close()
    rows = sorted(rows, key=lambda x: x.get("id", 0), reverse=True)[:15]
    return enriquecer(rows, maestras)


def filtrar(fecha="", fecha_desde="", fecha_hasta="", codigo="", lote="", maestras=None):
    maestras = maestras or common.cargar_maestras()
    db = get_db()
    try:
        rows = db.get_inventario()
    finally:
        db.close()

    sust_by_id = common.map_by_id(maestras["sustancias"])
    codigo = str(codigo).strip()
    lote = str(lote).strip().upper()
    fecha = str(fecha).strip()
    fecha_desde = str(fecha_desde).strip()
    fecha_hasta = str(fecha_hasta).strip()

    out = []
    for e in rows:
        sust = sust_by_id.get(e.get("id_sustancia"), {})
        c = str(sust.get("codigo", ""))
        fecha_row = str(e.get("fecha_entrada", ""))
        if fecha and fecha_row != fecha:
            continue
        if fecha_desde and fecha_row and fecha_row < fecha_desde:
            continue
        if fecha_hasta and fecha_row and fecha_row > fecha_hasta:
            continue
        if codigo and not c.startswith(codigo):
            continue
        if lote and lote not in str(e.get("lote", "")).upper():
            continue
        out.append(e)

    out.sort(key=lambda x: x.get("id", 0), reverse=True)
    return enriquecer(out, maestras)


def enriquecer(rows, maestras):
    sust_by_id = common.map_by_id(maestras["sustancias"])
    uni_by_id = common.map_by_id(maestras["unidades"])

    out = []
    for e in rows:
        s = sust_by_id.get(e.get("id_sustancia"), {})
        u = uni_by_id.get(e.get("id_unidad"), {})
        out.append({
            **e,
            "codigo": e.get("codigo") or s.get("codigo", ""),
            "nombre": e.get("nombre") or s.get("nombre", ""),
            "unidad_nombre": e.get("unidad") or u.get("unidad", ""),
        })
    return out


def total_salidas_activas(id_entrada):
    db = get_db()
    try:
        salidas = db.get_salidas()
    finally:
        db.close()
    total = 0.0
    for s in salidas:
        if s.get("estado", "ACTIVA") != "ACTIVA":
            continue
        if s.get("id_inventario") == id_entrada or s.get("id_entrada") == id_entrada:
            total += common.to_float(s.get("cantidad"))
    return total
