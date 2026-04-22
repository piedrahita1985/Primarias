import json
from collections import defaultdict
from datetime import date, datetime

from app_paths import resource_path

_ENTRADAS_PATH = resource_path("data", "entradas.json")
_SALIDAS_PATH = resource_path("data", "salidas.json")
_SUSTANCIAS_PATH = resource_path("data", "sustancias.json")
_UNIDADES_PATH = resource_path("data", "unidad.json")
_UBICACIONES_PATH = resource_path("data", "maestrasUbicaciones.json")
_COLORES_PATH = resource_path("data", "color_refuerzo.json")
_CONDICIONES_PATH = resource_path("data", "condicion_alm.json")
_FABRICANTES_PATH = resource_path("data", "fabricante.json")


def _load(path, key):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get(key, [])


def _save(path, key, items):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({key: items}, f, ensure_ascii=False, indent=2)


def _next_id(items):
    return max((i.get("id", 0) for i in items), default=0) + 1


def _to_float(value):
    try:
        txt = str(value).replace(",", ".").strip()
        return float(txt) if txt else 0.0
    except (TypeError, ValueError):
        return 0.0


def cargar_entradas():
    return _load(_ENTRADAS_PATH, "entradas")


def cargar_salidas():
    return _load(_SALIDAS_PATH, "salidas")


def guardar_entradas(items):
    _save(_ENTRADAS_PATH, "entradas", items)


def guardar_salidas(items):
    _save(_SALIDAS_PATH, "salidas", items)


def cargar_maestras():
    sustancias = _load(_SUSTANCIAS_PATH, "maestrasSustancias")
    unidades = _load(_UNIDADES_PATH, "unidad")
    ubicaciones = _load(_UBICACIONES_PATH, "maestrasUbicaciones")
    colores = _load(_COLORES_PATH, "color_refuerzo")
    condiciones = _load(_CONDICIONES_PATH, "condicion_alm")
    fabricantes = _load(_FABRICANTES_PATH, "fabricantes")

    # Solo opciones activas (si el campo existe)
    def _activos(rows):
        return [r for r in rows if r.get("estado", "HABILITADA") == "HABILITADA"]

    return {
        "sustancias": _activos(sustancias),
        "unidades": _activos(unidades),
        "ubicaciones": _activos(ubicaciones),
        "colores": _activos(colores),
        "condiciones": condiciones,
        "fabricantes": _activos(fabricantes),
    }


def agregar_entrada(record):
    entradas = cargar_entradas()
    nuevo = {"id": _next_id(entradas), **record}
    entradas.append(nuevo)
    guardar_entradas(entradas)
    return nuevo


def agregar_salida(record):
    salidas = cargar_salidas()
    nuevo = {"id": _next_id(salidas), **record}
    salidas.append(nuevo)
    guardar_salidas(salidas)
    return nuevo


def map_by_id(rows):
    return {r["id"]: r for r in rows if "id" in r}


def map_sustancia_by_codigo(sustancias):
    out = {}
    for s in sustancias:
        codigo = str(s.get("codigo", "")).strip()
        if codigo:
            out[codigo] = s
    return out


def stock_por_entrada(entradas, salidas):
    salidas_acum = defaultdict(float)
    for s in salidas:
        entrada_id = s.get("id_entrada")
        salidas_acum[entrada_id] += _to_float(s.get("cantidad"))

    stock = {}
    for e in entradas:
        ingreso = _to_float(e.get("cantidad"))
        egreso = salidas_acum[e.get("id", -1)]
        stock[e.get("id", -1)] = max(0.0, ingreso - egreso)
    return stock


def lotes_disponibles_por_sustancia(id_sustancia):
    entradas = cargar_entradas()
    salidas = cargar_salidas()
    stock = stock_por_entrada(entradas, salidas)

    disponibles = []
    for e in entradas:
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


def sugerir_unidad_id(id_sustancia):
    entradas = cargar_entradas()
    for e in sorted(entradas, key=lambda x: x.get("id", 0), reverse=True):
        if e.get("id_sustancia") == id_sustancia and e.get("id_unidad"):
            return e.get("id_unidad")
    return None


def construir_inventario():
    maestras = cargar_maestras()
    entradas = cargar_entradas()
    salidas = cargar_salidas()

    sustancias_by_id = map_by_id(maestras["sustancias"])
    unidades_by_id = map_by_id(maestras["unidades"])
    ubicaciones_by_id = map_by_id(maestras["ubicaciones"])
    colores_by_id = map_by_id(maestras["colores"])
    condiciones_by_id = map_by_id(maestras["condiciones"])

    stock = stock_por_entrada(entradas, salidas)

    rows = []
    for e in entradas:
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

    rows.sort(key=lambda r: (str(r.get("codigo", "")), str(r.get("lote", ""))))
    return rows
