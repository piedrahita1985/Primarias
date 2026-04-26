from database import get_db


def cargar() -> list:
    db = get_db()
    try:
        return db.get_fabricantes()
    finally:
        db.close()


def agregar(registros: list, datos: dict) -> dict:
    db = get_db()
    try:
        nombre = datos.get("fabricante", "")
        nuevo_id = db.crear_fabricante(nombre)
        nuevo = {"id": nuevo_id, "fabricante": nombre, "estado": "HABILITADA"}
        registros.append(nuevo)
        return nuevo
    finally:
        db.close()


def actualizar(registros: list, id_: int, datos: dict):
    db = get_db()
    try:
        db.actualizar_fabricante(id_, datos.get("fabricante", ""))
        for r in registros:
            if r["id"] == id_:
                r.update(datos)
                break
    finally:
        db.close()


def habilitar(registros: list, id_: int):
    db = get_db()
    try:
        db.habilitar_fabricante(id_)
        for r in registros:
            if r["id"] == id_:
                r["estado"] = "HABILITADA"
                break
    finally:
        db.close()


def inhabilitar(registros: list, id_: int):
    db = get_db()
    try:
        db.inhabilitar_fabricante(id_)
        for r in registros:
            if r["id"] == id_:
                r["estado"] = "INHABILITADA"
                break
    finally:
        db.close()
