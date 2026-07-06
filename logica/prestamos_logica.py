"""prestamos_logica.py – Lógica de negocio para el módulo de Préstamos (v2).

Flujo CECIF LE-FC009/04:
  SOLICITADO  →  PRESTADO  →  DEVUELTO
"""
from database import get_db
from logica import bitacora_logica as bit
from logica import movimientos_common as common
from logica import salidas_mov_logica as sal
from logica import usuarios_logica as usr


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def usuarios_habilitados():
    return [u for u in usr.cargar() if u.get("estado", "HABILITADA") == "HABILITADA"]


def codigos_con_stock(maestras):
    return sal.codigos_con_stock_disponible(maestras)


def lotes_disponibles(id_sustancia):
    return sal.lotes_disponibles_por_sustancia(id_sustancia)


def _enriquecer(rows, maestras, usuarios_by_id):
    sust_by_id = common.map_by_id(maestras.get("sustancias", []))
    uni_by_id  = common.map_by_id(maestras.get("unidades",  []))
    out = []
    for r in rows:
        sust  = sust_by_id.get(r.get("id_sustancia"), {})
        uni   = uni_by_id.get(r.get("id_unidad"),   {})
        presta = usuarios_by_id.get(r.get("id_usuario_presta"), {})
        out.append({
            **r,
            "codigo":  r.get("codigo")  or sust.get("codigo",  ""),
            "nombre":  r.get("nombre")  or sust.get("nombre",  ""),
            "unidad":  r.get("unidad")  or uni.get("unidad",   ""),
            "usuario_presta_nombre": (
                r.get("usuario_presta_nombre")
                or presta.get("nombre")
                or presta.get("usuario", "")
            ),
        })
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Consultas
# ─────────────────────────────────────────────────────────────────────────────

def todos_prestamos_activos(maestras):
    """Devuelve SOLICITADO + PRESTADO enriquecidos."""
    db = get_db()
    try:
        rows = db.get_prestamos_activos()
    finally:
        db.close()
    usuarios_by_id = common.map_by_id(usuarios_habilitados())
    return _enriquecer(rows, maestras, usuarios_by_id)


def prestamos_completados(maestras):
    """Devuelve DEVUELTO enriquecidos (historial)."""
    db = get_db()
    try:
        rows = db.get_prestamos_completados()
    finally:
        db.close()
    usuarios_by_id = common.map_by_id(usuarios_habilitados())
    return _enriquecer(rows, maestras, usuarios_by_id)


def cargar_prestamos():
    """Compatibilidad – devuelve todos los préstamos."""
    db = get_db()
    try:
        return db.get_prestamos()
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────────────────────
# Acciones
# ─────────────────────────────────────────────────────────────────────────────

def crear_solicitud(datos, usuario_accion="SISTEMA"):
    """Crea un préstamo en estado SOLICITADO."""
    db = get_db()
    try:
        id_usuario = datos.get("id_usuario") or 0
        nuevo_id = db.crear_prestamo(datos, id_usuario)
        bit.registrar_campos(
            tipo_operacion="PRESTAMO-SOLICITUD",
            id_registro=nuevo_id,
            usuario=usuario_accion,
            cambios=[{"campo": "estado", "valor_anterior": "", "valor_nuevo": "SOLICITADO"}],
        )
        return {"ok": True, "id": nuevo_id}
    finally:
        db.close()


def firmar_entrega(id_prestamo, id_usuario_entregador, firma_path, usuario_accion="SISTEMA"):
    """Firma 'Entregado por' -> SOLICITADO -> PRESTADO."""
    db = get_db()
    try:
        prestamo = next((p for p in db.get_prestamos() if p.get("id") == id_prestamo), None)
        if prestamo is None:
            return False, "Préstamo no encontrado."
        if str(prestamo.get("estado", "")).upper() != "SOLICITADO":
            return False, "El préstamo no está en estado SOLICITADO."
        # El usuario que entrega NO puede ser el mismo que hizo la solicitud
        id_solicitante = int(prestamo.get("id_usuario") or prestamo.get("id_usuario_presta") or 0)
        if id_solicitante and int(id_usuario_entregador or 0) == id_solicitante:
            return False, "El usuario que entrega no puede ser el mismo que realizó la solicitud."
        db.actualizar_prestamo_entrega(id_prestamo, id_usuario_entregador, firma_path)
        bit.registrar_campos(
            tipo_operacion="PRESTAMO-ENTREGA",
            id_registro=id_prestamo,
            usuario=usuario_accion,
            cambios=[{"campo": "estado", "valor_anterior": "SOLICITADO", "valor_nuevo": "PRESTADO"}],
        )
        return True, "Entrega registrada correctamente."
    finally:
        db.close()


def actualizar_detalle(id_prestamo, datos, usuario_accion="SISTEMA"):
    """Guarda campos de uso: fecha_ensayo, análisis, cantidad_mg, firma_analista."""
    db = get_db()
    try:
        prestamo = next((p for p in db.get_prestamos() if p.get("id") == id_prestamo), None)
        if prestamo is None:
            return False, "Préstamo no encontrado."

        cantidad_prestada = common.to_float(prestamo.get("cantidad"))
        cantidad_consumida = datos.get("cantidad_mg")
        if cantidad_consumida is not None:
            cantidad_consumida = common.to_float(cantidad_consumida)
            if cantidad_consumida < 0:
                return False, "La cantidad consumida no puede ser negativa."
            if cantidad_consumida > cantidad_prestada:
                return False, "La cantidad consumida no puede superar la cantidad prestada."

        db.actualizar_prestamo_detalle(id_prestamo, datos)
        bit.registrar_campos(
            tipo_operacion="PRESTAMO-DETALLE",
            id_registro=id_prestamo,
            usuario=usuario_accion,
            cambios=[{"campo": "analisis_realizado",
                      "valor_anterior": "",
                      "valor_nuevo": str(datos.get("analisis_realizado", ""))}],
        )
        return True, "Detalle guardado correctamente."
    finally:
        db.close()


def completar_devolucion(id_prestamo, fecha_devolucion, id_usuario_verificador,
                         firma_verificador, usuario_accion="SISTEMA"):
    """Firma 'Verificado el Recibido' -> PRESTADO -> DEVUELTO."""
    db = get_db()
    try:
        prestamo = next((p for p in db.get_prestamos() if p.get("id") == id_prestamo), None)
        if prestamo is None:
            return False, "Préstamo no encontrado."
        if str(prestamo.get("estado", "")).upper() != "PRESTADO":
            return False, "El préstamo no está en estado PRESTADO."
        db.completar_devolucion_prestamo(
            id_prestamo, fecha_devolucion,
            id_usuario_verificador, firma_verificador,
        )
        bit.registrar_campos(
            tipo_operacion="PRESTAMO-DEVOLUCION",
            id_registro=id_prestamo,
            usuario=usuario_accion,
            cambios=[{"campo": "estado", "valor_anterior": "PRESTADO", "valor_nuevo": "DEVUELTO"}],
        )
        return True, "Devolución registrada correctamente."
    finally:
        db.close()


def recibidos_pendientes_para_usuario(id_usuario, maestras):
    """Filas pendientes por recibir para el usuario destino."""
    db = get_db()
    try:
        rows = db.get_recibidos_pendientes_para(int(id_usuario or 0))
    finally:
        db.close()
    usuarios_by_id = common.map_by_id(usuarios_habilitados())
    return _enriquecer(rows, maestras, usuarios_by_id)


def devoluciones_pendientes_para_usuario(id_usuario, maestras):
    """Filas recibidas y pendientes de devolución para el usuario destino."""
    db = get_db()
    try:
        rows = db.get_devoluciones_pendientes_para(int(id_usuario or 0))
    finally:
        db.close()
    usuarios_by_id = common.map_by_id(usuarios_habilitados())
    return _enriquecer(rows, maestras, usuarios_by_id)


def responder_prestamo(
    id_prestamo,
    id_usuario_recibe,
    aceptar,
    observacion_recibo="",
    usuario_accion="SISTEMA",
):
    """Compatibilidad con UI/recibidos para aceptar/rechazar recepción."""
    db = get_db()
    try:
        ok, msg = db.responder_prestamo(
            id_prestamo=int(id_prestamo or 0),
            id_usuario_recibe=int(id_usuario_recibe or 0),
            aceptar=bool(aceptar),
            observacion_recibo=observacion_recibo,
            id_usuario_accion=int(id_usuario_recibe or 0),
        )
        if ok:
            bit.registrar_campos(
                tipo_operacion="PRESTAMO-RESPUESTA",
                id_registro=int(id_prestamo or 0),
                usuario=usuario_accion,
                cambios=[
                    {
                        "campo": "recepcion",
                        "valor_anterior": "PENDIENTE",
                        "valor_nuevo": "RECIBIDO" if aceptar else "RECHAZADO",
                    }
                ],
            )
        return ok, msg
    finally:
        db.close()


def devolver_prestamo(
    id_prestamo,
    id_usuario_devuelve,
    observacion_devolucion="",
    usuario_accion="SISTEMA",
):
    """Compatibilidad con UI/recibidos para cierre de devolución."""
    db = get_db()
    try:
        ok, msg = db.devolver_prestamo(
            id_prestamo=int(id_prestamo or 0),
            id_usuario_devuelve=int(id_usuario_devuelve or 0),
            observacion_devolucion=observacion_devolucion,
            id_usuario_accion=int(id_usuario_devuelve or 0),
        )
        if ok:
            bit.registrar_campos(
                tipo_operacion="PRESTAMO-DEVOLUCION-RECIBIDOS",
                id_registro=int(id_prestamo or 0),
                usuario=usuario_accion,
                cambios=[
                    {
                        "campo": "devolucion",
                        "valor_anterior": "PENDIENTE",
                        "valor_nuevo": "DEVUELTO",
                    }
                ],
            )
        return ok, msg
    finally:
        db.close()
