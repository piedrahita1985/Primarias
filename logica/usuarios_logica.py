from database import get_db
import auth


def cargar() -> list:
    db = get_db()
    try:
        return db.get_usuarios()
    finally:
        db.close()


def autenticar(usuario: str, contrasena: str):
    """Valida credenciales contra la BD (verificacion de hash + migracion
    perezosa de cuentas legadas). Devuelve el usuario normalizado o None."""
    db = get_db()
    try:
        return db.get_usuario_login(usuario, contrasena)
    finally:
        db.close()


def verificar_firma_password(user: dict, ingresada: str) -> bool:
    """Verifica la contrasena de firma de 'user' (ya cargado en memoria)."""
    firma_pass = (user or {}).get("permisos", {}).get("firma_password", "")
    return auth.verify_password(ingresada, firma_pass)


def agregar(registros: list, datos: dict) -> dict:
    db = get_db()
    try:
        nuevo_id = db.crear_usuario(datos)
        # Re-fetch full normalized user from DB
        todos = db.get_usuarios()
        nuevo = next((u for u in todos if u["id"] == nuevo_id), None)
        if nuevo:
            registros.append(nuevo)
            return nuevo
        return {**datos, "id": nuevo_id}
    finally:
        db.close()


def actualizar(registros: list, id_: int, datos: dict):
    db = get_db()
    try:
        db.actualizar_usuario(id_, datos)
        for r in registros:
            if r["id"] == id_:
                r.update(datos)
                break
    finally:
        db.close()


def habilitar(registros: list, id_: int):
    db = get_db()
    try:
        db.habilitar_usuario(id_)
        for r in registros:
            if r["id"] == id_:
                r["estado"] = "HABILITADA"
                break
    finally:
        db.close()


def inhabilitar(registros: list, id_: int):
    db = get_db()
    try:
        db.inhabilitar_usuario(id_)
        for r in registros:
            if r["id"] == id_:
                r["estado"] = "INHABILITADA"
                break
    finally:
        db.close()

