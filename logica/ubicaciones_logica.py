from database import get_db

SUFIJOS = {"FREEZER": "F", "NEVERA": "N", "CABINA": "C"}


def cargar() -> list:
    db = get_db()
    try:
        return db.get_ubicaciones()
    finally:
        db.close()


def agregar(registros: list, datos: dict) -> dict:
    db = get_db()
    try:
        ubicacion = datos.get("ubicacion", "")
        no_caja = datos.get("no_caja", "")
        nuevo_id = db.crear_ubicacion(ubicacion, no_caja)
        nuevo = {"id": nuevo_id, "ubicacion": ubicacion, "no_caja": no_caja, "estado": "HABILITADA"}
        registros.append(nuevo)
        return nuevo
    finally:
        db.close()


def actualizar(registros: list, id_: int, datos: dict):
    db = get_db()
    try:
        db.actualizar_ubicacion(id_, datos.get("ubicacion", ""), datos.get("no_caja", ""))
        for r in registros:
            if r["id"] == id_:
                r.update(datos)
                break
    finally:
        db.close()


def habilitar(registros: list, id_: int):
    db = get_db()
    try:
        db.habilitar_ubicacion(id_)
        for r in registros:
            if r["id"] == id_:
                r["estado"] = "HABILITADA"
                break
    finally:
        db.close()


def inhabilitar(registros: list, id_: int):
    db = get_db()
    try:
        db.inhabilitar_ubicacion(id_)
        for r in registros:
            if r["id"] == id_:
                r["estado"] = "INHABILITADA"
                break
    finally:
        db.close()
