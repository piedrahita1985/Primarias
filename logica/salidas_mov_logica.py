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


def _resolver_id_usuario(db, usuario: str) -> int:
    usuario_txt = str(usuario or "").strip()
    if usuario_txt:
        usuarios = db.get_usuarios()
        exacto = next((u for u in usuarios if str(u.get("usuario", "")).strip() == usuario_txt), None)
        if exacto:
            return exacto["id"]
        por_nombre = next((u for u in usuarios if str(u.get("nombre", "")).strip() == usuario_txt), None)
        if por_nombre:
            return por_nombre["id"]

    usuarios = db.get_usuarios()
    habilitado = next((u for u in usuarios if str(u.get("estado", "HABILITADA")) == "HABILITADA"), None)
    if habilitado:
        return habilitado["id"]
    if usuarios:
        return usuarios[0]["id"]
    raise ValueError("No hay usuarios registrados para asociar el movimiento de salida.")


def agregar(record, usuario="SISTEMA"):
    record = _normalize_record_fields(record)
    db = get_db()
    try:
        # id_usuario puede venir en el record o derivarse de usuario
        id_usuario = record.pop("id_usuario", None) or _resolver_id_usuario(db, usuario)
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
    """Actualiza una salida, incluyendo cantidad y/o lote. Valida el stock
    disponible ANTES de mutar nada (para no dejar el stock en un estado
    intermedio si la validacion falla), y reconcilia el stock entre el lote
    original y el nuevo si la salida se mueve de lote."""
    cambios = _normalize_record_fields(cambios)
    db = get_db()
    try:
        rows = db.get_salidas()
        old = next((r for r in rows if r.get("id") == id_salida), None)

        salida = db.get_salida(id_salida)
        if not salida:
            raise ValueError("No se encontro la salida a actualizar.")
        if str(salida.get("estado", "")).upper() == "ANULADA":
            raise ValueError("No se puede editar una salida anulada.")

        id_inv_orig = salida["id_inventario"]
        id_inv_nuevo = cambios.get("id_inventario") or cambios.get("id_entrada") or id_inv_orig
        cantidad_orig = common.to_float(salida.get("cantidad"))
        cantidad_nueva = (
            common.to_float(cambios["cantidad"]) if cambios.get("cantidad") is not None else cantidad_orig
        )

        stock_destino_leido = db.get_stock_actual(id_inv_nuevo)
        if stock_destino_leido is None:
            raise ValueError("No se encontro el lote de inventario indicado.")
        disponible_destino = stock_destino_leido
        if id_inv_nuevo == id_inv_orig:
            # La cantidad de la salida original "vuelve" a estar disponible
            # para efectos de esta validacion (se esta reemplazando, no sumando).
            disponible_destino += cantidad_orig

        if cantidad_nueva > disponible_destino + common.EPSILON_STOCK:
            raise ValueError(
                f"Stock insuficiente en el lote seleccionado. "
                f"Disponible: {round(disponible_destino, 4)}"
            )

        # Validacion superada: recien ahora se muta el stock. valor_esperado
        # protege cada escritura contra otra operacion concurrente sobre el
        # mismo lote (ver actualizar_stock); si el lote cambio entre la
        # lectura de arriba y este punto, se aborta con un error claro en vez
        # de sobrescribir en silencio el cambio de la otra operacion.
        if id_inv_nuevo == id_inv_orig:
            db.actualizar_stock(
                id_inv_orig, max(0.0, disponible_destino - cantidad_nueva),
                valor_esperado=stock_destino_leido,
            )
        else:
            stock_orig = db.get_stock_actual(id_inv_orig) or 0
            db.actualizar_stock(id_inv_orig, stock_orig + cantidad_orig, valor_esperado=stock_orig)
            db.actualizar_stock(
                id_inv_nuevo, max(0.0, disponible_destino - cantidad_nueva),
                valor_esperado=stock_destino_leido,
            )

        db.actualizar_salida(id_salida, {
            "id_inventario": id_inv_nuevo,
            "id_tipo_salida": cambios.get("id_tipo_salida") or salida["id_tipo_salida"],
            "cantidad": cantidad_nueva,
            "actividad": cambios.get("actividad"),
            "observacion": cambios.get("observacion"),
            "fecha_salida": cambios.get("fecha_salida"),
            "factura": cambios.get("factura"),
        })

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


def anular_con_conexion(db, id_salida):
    """Anula una salida y restaura el stock, reutilizando una conexion (db)
    ya abierta por el llamador -- evita abrir una segunda conexion cuando se
    anula en cascada (ej. desde entradas_mov_logica.anular())."""
    salida = db.get_salida(id_salida)
    if not salida or str(salida.get("estado", "")).upper() == "ANULADA":
        return
    db.marcar_salida_anulada(id_salida)
    stock_actual = db.get_stock_actual(salida["id_inventario"])
    if stock_actual is not None:
        db.actualizar_stock(
            salida["id_inventario"], stock_actual + common.to_float(salida.get("cantidad")),
            valor_esperado=stock_actual,
        )


def anular(id_salida, usuario="SISTEMA"):
    db = get_db()
    try:
        anular_con_conexion(db, id_salida)
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
        cantidad_envases = common.to_float(e.get("cantidad_actual", e.get("cantidad", 0)))
        if cantidad_envases <= 0:
            continue
        presentacion = common.to_float(e.get("presentacion") or 1) or 1
        disponible_contenido = round(cantidad_envases * presentacion, 4)
        disponibles.append({
            "id_entrada": e.get("id"),
            "lote": e.get("lote", ""),
            "catalogo": e.get("catalogo", ""),
            "disponible": disponible_contenido,
            "presentacion": presentacion,
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
        presentacion = float(e.get("presentacion") or 1) or 1
        cantidad_display = round(float(s.get("cantidad", 0)) * presentacion, 4)
        out.append({
            **s,
            "codigo": s.get("codigo") or sust.get("codigo", ""),
            "nombre": s.get("nombre") or sust.get("nombre", ""),
            "lote": s.get("lote") or e.get("lote", ""),
            "unidad_nombre": s.get("unidad") or uni.get("unidad", ""),
            "cantidad_display": cantidad_display,
        })
    return out


