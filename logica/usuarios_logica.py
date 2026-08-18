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
    """Verifica la contrasena de firma de 'user' (ya cargado en memoria).

    Si la firma_password almacenada todavia esta en texto plano (cuenta legada)
    y la verificacion es exitosa, la rehashea en la BD -- mismo patron de
    migracion perezosa que ya se aplica a la contrasena de login (ver
    KardexDB.get_usuario_login)."""
    firma_pass = (user or {}).get("permisos", {}).get("firma_password", "")
    if not auth.verify_password(ingresada, firma_pass):
        return False
    if firma_pass and not auth.is_hashed(firma_pass) and (user or {}).get("id"):
        db = get_db()
        try:
            nuevo_hash = auth.hash_password(ingresada)
            db.rehash_firma_password(user["id"], nuevo_hash)
            user.setdefault("permisos", {})["firma_password"] = nuevo_hash
        finally:
            db.close()
    return True


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

