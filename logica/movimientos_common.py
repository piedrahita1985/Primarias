import json
from collections import defaultdict

from app_paths import resource_path

ENTRADAS_PATH = resource_path("data", "entradas.json")
SALIDAS_PATH = resource_path("data", "salidas.json")
SUSTANCIAS_PATH = resource_path("data", "sustancias.json")
UNIDADES_PATH = resource_path("data", "unidad.json")
UBICACIONES_PATH = resource_path("data", "maestrasUbicaciones.json")
COLORES_PATH = resource_path("data", "color_refuerzo.json")
CONDICIONES_PATH = resource_path("data", "condicion_alm.json")
FABRICANTES_PATH = resource_path("data", "fabricante.json")
BITACORA_PATH = resource_path("data", "bitacora.json")
TIPOS_ENTRADA_PATH = resource_path("data", "tipo_entrada.json")
TIPOS_SALIDA_PATH = resource_path("data", "tipo_salida.json")
INVENTARIO_PATH = resource_path("data", "inventario.json")


def load_json(path, key):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get(key, [])


def save_json(path, key, items):
    compact_files = {
        ENTRADAS_PATH,
        SALIDAS_PATH,
        BITACORA_PATH,
        INVENTARIO_PATH,
    }
    with open(path, "w", encoding="utf-8") as f:
        if path in compact_files:
            records = [
                "  " + json.dumps(item, ensure_ascii=False, separators=(", ", ": "))
                for item in items
            ]
            if records:
                f.write("{ \"" + key + "\": [\n")
                f.write(",\n".join(records))
                f.write("\n] }\n")
            else:
                f.write("{ \"" + key + "\": [] }\n")
        else:
            json.dump({key: items}, f, ensure_ascii=False, indent=2)


def next_id(items):
    return max((i.get("id", 0) for i in items), default=0) + 1


def to_float(value):
    try:
        txt = str(value).replace(",", ".").strip()
        return float(txt) if txt else 0.0
    except (TypeError, ValueError):
        return 0.0


def map_by_id(rows):
    return {r["id"]: r for r in rows if "id" in r}


def map_sustancia_by_codigo(sustancias):
    out = {}
    for s in sustancias:
        codigo = str(s.get("codigo", "")).strip()
        if codigo:
            out[codigo] = s
    return out


def cargar_maestras():
    sustancias = load_json(SUSTANCIAS_PATH, "maestrasSustancias")
    unidades = load_json(UNIDADES_PATH, "unidad")
    ubicaciones = load_json(UBICACIONES_PATH, "maestrasUbicaciones")
    colores = load_json(COLORES_PATH, "color_refuerzo")
    condiciones = load_json(CONDICIONES_PATH, "condicion_alm")
    fabricantes = load_json(FABRICANTES_PATH, "fabricantes")
    tipos_entrada = load_json(TIPOS_ENTRADA_PATH, "tipos_entrada")
    tipos_salida = load_json(TIPOS_SALIDA_PATH, "tipos_salida")

    def activos(rows):
        return [r for r in rows if r.get("estado", "HABILITADA") == "HABILITADA"]

    return {
        "sustancias": activos(sustancias),
        "unidades": activos(unidades),
        "ubicaciones": activos(ubicaciones),
        "colores": activos(colores),
        "condiciones": activos(condiciones),
        "fabricantes": activos(fabricantes),
        "tipos_entrada": activos(tipos_entrada),
        "tipos_salida": activos(tipos_salida),
    }


def cargar_entradas():
    rows = load_json(ENTRADAS_PATH, "entradas")
    for r in rows:
        r.setdefault("estado", "ACTIVA")
    return rows


def guardar_entradas(rows):
    save_json(ENTRADAS_PATH, "entradas", rows)


def cargar_salidas():
    rows = load_json(SALIDAS_PATH, "salidas")
    for r in rows:
        r.setdefault("estado", "ACTIVA")
    return rows


def guardar_salidas(rows):
    save_json(SALIDAS_PATH, "salidas", rows)


def stock_por_entrada(entradas, salidas):
    salidas_acum = defaultdict(float)
    for s in salidas:
        if s.get("estado", "ACTIVA") != "ACTIVA":
            continue
        entrada_id = s.get("id_entrada")
        salidas_acum[entrada_id] += to_float(s.get("cantidad"))

    stock = {}
    for e in entradas:
        if e.get("estado", "ACTIVA") != "ACTIVA":
            continue
        ingreso = to_float(e.get("cantidad"))
        egreso = salidas_acum[e.get("id", -1)]
        stock[e.get("id", -1)] = max(0.0, ingreso - egreso)
    return stock
