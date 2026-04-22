import json

from app_paths import resource_path

_DATA_PATH = resource_path("data", "unidad.json")
_KEY = "unidad"


def cargar() -> list:
    with open(_DATA_PATH, "r", encoding="utf-8") as f:
        datos = json.load(f)
    registros = datos.get(_KEY, [])
    for r in registros:
        r.setdefault("estado", "HABILITADA")
    return registros


def _guardar(registros: list):
    with open(_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump({_KEY: registros}, f, ensure_ascii=False, indent=2)


def agregar(registros: list, datos: dict) -> dict:
    max_id = max((r["id"] for r in registros), default=0)
    nuevo = {"id": max_id + 1, "estado": "HABILITADA", **datos}
    registros.append(nuevo)
    _guardar(registros)
    return nuevo


def actualizar(registros: list, id_: int, datos: dict):
    for r in registros:
        if r["id"] == id_:
            r.update(datos)
            break
    _guardar(registros)


def habilitar(registros: list, id_: int):
    for r in registros:
        if r["id"] == id_:
            r["estado"] = "HABILITADA"
            break
    _guardar(registros)


def inhabilitar(registros: list, id_: int):
    for r in registros:
        if r["id"] == id_:
            r["estado"] = "INHABILITADA"
            break
    _guardar(registros)
