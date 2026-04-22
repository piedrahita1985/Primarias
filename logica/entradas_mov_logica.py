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
    for key in ["lote", "catalogo", "potencia", "factura", "observaciones"]:
        if key in out:
            out[key] = _normalize_text(out.get(key))
    return out


def cargar():
    return common.cargar_entradas()


def agregar(record, usuario="SISTEMA"):
    rows = cargar()
    nuevo = {"id": common.next_id(rows), "estado": "ACTIVA", **_normalize_record_fields(record)}
    rows.append(nuevo)
    common.guardar_entradas(rows)
    inv.guardar_snapshot()
    bit.registrar_campos(
        tipo_operacion="ENTRADAS-CREAR",
        id_registro=nuevo.get("id"),
        usuario=usuario,
        cambios=[{"campo": "REGISTRO", "valor_anterior": "", "valor_nuevo": "CREADO"}],
    )
    return nuevo


def actualizar(id_entrada, cambios, usuario="SISTEMA"):
    cambios = _normalize_record_fields(cambios)
    rows = cargar()
    old = None
    updated = None
    for r in rows:
        if r.get("id") == id_entrada:
            old = dict(r)
            r.update(cambios)
            updated = dict(r)
            break
    common.guardar_entradas(rows)
    inv.guardar_snapshot()
    cambios_log = []
    if old is not None and updated is not None:
        keys = sorted(set(old.keys()) | set(updated.keys()))
        for k in keys:
            old_v = old.get(k)
            new_v = updated.get(k)
            if str(old_v) != str(new_v):
                cambios_log.append({"campo": k, "valor_anterior": old_v, "valor_nuevo": new_v})
    bit.registrar_campos("ENTRADAS-EDITAR", id_entrada, usuario=usuario, cambios=cambios_log)


def anular(id_entrada, usuario="SISTEMA"):
    entradas = cargar()
    salidas = common.cargar_salidas()

    for e in entradas:
        if e.get("id") == id_entrada:
            e["estado"] = "ANULADA"
            break

    # Si se anula la entrada, se anulan salidas asociadas para consistencia kardex.
    for s in salidas:
        if s.get("id_entrada") == id_entrada:
            s["estado"] = "ANULADA"

    common.guardar_entradas(entradas)
    common.guardar_salidas(salidas)
    inv.guardar_snapshot()
    bit.registrar_campos(
        "ENTRADAS-ANULAR",
        id_entrada,
        usuario=usuario,
        cambios=[
            {"campo": "estado", "valor_anterior": "ACTIVA", "valor_nuevo": "ANULADA"},
            {"campo": "salidas_asociadas", "valor_anterior": "ACTIVAS", "valor_nuevo": "ANULADAS"},
        ],
    )


def ultimas_15(maestras):
    rows = sorted(cargar(), key=lambda x: x.get("id", 0), reverse=True)[:15]
    return enriquecer(rows, maestras)


def filtrar(fecha="", fecha_desde="", fecha_hasta="", codigo="", lote="", maestras=None):
    maestras = maestras or common.cargar_maestras()
    rows = cargar()
    sust_by_id = common.map_by_id(maestras["sustancias"])

    out = []
    codigo = str(codigo).strip()
    lote = str(lote).strip().upper()
    fecha = str(fecha).strip()
    fecha_desde = str(fecha_desde).strip()
    fecha_hasta = str(fecha_hasta).strip()

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
            "codigo": s.get("codigo", ""),
            "nombre": s.get("nombre", ""),
            "unidad_nombre": u.get("unidad", ""),
        })
    return out


def total_salidas_activas(id_entrada):
    salidas = common.cargar_salidas()
    total = 0.0
    for s in salidas:
        if s.get("estado", "ACTIVA") != "ACTIVA":
            continue
        if s.get("id_entrada") == id_entrada:
            total += common.to_float(s.get("cantidad"))
    return total
