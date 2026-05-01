import sqlite3
import os

from database import _cargar_config, _crear_tablas_si_no_existen, _migrar_schema, _ruta_base, _sembrar_admin_si_no_existe


def main():
    cfg = _cargar_config()
    motor = cfg.get("motor", "sqlite").lower()
    if motor != "sqlite":
        print("Inicializacion manual soportada solo para SQLite.")
        return

    db_rel = cfg["sqlite"]["path"]
    db_path = os.path.join(_ruta_base(), db_rel)
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        _crear_tablas_si_no_existen(conn)
        _sembrar_admin_si_no_existe(conn)
        _migrar_schema(conn)
        print(f"Base de datos inicializada en: {db_path}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
