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
    for key in ["actividad", "observacion"]:
        if key in out:
            out[key] = _normalize_text(out.get(key))
    return out


def cargar():
    return common.cargar_salidas()


def agregar(record, usuario="SISTEMA"):
    record = _normalize_record_fields(record)
    db = get_db()
    try:
        # id_usuario puede venir en el record o derivarse de usuario
        id_usuario = record.pop("id_usuario", None) or 0
        nuevo_id = db.crear_salida(record, id_usuario)
        resumen = f"cant={record.get('cantidad', '')} | entrada={record.get('id_entrada', record.get('id_inventario', ''))}"
        bit.registrar_campos(
            tipo_operacion="SALIDAS-CREAR",
            id_registro=nuevo_id,
            usuario=usuario,
            cambios=[{"campo": "REGISTRO", "valor_anterior": "", "valor_nuevo": f"CREADO | {resumen}"}],
        )
        return {**record, "id": nuevo_id, "estado": "ACTIVA"}
    finally:
        db.close()


def actualizar(id_salida, cambios, usuario="SISTEMA"):
    cambios = _normalize_record_fields(cambios)
    db = get_db()
    try:
        rows = db.get_salidas()
        old = next((r for r in rows if r.get("id") == id_salida), None)
        db.actualizar_salida(id_salida, cambios)
        cambios_log = []
        if old:
            for k in sorted(set(old.keys()) | set(cambios.keys())):
                ov = old.get(k)
                nv = cambios.get(k, ov)
                if str(ov) != str(nv):
                    cambios_log.append({"campo": k, "valor_anterior": ov, "valor_nuevo": nv})
        bit.registrar_campos("SALIDAS-EDITAR", id_salida, usuario=usuario, cambios=cambios_log)
    finally:
        db.close()


def anular(id_salida, usuario="SISTEMA"):
    db = get_db()
    try:
        db.anular_salida(id_salida)
        bit.registrar_campos(
            "SALIDAS-ANULAR",
            id_salida,
            usuario=usuario,
            cambios=[{"campo": "estado", "valor_anterior": "ACTIVA", "valor_nuevo": "ANULADA"}],
        )
    finally:
        db.close()


def lotes_disponibles_por_sustancia(id_sustancia):
    db = get_db()
    try:
        entradas = db.get_inventario()
    finally:
        db.close()

    disponibles = []
    for e in entradas:
        if e.get("estado", "ACTIVA") != "ACTIVA":
            continue
        if e.get("id_sustancia") != id_sustancia:
            continue
        disponible = common.to_float(e.get("cantidad_actual", e.get("cantidad", 0)))
        if disponible <= 0:
            continue
        disponibles.append({
            "id_entrada": e.get("id"),
            "lote": e.get("lote", ""),
            "catalogo": e.get("catalogo", ""),
            "disponible": round(disponible, 4),
            "id_unidad": e.get("id_unidad"),
        })
    return disponibles


def codigos_con_stock_disponible(maestras):
    db = get_db()
    try:
        entradas = db.get_inventario()
    finally:
        db.close()
    sust_by_id = common.map_by_id(maestras["sustancias"])

    codigos = set()
    for e in entradas:
        if e.get("estado", "ACTIVA") != "ACTIVA":
            continue
        if common.to_float(e.get("cantidad_actual", e.get("cantidad", 0))) <= 0:
            continue
        sust = sust_by_id.get(e.get("id_sustancia"), {})
        codigo = str(sust.get("codigo", e.get("codigo", ""))).strip()
        if codigo:
            codigos.add(codigo)
    return sorted(codigos, key=lambda x: (len(x), x))


def ultimas_15(maestras):
    db = get_db()
    try:
        rows = db.get_salidas()
    finally:
        db.close()
    rows = sorted(rows, key=lambda x: x.get("id", 0), reverse=True)[:15]
    return enriquecer(rows, maestras)


def filtrar(fecha="", fecha_desde="", fecha_hasta="", codigo="", lote="", maestras=None):
    maestras = maestras or common.cargar_maestras()
    db = get_db()
    try:
        rows = db.get_salidas()
        entradas = db.get_inventario()
    finally:
        db.close()

    ent_by_id = common.map_by_id(entradas)
    sust_by_id = common.map_by_id(maestras["sustancias"])
    codigo = str(codigo).strip()
    lote = str(lote).strip().upper()
    fecha = str(fecha).strip()
    fecha_desde = str(fecha_desde).strip()
    fecha_hasta = str(fecha_hasta).strip()

    out = []
    for s in rows:
        ent_id = s.get("id_inventario") or s.get("id_entrada")
        ent = ent_by_id.get(ent_id, {})
        sust = sust_by_id.get(s.get("id_sustancia") or ent.get("id_sustancia"), {})
        c = str(sust.get("codigo", s.get("codigo", "")))
        fecha_row = str(s.get("fecha_salida", ""))
        if fecha and fecha_row != fecha:
            continue
        if fecha_desde and fecha_row and fecha_row < fecha_desde:
            continue
        if fecha_hasta and fecha_row and fecha_row > fecha_hasta:
            continue
        if codigo and not c.startswith(codigo):
            continue
        if lote and lote not in str(ent.get("lote", "")).upper():
            continue
        out.append(s)

    out.sort(key=lambda x: x.get("id", 0), reverse=True)
    return enriquecer(out, maestras)


def enriquecer(rows, maestras):
    db = get_db()
    try:
        entradas = db.get_inventario()
    finally:
        db.close()
    ent_by_id = common.map_by_id(entradas)
    sust_by_id = common.map_by_id(maestras["sustancias"])
    uni_by_id = common.map_by_id(maestras["unidades"])

    out = []
    for s in rows:
        ent_id = s.get("id_inventario") or s.get("id_entrada")
        e = ent_by_id.get(ent_id, {})
        sust = sust_by_id.get(s.get("id_sustancia") or e.get("id_sustancia"), {})
        uni = uni_by_id.get(s.get("id_unidad") or e.get("id_unidad"), {})
        out.append({
            **s,
            "codigo": s.get("codigo") or sust.get("codigo", ""),
            "nombre": s.get("nombre") or sust.get("nombre", ""),
            "lote": s.get("lote") or e.get("lote", ""),
            "unidad_nombre": s.get("unidad") or uni.get("unidad", ""),
        })
    return out


