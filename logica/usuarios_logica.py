import json

from app_paths import resource_path

_DATA_PATH = resource_path("data", "usuarios.json")
_KEY = "usuarios"

_DEFAULT_PERMISOS = {
    "entradas": True,
    "salidas": True,
    "inventario": True,
    "bitacora": True,
    "prestamos": True,
    "sustancias": True,
    "tipos_entrada": True,
    "tipos_salida": True,
    "fabricantes": True,
    "unidades": True,
    "ubicaciones": True,
    "condiciones": True,
    "colores": True,
    "usuarios": True,
    "firma_path": "",
    "firma_password": "",
}


def _normalizar(r: dict) -> dict:
    src_permisos = r.get("permisos", {}) if isinstance(r.get("permisos", {}), dict) else {}
    permisos = dict(_DEFAULT_PERMISOS)
    permisos.update(src_permisos)

    # Compatibilidad con estructura anterior de permisos.
    if "stock" in src_permisos:
        permisos["inventario"] = bool(src_permisos.get("stock"))
    if "auditoria" in src_permisos:
        permisos["bitacora"] = bool(src_permisos.get("auditoria"))

    return {
        "id": r.get("id"),
        "usuario": r.get("usuario") or r.get("nombre", ""),
        "contrasena": r.get("contrasena") or r.get("contraseña", ""),
        "nombre": r.get("nombre", ""),
        "rol": r.get("rol", ""),
        "permisos": permisos,
        "estado": r.get("estado", "HABILITADA"),
    }


def cargar() -> list:
    with open(_DATA_PATH, "r", encoding="utf-8") as f:
        datos = json.load(f)
    registros = [_normalizar(r) for r in datos.get(_KEY, [])]
    return registros


def _guardar(registros: list):
    records = [
        "  " + json.dumps(r, ensure_ascii=False, separators=(", ", ": "))
        for r in registros
    ]
    with open(_DATA_PATH, "w", encoding="utf-8") as f:
        if records:
            f.write("{ \"usuarios\": [\n")
            f.write(",\n".join(records))
            f.write("\n] }\n")
        else:
            f.write("{ \"usuarios\": [] }\n")


def agregar(registros: list, datos: dict) -> dict:
    max_id = max((r["id"] for r in registros), default=0)
    nuevo = _normalizar({"id": max_id + 1, "estado": "HABILITADA", **datos})
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
