from datetime import datetime
import json

from app_paths import resource_path
from logica import bitacora_logica as bit
from logica import movimientos_common as common
from logica import salidas_mov_logica as sal
from logica import usuarios_logica as usr

PRESTAMOS_PATH = resource_path("data", "prestamos.json")
RECIBOS_PATH = resource_path("data", "recibos.json")


def _normalize_obs(value):
    txt = str(value or "").replace("\n", " ").strip()
    while "  " in txt:
        txt = txt.replace("  ", " ")
    return txt.upper()


def _load_json_safe(path, key):
    try:
        text = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return []
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    return data.get(key, []) if isinstance(data, dict) else []


def _save_compact(path, key, items):
    records = [
        "  " + json.dumps(item, ensure_ascii=False, separators=(", ", ": "))
        for item in items
    ]
    with open(path, "w", encoding="utf-8") as f:
        if records:
            f.write('{ "' + key + '\": [\n')
            f.write(",\n".join(records))
            f.write("\n] }\n")
        else:
            f.write('{ "' + key + '\": [] }\n')


def cargar_prestamos():
    rows = _load_json_safe(PRESTAMOS_PATH, "prestamos")
    for r in rows:
        r.setdefault("estado", "PENDIENTE")
    return rows


def guardar_prestamos(rows):
    _save_compact(PRESTAMOS_PATH, "prestamos", rows)


def cargar_recibos():
    return _load_json_safe(RECIBOS_PATH, "recibos")


def guardar_recibos(rows):
    _save_compact(RECIBOS_PATH, "recibos", rows)


def usuarios_habilitados():
    return [u for u in usr.cargar() if u.get("estado", "HABILITADA") == "HABILITADA"]


def codigos_con_stock(maestras):
    return sal.codigos_con_stock_disponible(maestras)


def lotes_disponibles(id_sustancia):
    return sal.lotes_disponibles_por_sustancia(id_sustancia)


def _tipo_salida_prestamo_id(maestras):
    for r in maestras.get("tipos_salida", []):
        nombre = str(r.get("tipo_salida", "")).strip().upper()
        if nombre in {"PRESTAMO", "PRÉSTAMO"}:
            return r.get("id")
    return None


def crear_prestamo(datos, usuario_presta="SISTEMA"):
    rows = cargar_prestamos()
    now_txt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nuevo = {
        "id": common.next_id(rows),
        "fecha_creacion": now_txt,
        "fecha_prestamo": datos.get("fecha_prestamo", datetime.now().strftime("%Y-%m-%d")),
        "id_sustancia": datos.get("id_sustancia"),
        "id_entrada": datos.get("id_entrada"),
        "id_unidad": datos.get("id_unidad"),
        "cantidad": float(datos.get("cantidad", 0)),
        "id_usuario_presta": datos.get("id_usuario_presta"),
        "id_usuario_destino": datos.get("id_usuario_destino"),
        "firma_presta_path": datos.get("firma_presta_path", ""),
        "observacion": _normalize_obs(datos.get("observacion", "")),
        "estado": "PENDIENTE",
    }
    rows.append(nuevo)
    guardar_prestamos(rows)

    bit.registrar_campos(
        tipo_operacion="PRESTAMO-CREAR",
        id_registro=nuevo.get("id"),
        usuario=usuario_presta,
        cambios=[{"campo": "estado", "valor_anterior": "", "valor_nuevo": "PENDIENTE"}],
    )
    return nuevo


def _enriquecer_prestamo(prestamo, maestras, usuarios_by_id):
    sust_by_id = common.map_by_id(maestras.get("sustancias", []))
    uni_by_id = common.map_by_id(maestras.get("unidades", []))
    sust = sust_by_id.get(prestamo.get("id_sustancia"), {})
    uni = uni_by_id.get(prestamo.get("id_unidad"), {})
    presta = usuarios_by_id.get(prestamo.get("id_usuario_presta"), {})
    destino = usuarios_by_id.get(prestamo.get("id_usuario_destino"), {})
    return {
        **prestamo,
        "codigo": sust.get("codigo", ""),
        "nombre": sust.get("nombre", ""),
        "lote": _lote_por_entrada(prestamo.get("id_entrada")),
        "unidad": uni.get("unidad", ""),
        "usuario_presta_nombre": presta.get("nombre") or presta.get("usuario", ""),
        "usuario_destino_nombre": destino.get("nombre") or destino.get("usuario", ""),
    }


def _lote_por_entrada(id_entrada):
    for e in common.cargar_entradas():
        if e.get("id") == id_entrada:
            return e.get("lote", "")
    return ""


def meses_prestamos_emitidos(id_usuario):
    rows = [r for r in cargar_prestamos() if r.get("id_usuario_presta") == id_usuario]
    meses = set()
    for r in rows:
        fecha = str(r.get("fecha_prestamo", "")).strip()
        if len(fecha) >= 7 and fecha[4] == "-":
            meses.add(fecha[:7])
    return sorted(meses, reverse=True)


def prestamos_emitidos_por_usuario(id_usuario, maestras, mes="", limit=15):
    usuarios = usuarios_habilitados()
    usuarios_by_id = common.map_by_id(usuarios)
    rows = [r for r in cargar_prestamos() if r.get("id_usuario_presta") == id_usuario]

    mes = str(mes or "").strip()
    if mes:
        rows = [r for r in rows if str(r.get("fecha_prestamo", "")).startswith(mes)]

    rows.sort(key=lambda x: x.get("id", 0), reverse=True)
    if limit is not None and limit > 0:
        rows = rows[:limit]
    return [_enriquecer_prestamo(r, maestras, usuarios_by_id) for r in rows]


def prestamos_pendientes_para_usuario(id_usuario, maestras):
    usuarios = usuarios_habilitados()
    usuarios_by_id = common.map_by_id(usuarios)
    rows = [
        r for r in cargar_prestamos()
        if r.get("id_usuario_destino") == id_usuario and r.get("estado", "PENDIENTE") == "PENDIENTE"
    ]
    rows.sort(key=lambda x: x.get("id", 0), reverse=True)
    return [_enriquecer_prestamo(r, maestras, usuarios_by_id) for r in rows]


def responder_prestamo(id_prestamo, id_usuario_recibe, aceptar, observacion_recibo="", usuario_accion="SISTEMA"):
    prestamos = cargar_prestamos()
    idx = next((i for i, p in enumerate(prestamos) if p.get("id") == id_prestamo), None)
    if idx is None:
        return False, "No se encontró el préstamo seleccionado."

    prestamo = prestamos[idx]
    if prestamo.get("estado", "PENDIENTE") != "PENDIENTE":
        return False, "Este préstamo ya fue respondido."

    if int(prestamo.get("id_usuario_destino") or 0) != int(id_usuario_recibe or 0):
        return False, "El préstamo no corresponde al usuario autenticado."

    if aceptar:
        lotes = sal.lotes_disponibles_por_sustancia(prestamo.get("id_sustancia"))
        lote = next((l for l in lotes if l.get("id_entrada") == prestamo.get("id_entrada")), None)
        disponible = common.to_float(lote.get("disponible") if lote else 0)
        cantidad = common.to_float(prestamo.get("cantidad"))
        if cantidad <= 0:
            return False, "Cantidad de préstamo inválida."
        if disponible < cantidad:
            return False, f"Stock insuficiente para aceptar. Disponible actual: {disponible}"

        maestras = common.cargar_maestras()
        usuarios = usuarios_habilitados()
        usuarios_by_id = common.map_by_id(usuarios)
        presta = usuarios_by_id.get(prestamo.get("id_usuario_presta"), {})
        tipo_salida_id = _tipo_salida_prestamo_id(maestras)

        record_salida = {
            "fecha_salida": datetime.now().strftime("%Y-%m-%d"),
            "id_tipo_salida": tipo_salida_id,
            "id_sustancia": prestamo.get("id_sustancia"),
            "id_entrada": prestamo.get("id_entrada"),
            "id_unidad": prestamo.get("id_unidad"),
            "cantidad": cantidad,
            "actividad": f"PRESTAMO A {(usuarios_by_id.get(id_usuario_recibe, {}).get('usuario') or '').upper()}",
            "observacion": _normalize_obs(
                f"Préstamo aprobado por receptor. Prestador: {presta.get('usuario', '')}. {observacion_recibo}"
            ),
        }
        salida = sal.agregar(record_salida, usuario=usuario_accion)
        id_salida = salida.get("id")
        nuevo_estado = "ACEPTADO"
    else:
        id_salida = None
        nuevo_estado = "RECHAZADO"

    prestamo["estado"] = nuevo_estado
    prestamo["fecha_respuesta"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prestamo["id_usuario_recibe"] = id_usuario_recibe
    guardar_prestamos(prestamos)

    recibos = cargar_recibos()
    recibo = {
        "id": common.next_id(recibos),
        "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "id_prestamo": id_prestamo,
        "id_sustancia": prestamo.get("id_sustancia"),
        "id_usuario_presta": prestamo.get("id_usuario_presta"),
        "id_usuario_recibe": id_usuario_recibe,
        "cantidad": prestamo.get("cantidad"),
        "recibio": bool(aceptar),
        "estado": nuevo_estado,
        "observacion": _normalize_obs(observacion_recibo),
        "id_salida": id_salida,
    }
    recibos.append(recibo)
    guardar_recibos(recibos)

    bit.registrar_campos(
        tipo_operacion="PRESTAMO-RESPUESTA",
        id_registro=id_prestamo,
        usuario=usuario_accion,
        cambios=[{"campo": "estado", "valor_anterior": "PENDIENTE", "valor_nuevo": nuevo_estado}],
    )

    return True, "Préstamo procesado correctamente."
