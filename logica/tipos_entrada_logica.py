from database import get_db


def cargar() -> list:
    db = get_db()
    try:
        return db.get_tipos_entrada()
    finally:
        db.close()


def agregar(registros: list, datos: dict) -> dict:
    db = get_db()
    try:
        tipo = datos.get("tipo_entrada", "")
        nuevo_id = db.crear_tipo_entrada(tipo)
        nuevo = {"id": nuevo_id, "tipo_entrada": tipo, "estado": "HABILITADA"}
        registros.append(nuevo)
        return nuevo
    finally:
        db.close()


def actualizar(registros: list, id_: int, datos: dict):
    db = get_db()
    try:
        tipo = datos.get("tipo_entrada", "")
        estado = datos.get("estado", "HABILITADA")
        db.actualizar_tipo_entrada(id_, tipo, estado)
        for r in registros:
            if r["id"] == id_:
                r.update(datos)
                break
    finally:
        db.close()


def habilitar(registros: list, id_: int):
    db = get_db()
    try:
        db.habilitar_tipo_entrada(id_)
        for r in registros:
            if r["id"] == id_:
                r["estado"] = "HABILITADA"
                break
    finally:
        db.close()


def inhabilitar(registros: list, id_: int):
    db = get_db()
    try:
        db.inhabilitar_tipo_entrada(id_)
        for r in registros:
            if r["id"] == id_:
                r["estado"] = "INHABILITADA"
                break
    finally:
        db.close()
