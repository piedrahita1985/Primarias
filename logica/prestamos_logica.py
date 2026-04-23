from datetime import datetime
import json

from app_paths import resource_path
from logica import bitacora_logica as bit
from logica import inventario_mov_logica as inv
from logica import movimientos_common as common
from logica import salidas_mov_logica as sal
from logica import usuarios_logica as usr

PRESTAMOS_PATH = resource_path("data", "prestamos.json")
RECIBIDOS_PATH = resource_path("data", "recibidos.json")
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


def _normalize_estado_recepcion(value):
    estado = str(value or "").strip().upper()
    if estado in {"ACEPTADO", "RECIBIDO"}:
        return "RECIBIDO"
    if estado == "RECHAZADO":
        return "RECHAZADO"
    return "PENDIENTE"


def _recibido_from_legacy(row):
    prestamo = next((p for p in cargar_prestamos() if p.get("id") == row.get("id_prestamo")), {})
    estado_recepcion = _normalize_estado_recepcion(row.get("estado"))
    estado_devolucion = "PENDIENTE" if estado_recepcion == "RECIBIDO" else "NO_APLICA"
    return {
        "id": row.get("id"),
        "id_prestamo": row.get("id_prestamo"),
        "id_sustancia": row.get("id_sustancia") or prestamo.get("id_sustancia"),
        "id_entrada": prestamo.get("id_entrada"),
        "id_unidad": prestamo.get("id_unidad"),
        "id_usuario_presta": row.get("id_usuario_presta") or prestamo.get("id_usuario_presta"),
        "id_usuario_destino": row.get("id_usuario_recibe") or prestamo.get("id_usuario_destino"),
        "cantidad": row.get("cantidad") or prestamo.get("cantidad"),
        "estado_recepcion": estado_recepcion,
        "fecha_recepcion": row.get("fecha", "") if estado_recepcion == "RECIBIDO" else "",
        "observacion_recepcion": row.get("observacion", ""),
        "estado_devolucion": estado_devolucion,
        "fecha_devolucion": "",
        "observacion_devolucion": "",
        "id_salida_prestamo": row.get("id_salida"),
    }


def cargar_recibidos():
    rows = _load_json_safe(RECIBIDOS_PATH, "recibidos")
    if rows:
        return rows
    legacy = cargar_recibos()
    if legacy:
        normalized = [_recibido_from_legacy(r) for r in legacy]
        guardar_recibidos(normalized)
        return normalized
    return []


def guardar_recibidos(rows):
    _save_compact(RECIBIDOS_PATH, "recibidos", rows)


def _crear_recibido_pendiente(prestamo):
    return {
        "id": None,
        "id_prestamo": prestamo.get("id"),
        "id_sustancia": prestamo.get("id_sustancia"),
        "id_entrada": prestamo.get("id_entrada"),
        "id_unidad": prestamo.get("id_unidad"),
        "id_usuario_presta": prestamo.get("id_usuario_presta"),
        "id_usuario_destino": prestamo.get("id_usuario_destino"),
        "cantidad": prestamo.get("cantidad"),
        "estado_recepcion": "PENDIENTE",
        "fecha_recepcion": "",
        "observacion_recepcion": "",
        "estado_devolucion": "NO_APLICA",
        "fecha_devolucion": "",
        "observacion_devolucion": "",
        "id_salida_prestamo": None,
    }


def _ensure_recibido(rows, prestamo):
    recibido = next((r for r in rows if r.get("id_prestamo") == prestamo.get("id")), None)
    if recibido is not None:
        return recibido
    recibido = _crear_recibido_pendiente(prestamo)
    recibido["id"] = common.next_id(rows)
    rows.append(recibido)
    return recibido


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
    recibidos = cargar_recibidos()
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
    recibido = _crear_recibido_pendiente(nuevo)
    recibido["id"] = common.next_id(recibidos)
    recibidos.append(recibido)
    guardar_recibidos(recibidos)

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


def _enriquecer_recibido(recibido, maestras, usuarios_by_id):
    sust_by_id = common.map_by_id(maestras.get("sustancias", []))
    uni_by_id = common.map_by_id(maestras.get("unidades", []))
    sust = sust_by_id.get(recibido.get("id_sustancia"), {})
    uni = uni_by_id.get(recibido.get("id_unidad"), {})
    presta = usuarios_by_id.get(recibido.get("id_usuario_presta"), {})
    destino = usuarios_by_id.get(recibido.get("id_usuario_destino"), {})
    return {
        **recibido,
        "codigo": sust.get("codigo", ""),
        "nombre": sust.get("nombre", ""),
        "lote": _lote_por_entrada(recibido.get("id_entrada")),
        "unidad": uni.get("unidad", ""),
        "usuario_presta_nombre": presta.get("nombre") or presta.get("usuario", ""),
        "usuario_destino_nombre": destino.get("nombre") or destino.get("usuario", ""),
    }


def recibidos_pendientes_para_usuario(id_usuario, maestras):
    usuarios = usuarios_habilitados()
    usuarios_by_id = common.map_by_id(usuarios)
    rows = [
        r for r in cargar_recibidos()
        if r.get("id_usuario_destino") == id_usuario
        and _normalize_estado_recepcion(r.get("estado_recepcion")) == "PENDIENTE"
    ]
    rows.sort(key=lambda x: x.get("id", 0), reverse=True)
    return [_enriquecer_recibido(r, maestras, usuarios_by_id) for r in rows]


def devoluciones_pendientes_para_usuario(id_usuario, maestras):
    usuarios = usuarios_habilitados()
    usuarios_by_id = common.map_by_id(usuarios)
    rows = [
        r for r in cargar_recibidos()
        if r.get("id_usuario_destino") == id_usuario
        and _normalize_estado_recepcion(r.get("estado_recepcion")) == "RECIBIDO"
        and str(r.get("estado_devolucion", "")).strip().upper() == "PENDIENTE"
    ]
    rows.sort(key=lambda x: x.get("id", 0), reverse=True)
    return [_enriquecer_recibido(r, maestras, usuarios_by_id) for r in rows]


def responder_prestamo(id_prestamo, id_usuario_recibe, aceptar, observacion_recibo="", usuario_accion="SISTEMA"):
    prestamos = cargar_prestamos()
    recibidos = cargar_recibidos()
    idx = next((i for i, p in enumerate(prestamos) if p.get("id") == id_prestamo), None)
    if idx is None:
        return False, "No se encontró el préstamo seleccionado."

    prestamo = prestamos[idx]
    if prestamo.get("estado", "PENDIENTE") != "PENDIENTE":
        return False, "Este préstamo ya fue respondido."

    recibido = _ensure_recibido(recibidos, prestamo)

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
        nuevo_estado = "RECIBIDO"
    else:
        id_salida = None
        nuevo_estado = "RECHAZADO"

    prestamo["estado"] = nuevo_estado
    prestamo["fecha_respuesta"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prestamo["id_usuario_recibe"] = id_usuario_recibe
    guardar_prestamos(prestamos)

    recibido["id_sustancia"] = prestamo.get("id_sustancia")
    recibido["id_entrada"] = prestamo.get("id_entrada")
    recibido["id_unidad"] = prestamo.get("id_unidad")
    recibido["id_usuario_presta"] = prestamo.get("id_usuario_presta")
    recibido["id_usuario_destino"] = id_usuario_recibe
    recibido["cantidad"] = prestamo.get("cantidad")
    recibido["estado_recepcion"] = nuevo_estado
    recibido["fecha_recepcion"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S") if aceptar else ""
    recibido["observacion_recepcion"] = _normalize_obs(observacion_recibo)
    recibido["estado_devolucion"] = "PENDIENTE" if aceptar else "NO_APLICA"
    recibido["id_salida_prestamo"] = id_salida
    guardar_recibidos(recibidos)

    bit.registrar_campos(
        tipo_operacion="PRESTAMO-RESPUESTA",
        id_registro=id_prestamo,
        usuario=usuario_accion,
        cambios=[{"campo": "estado", "valor_anterior": "PENDIENTE", "valor_nuevo": nuevo_estado}],
    )

    return True, "Préstamo procesado correctamente."


def devolver_prestamo(id_prestamo, id_usuario_devuelve, observacion_devolucion="", usuario_accion="SISTEMA"):
    prestamos = cargar_prestamos()
    recibidos = cargar_recibidos()

    prestamo = next((p for p in prestamos if p.get("id") == id_prestamo), None)
    if prestamo is None:
        return False, "No se encontró el préstamo seleccionado."

    recibido = next((r for r in recibidos if r.get("id_prestamo") == id_prestamo), None)
    if recibido is None:
        return False, "No existe registro de recibido para este préstamo."

    if int(recibido.get("id_usuario_destino") or 0) != int(id_usuario_devuelve or 0):
        return False, "La devolución no corresponde al usuario autenticado."

    if _normalize_estado_recepcion(recibido.get("estado_recepcion")) != "RECIBIDO":
        return False, "El préstamo aún no ha sido recibido oficialmente."

    if str(recibido.get("estado_devolucion", "")).strip().upper() == "DEVUELTO":
        return False, "Este préstamo ya fue devuelto."

    cantidad = common.to_float(recibido.get("cantidad") or prestamo.get("cantidad"))
    if cantidad <= 0:
        return False, "Cantidad de devolución inválida."

    entradas = common.cargar_entradas()
    entrada = next((e for e in entradas if e.get("id") == prestamo.get("id_entrada")), None)
    if entrada is None:
        return False, "No se encontró la entrada original del préstamo."

    cantidad_anterior = common.to_float(entrada.get("cantidad"))
    entrada["cantidad"] = round(cantidad_anterior + cantidad, 4)
    common.guardar_entradas(entradas)
    inv.guardar_snapshot()

    prestamo["estado"] = "DEVUELTO"
    prestamo["fecha_devolucion"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    prestamo["id_usuario_devuelve"] = id_usuario_devuelve
    guardar_prestamos(prestamos)

    recibido["estado_devolucion"] = "DEVUELTO"
    recibido["fecha_devolucion"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    recibido["observacion_devolucion"] = _normalize_obs(observacion_devolucion)
    guardar_recibidos(recibidos)

    bit.registrar_campos(
        tipo_operacion="PRESTAMO-DEVOLUCION",
        id_registro=id_prestamo,
        usuario=usuario_accion,
        cambios=[
            {"campo": "estado", "valor_anterior": "RECIBIDO", "valor_nuevo": "DEVUELTO"},
            {"campo": "cantidad_entrada", "valor_anterior": cantidad_anterior, "valor_nuevo": entrada.get("cantidad")},
        ],
    )
    return True, "Devolución registrada correctamente."
