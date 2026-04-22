from datetime import date, datetime

from logica import movimientos_common as common


def sugerir_unidad_id(id_sustancia):
    entradas = common.cargar_entradas()
    for e in sorted(entradas, key=lambda x: x.get("id", 0), reverse=True):
        if e.get("estado", "ACTIVA") != "ACTIVA":
            continue
        if e.get("id_sustancia") == id_sustancia and e.get("id_unidad"):
            return e.get("id_unidad")
    return None


def construir_inventario():
    maestras = common.cargar_maestras()
    entradas = common.cargar_entradas()
    salidas = common.cargar_salidas()

    sustancias_by_id = common.map_by_id(maestras["sustancias"])
    unidades_by_id = common.map_by_id(maestras["unidades"])
    ubicaciones_by_id = common.map_by_id(maestras["ubicaciones"])
    colores_by_id = common.map_by_id(maestras["colores"])
    condiciones_by_id = common.map_by_id(maestras["condiciones"])

    stock = common.stock_por_entrada(entradas, salidas)

    rows = []
    for e in entradas:
        if e.get("estado", "ACTIVA") != "ACTIVA":
            continue

        s = sustancias_by_id.get(e.get("id_sustancia"), {})
        u = unidades_by_id.get(e.get("id_unidad"), {})
        ub = ubicaciones_by_id.get(e.get("id_ubicacion"), {})
        c = colores_by_id.get(e.get("id_color_refuerzo"), {})
        ca = condiciones_by_id.get(e.get("id_condicion_alm"), {})

        fecha_v = str(e.get("fecha_vencimiento", "")).strip()
        alarma_fv = ""
        if fecha_v:
            try:
                fv = datetime.strptime(fecha_v, "%Y-%m-%d").date()
                if fv < date.today():
                    alarma_fv = "VENCIDO"
                elif (fv - date.today()).days <= 30:
                    alarma_fv = "PROXIMO A VENCER"
                else:
                    alarma_fv = "OK"
            except ValueError:
                alarma_fv = ""

        rows.append({
            "id_entrada": e.get("id"),
            "codigo": s.get("codigo", ""),
            "propiedad": s.get("propiedad", ""),
            "tipo_muestras": s.get("tipo_muestras", ""),
            "uso_previsto": s.get("uso_previsto", ""),
            "no_caja": ub.get("no_caja", ""),
            "ubicacion": ub.get("ubicacion", ""),
            "condicion_alm": ca.get("condicion", ""),
            "nombre": s.get("nombre", ""),
            "potencia": e.get("potencia", ""),
            "lote": e.get("lote", ""),
            "catalogo": e.get("catalogo", ""),
            "fecha_ingreso": e.get("fecha_entrada", ""),
            "fecha_vencimiento": e.get("fecha_vencimiento", ""),
            "alarma_fv": alarma_fv,
            "unidad": u.get("unidad", ""),
            "presentacion": e.get("presentacion", ""),
            "cantidad_minima": s.get("cantidad_minima", ""),
            "color_refuerzo": c.get("color_refuerzo", ""),
            "certificado_anl": "SI" if e.get("certificado_anl") else "NO",
            "ficha_seguridad": "SI" if e.get("ficha_seguridad") else "NO",
            "factura_compra": "SI" if e.get("factura_compra") else "NO",
            "codigo_sistema": s.get("codigo_sistema", ""),
            "stock": round(stock.get(e.get("id"), 0.0), 4),
        })

        cant_min = common.to_float(s.get("cantidad_minima"))
        current_stock = common.to_float(rows[-1].get("stock"))
        if cant_min > 0 and current_stock < cant_min:
            rows[-1]["alarma_stock"] = "BAJO MINIMO"
        else:
            rows[-1]["alarma_stock"] = "OK"

    rows.sort(key=lambda r: (str(r.get("codigo", "")), str(r.get("lote", ""))))
    return rows


def guardar_snapshot():
    rows = construir_inventario()
    common.save_json(common.INVENTARIO_PATH, "inventario", rows)
    return rows


def cargar_snapshot():
    rows = common.load_json(common.INVENTARIO_PATH, "inventario")
    if not rows:
        rows = guardar_snapshot()
    return rows
