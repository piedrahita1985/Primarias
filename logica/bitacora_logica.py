from datetime import datetime

from logica import movimientos_common as common


def registrar(modulo, accion, id_registro, detalle="", usuario="SISTEMA"):
    tipo = f"{str(modulo).upper()}-{str(accion).upper()}"
    registrar_campos(
        tipo_operacion=tipo,
        id_registro=id_registro,
        usuario=usuario,
        cambios=[{"campo": "DETALLE", "valor_anterior": "", "valor_nuevo": detalle}],
    )


def registrar_campos(tipo_operacion, id_registro, usuario="SISTEMA", cambios=None):
    cambios = cambios or []
    if not cambios:
        cambios = [{"campo": "REGISTRO", "valor_anterior": "", "valor_nuevo": "SIN CAMBIOS"}]

    rows = cargar()
    now_txt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for c in cambios:
        rows.append({
            "id": common.next_id(rows),
            "fecha_hora": now_txt,
            "usuario": usuario,
            "tipo_operacion": str(tipo_operacion).upper(),
            "id_registro": id_registro,
            "campo": str(c.get("campo", "")),
            "valor_anterior": str(c.get("valor_anterior", "")),
            "valor_nuevo": str(c.get("valor_nuevo", "")),
        })
    guardar(rows)


def cargar():
    rows = common.load_json(common.BITACORA_PATH, "bitacora")
    out = []
    for r in rows:
        if "tipo_operacion" in r:
            out.append(r)
            continue
        tipo = f"{str(r.get('modulo', '')).upper()}-{str(r.get('accion', '')).upper()}".strip("-")
        out.append({
            "id": r.get("id"),
            "fecha_hora": r.get("fecha_hora", ""),
            "usuario": r.get("usuario", ""),
            "tipo_operacion": tipo,
            "id_registro": r.get("id_registro", ""),
            "campo": "DETALLE",
            "valor_anterior": "",
            "valor_nuevo": r.get("detalle", ""),
        })
    return out


def guardar(rows):
    common.save_json(common.BITACORA_PATH, "bitacora", rows)


def ultimos_200():
    rows = sorted(cargar(), key=lambda x: x.get("id", 0), reverse=True)
    return rows[:200]


def filtrar(desde="", hasta="", usuario="", tipo_operacion="", id_registro=""):
    rows = cargar()
    out = []

    desde = (desde or "").strip()
    hasta = (hasta or "").strip()
    usuario = (usuario or "").strip().upper()
    tipo_operacion = (tipo_operacion or "").strip().upper()
    id_registro = str(id_registro or "").strip()

    for r in rows:
        fecha_hora = str(r.get("fecha_hora", ""))
        fecha = fecha_hora[:10] if len(fecha_hora) >= 10 else ""

        if desde and fecha and fecha < desde:
            continue
        if hasta and fecha and fecha > hasta:
            continue
        if usuario and usuario not in str(r.get("usuario", "")).upper():
            continue
        if tipo_operacion and tipo_operacion not in str(r.get("tipo_operacion", "")).upper():
            continue
        if id_registro and id_registro != str(r.get("id_registro", "")):
            continue
        out.append(r)

    out.sort(key=lambda x: x.get("id", 0), reverse=True)
    return out
