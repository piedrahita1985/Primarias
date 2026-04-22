from logica import movimientos_common as common
from logica import bitacora_logica as bit
from logica import inventario_mov_logica as inv


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
    rows = cargar()
    nuevo = {"id": common.next_id(rows), "estado": "ACTIVA", **_normalize_record_fields(record)}
    rows.append(nuevo)
    common.guardar_salidas(rows)
    inv.guardar_snapshot()

    cambios = [
        {"campo": "REGISTRO", "valor_anterior": "", "valor_nuevo": "CREADO"},
        {"campo": "cantidad", "valor_anterior": "0", "valor_nuevo": nuevo.get("cantidad", "")},
    ]
    if nuevo.get("id_entrada") is not None:
        cambios.append({
            "campo": "id_entrada",
            "valor_anterior": "",
            "valor_nuevo": nuevo.get("id_entrada", ""),
        })

    bit.registrar_campos(
        tipo_operacion="SALIDAS-CREAR",
        id_registro=nuevo.get("id"),
        usuario=usuario,
        cambios=cambios,
    )
    return nuevo


def actualizar(id_salida, cambios, usuario="SISTEMA"):
    cambios = _normalize_record_fields(cambios)
    rows = cargar()
    old = None
    updated = None
    for r in rows:
        if r.get("id") == id_salida:
            old = dict(r)
            r.update(cambios)
            updated = dict(r)
            break
    common.guardar_salidas(rows)
    inv.guardar_snapshot()
    cambios_log = []
    if old is not None and updated is not None:
        keys = sorted(set(old.keys()) | set(updated.keys()))
        for k in keys:
            old_v = old.get(k)
            new_v = updated.get(k)
            if str(old_v) != str(new_v):
                cambios_log.append({"campo": k, "valor_anterior": old_v, "valor_nuevo": new_v})
    bit.registrar_campos("SALIDAS-EDITAR", id_salida, usuario=usuario, cambios=cambios_log)


def anular(id_salida, usuario="SISTEMA"):
    rows = cargar()
    for r in rows:
        if r.get("id") == id_salida:
            r["estado"] = "ANULADA"
            break
    common.guardar_salidas(rows)
    inv.guardar_snapshot()
    bit.registrar_campos(
        "SALIDAS-ANULAR",
        id_salida,
        usuario=usuario,
        cambios=[{"campo": "estado", "valor_anterior": "ACTIVA", "valor_nuevo": "ANULADA"}],
    )


def lotes_disponibles_por_sustancia(id_sustancia):
    entradas = common.cargar_entradas()
    salidas = common.cargar_salidas()
    stock = common.stock_por_entrada(entradas, salidas)

    disponibles = []
    for e in entradas:
        if e.get("estado", "ACTIVA") != "ACTIVA":
            continue
        if e.get("id_sustancia") != id_sustancia:
            continue
        disponible = stock.get(e.get("id"), 0.0)
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
    entradas = common.cargar_entradas()
    salidas = common.cargar_salidas()
    stock = common.stock_por_entrada(entradas, salidas)
    sust_by_id = common.map_by_id(maestras["sustancias"])

    codigos = set()
    for e in entradas:
        if e.get("estado", "ACTIVA") != "ACTIVA":
            continue
        if stock.get(e.get("id"), 0.0) <= 0:
            continue
        sust = sust_by_id.get(e.get("id_sustancia"), {})
        codigo = str(sust.get("codigo", "")).strip()
        if codigo:
            codigos.add(codigo)
    return sorted(codigos, key=lambda x: (len(x), x))


def ultimas_15(maestras):
    rows = sorted(cargar(), key=lambda x: x.get("id", 0), reverse=True)[:15]
    return enriquecer(rows, maestras)


def filtrar(fecha="", fecha_desde="", fecha_hasta="", codigo="", lote="", maestras=None):
    maestras = maestras or common.cargar_maestras()
    rows = cargar()
    entradas = common.cargar_entradas()
    ent_by_id = common.map_by_id(entradas)
    sust_by_id = common.map_by_id(maestras["sustancias"])

    out = []
    codigo = str(codigo).strip()
    lote = str(lote).strip().upper()
    fecha = str(fecha).strip()
    fecha_desde = str(fecha_desde).strip()
    fecha_hasta = str(fecha_hasta).strip()

    for s in rows:
        ent = ent_by_id.get(s.get("id_entrada"), {})
        sust = sust_by_id.get(s.get("id_sustancia"), {})
        c = str(sust.get("codigo", ""))
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
    entradas = common.cargar_entradas()
    ent_by_id = common.map_by_id(entradas)
    sust_by_id = common.map_by_id(maestras["sustancias"])
    uni_by_id = common.map_by_id(maestras["unidades"])

    out = []
    for s in rows:
        e = ent_by_id.get(s.get("id_entrada"), {})
        sust = sust_by_id.get(s.get("id_sustancia"), {})
        uni = uni_by_id.get(s.get("id_unidad"), {})
        if not uni:
            uni = uni_by_id.get(e.get("id_unidad"), {})
        out.append({
            **s,
            "codigo": sust.get("codigo", ""),
            "nombre": sust.get("nombre", ""),
            "lote": e.get("lote", ""),
            "unidad_nombre": uni.get("unidad", ""),
        })
    return out
