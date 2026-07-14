"""
auth.py - Hashing y verificacion de contrasenas (bcrypt).

Las contrasenas legadas (texto plano, de instalaciones anteriores) siguen
siendo validas: verify_password() detecta si el valor almacenado es un hash
bcrypt o texto plano y compara segun corresponda. Esto permite una migracion
perezosa: quien ya tenia clave en texto plano puede seguir iniciando sesion,
y el llamador es responsable de reescribir el hash tras una verificacion
exitosa contra un valor no hasheado.
"""

import bcrypt

_BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")


def hash_password(plain: str) -> str:
    """Devuelve el hash bcrypt de una contrasena en texto plano."""
    raw = str(plain or "").encode("utf-8")
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def is_hashed(stored: str) -> bool:
    """True si 'stored' ya es un hash bcrypt (y no texto plano legado)."""
    return str(stored or "").startswith(_BCRYPT_PREFIXES)


def verify_password(plain: str, stored: str) -> bool:
    """Verifica 'plain' contra 'stored', sea este un hash bcrypt o texto plano legado."""
    stored = str(stored or "")
    plain = str(plain or "")
    if not stored:
        return False
    if is_hashed(stored):
        try:
            return bcrypt.checkpw(plain.encode("utf-8"), stored.encode("utf-8"))
        except ValueError:
            return False
    return plain == stored
