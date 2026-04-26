from database import get_db
from logica import bitacora_logica as bit
from logica import movimientos_common as common
from logica import salidas_mov_logica as sal
from logica import usuarios_logica as usr


def _normalize_obs(value):
    txt = str(value or "").replace("\n", " ").strip()
    while "  " in txt:
        txt = txt.replace("  ", " ")
    return txt.upper()


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


def cargar_prestamos():
    db = get_db()
    try:
        return db.get_prestamos()
    finally:
        db.close()


def cargar_recibidos():
    """Alias compatible — devuelve todos los préstamos para que la UI filtre por destino."""
    return cargar_prestamos()


def meses_prestamos_emitidos(id_usuario):
    db = get_db()
    try:
        if hasattr(db, "get_meses_prestamos_emitidos"):
            return db.get_meses_prestamos_emitidos(id_usuario)
        rows = db.get_prestamos_emitidos(id_usuario)
    finally:
        db.close()
    meses = set()
    for r in rows:
        fecha = str(r.get("fecha_prestamo", "")).strip()
        if len(fecha) >= 7 and fecha[4] == "-":
            meses.add(fecha[:7])
    return sorted(meses, reverse=True)


def _enriquecer(rows, maestras, usuarios_by_id):
    sust_by_id = common.map_by_id(maestras.get("sustancias", []))
    uni_by_id = common.map_by_id(maestras.get("unidades", []))
    out = []
    for r in rows:
        sust = sust_by_id.get(r.get("id_sustancia"), {})
        uni = uni_by_id.get(r.get("id_unidad"), {})
        presta = usuarios_by_id.get(r.get("id_usuario_presta"), {})
        destino = usuarios_by_id.get(r.get("id_usuario_destino"), {})
        out.append({
            **r,
            "codigo": r.get("codigo") or sust.get("codigo", ""),
            "nombre": r.get("nombre") or sust.get("nombre", ""),
            "unidad": r.get("unidad") or uni.get("unidad", ""),
            "usuario_presta_nombre": r.get("usuario_presta_nombre") or presta.get("nombre") or presta.get("usuario", ""),
            "usuario_destino_nombre": r.get("usuario_destino_nombre") or destino.get("nombre") or destino.get("usuario", ""),
        })
    return out


def prestamos_emitidos_por_usuario(id_usuario, maestras, mes="", limit=15):
    db = get_db()
    try:
        rows = db.get_prestamos_emitidos(id_usuario)
    finally:
        db.close()

    mes = str(mes or "").strip()
    if mes:
        rows = [r for r in rows if str(r.get("fecha_prestamo", "")).startswith(mes)]
    rows.sort(key=lambda x: x.get("id", 0), reverse=True)
    if limit and limit > 0:
        rows = rows[:limit]

    usuarios_by_id = common.map_by_id(usuarios_habilitados())
    return _enriquecer(rows, maestras, usuarios_by_id)


def prestamos_pendientes_para_usuario(id_usuario, maestras):
    db = get_db()
    try:
        rows = db.get_prestamos_pendientes_para(id_usuario)
    finally:
        db.close()
    usuarios_by_id = common.map_by_id(usuarios_habilitados())
    return _enriquecer(rows, maestras, usuarios_by_id)


def recibidos_pendientes_para_usuario(id_usuario, maestras):
    db = get_db()
    try:
        rows = db.get_recibidos_pendientes_para(id_usuario)
    finally:
        db.close()
    usuarios_by_id = common.map_by_id(usuarios_habilitados())
    return _enriquecer(rows, maestras, usuarios_by_id)


def devoluciones_pendientes_para_usuario(id_usuario, maestras):
    db = get_db()
    try:
        rows = db.get_devoluciones_pendientes_para(id_usuario)
    finally:
        db.close()
    usuarios_by_id = common.map_by_id(usuarios_habilitados())
    return _enriquecer(rows, maestras, usuarios_by_id)


def crear_prestamo(datos, usuario_presta="SISTEMA"):
    db = get_db()
    try:
        id_usuario_presta = datos.get("id_usuario_presta") or 0
        nuevo_id = db.crear_prestamo(datos, id_usuario_presta)
        bit.registrar_campos(
            tipo_operacion="PRESTAMO-CREAR",
            id_registro=nuevo_id,
            usuario=usuario_presta,
            cambios=[{"campo": "estado", "valor_anterior": "", "valor_nuevo": "PENDIENTE"}],
        )
        return {**datos, "id": nuevo_id, "estado": "PENDIENTE"}
    finally:
        db.close()


def responder_prestamo(id_prestamo, id_usuario_recibe, aceptar, observacion_recibo="", usuario_accion="SISTEMA"):
    db = get_db()
    try:
        prestamos = db.get_prestamos()
        prestamo = next((p for p in prestamos if p.get("id") == id_prestamo), None)
        if prestamo is None:
            return False, "No se encontró el préstamo seleccionado."

        if prestamo.get("estado", "PENDIENTE") != "PENDIENTE":
            return False, "Este préstamo ya fue respondido."

        if int(prestamo.get("id_usuario_destino") or 0) != int(id_usuario_recibe or 0):
            return False, "El préstamo no corresponde al usuario autenticado."

        id_salida = None
        if aceptar:
            lotes = sal.lotes_disponibles_por_sustancia(prestamo.get("id_sustancia"))
            lote = next((l for l in lotes if l.get("id_entrada") == prestamo.get("id_entrada")), None)
            disponible = common.to_float(lote.get("disponible") if lote else 0)
            cantidad = common.to_float(prestamo.get("cantidad"))
            if cantidad <= 0:
                return False, "Cantidad de préstamo inválida."
            if disponible < cantidad:
                return False, f"Stock insuficiente. Disponible: {disponible}"

            maestras = common.cargar_maestras()
            usuarios_by_id = common.map_by_id(usuarios_habilitados())
            presta = usuarios_by_id.get(prestamo.get("id_usuario_presta"), {})
            tipo_salida_id = _tipo_salida_prestamo_id(maestras)

            record_salida = {
                "fecha_salida": __import__("datetime").datetime.now().strftime("%Y-%m-%d"),
                "id_tipo_salida": tipo_salida_id,
                "id_sustancia": prestamo.get("id_sustancia"),
                "id_entrada": prestamo.get("id_entrada"),
                "id_inventario": prestamo.get("id_entrada"),
                "id_unidad": prestamo.get("id_unidad"),
                "cantidad": cantidad,
                "actividad": f"PRESTAMO A {(usuarios_by_id.get(id_usuario_recibe, {}).get('usuario') or '').upper()}",
                "observacion": _normalize_obs(
                    f"Préstamo aprobado por receptor. Prestador: {presta.get('usuario', '')}. {observacion_recibo}"
                ),
            }
            salida = sal.agregar(record_salida, usuario=usuario_accion)
            id_salida = salida.get("id")

        db.responder_prestamo(
            id_prestamo=id_prestamo,
            id_usuario_recibe=id_usuario_recibe,
            aceptar=aceptar,
            obs=_normalize_obs(observacion_recibo),
            id_salida=id_salida,
        )

        nuevo_estado = "RECIBIDO" if aceptar else "RECHAZADO"
        bit.registrar_campos(
            tipo_operacion="PRESTAMO-RESPUESTA",
            id_registro=id_prestamo,
            usuario=usuario_accion,
            cambios=[{"campo": "estado", "valor_anterior": "PENDIENTE", "valor_nuevo": nuevo_estado}],
        )
        return True, "Préstamo procesado correctamente."
    finally:
        db.close()


def devolver_prestamo(id_prestamo, id_usuario_devuelve, observacion_devolucion="", usuario_accion="SISTEMA"):
    db = get_db()
    try:
        prestamos = db.get_prestamos()
        prestamo = next((p for p in prestamos if p.get("id") == id_prestamo), None)
        if prestamo is None:
            return False, "No se encontró el préstamo."

        if str(prestamo.get("estado_recepcion", "")).upper() != "RECIBIDO":
            return False, "El préstamo aún no ha sido recibido oficialmente."

        if str(prestamo.get("estado_devolucion", "")).upper() == "DEVUELTO":
            return False, "Este préstamo ya fue devuelto."

        if int(prestamo.get("id_usuario_destino") or 0) != int(id_usuario_devuelve or 0):
            return False, "La devolución no corresponde al usuario autenticado."

        cantidad = common.to_float(prestamo.get("cantidad"))
        if cantidad <= 0:
            return False, "Cantidad de devolución inválida."

        db.devolver_prestamo(
            id_prestamo=id_prestamo,
            id_usuario_devuelve=id_usuario_devuelve,
            obs=_normalize_obs(observacion_devolucion),
        )
        # Reintegrar stock
        id_entrada = prestamo.get("id_entrada") or prestamo.get("id_inventario")
        if id_entrada:
            inventario = db.get_inventario()
            entrada = next((e for e in inventario if e.get("id") == id_entrada), None)
            if entrada:
                nueva_cantidad = round(common.to_float(entrada.get("cantidad_actual", entrada.get("cantidad", 0))) + cantidad, 4)
                db.actualizar_stock(id_entrada, nueva_cantidad)

        bit.registrar_campos(
            tipo_operacion="PRESTAMO-DEVOLUCION",
            id_registro=id_prestamo,
            usuario=usuario_accion,
            cambios=[
                {"campo": "estado", "valor_anterior": "RECIBIDO", "valor_nuevo": "DEVUELTO"},
            ],
        )
        return True, "Devolución registrada correctamente."
    finally:
        db.close()

