"""
init_db_hybrid.py
=================
Script de inicialización de base de datos.
Compatible con SQLite y SQL Server (según config.json).

Uso:
    python init_db_hybrid.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db


def init_database():
    """Inicializa tablas y datos básicos en cualquier motor configurado."""
    print("Conectando a la base de datos...")
    db = get_db()

    try:
        users = db.get_usuarios()
        if not users:
            print("Creando usuario administrador...")
            admin_id = db.crear_usuario(
                {
                    "usuario": "admin",
                    "contrasena": "admin",
                    "nombre": "Administrador",
                    "rol": "ADMIN",
                    "estado": "HABILITADA",
                    "firma_path": "",
                    "firma_password": "",
                    "permisos": {
                        "log_entradas": True,
                        "log_salidas": True,
                        "log_inventario": True,
                        "log_bitacora": True,
                        "log_prestamos": True,
                        "recibidos": True,
                        "maestra_sustancias": True,
                        "maestra_tipos_entrada": True,
                        "maestra_tipos_salida": True,
                        "maestra_fabricantes": True,
                        "maestra_unidades": True,
                        "maestra_ubicaciones": True,
                        "maestra_condiciones": True,
                        "maestra_colores": True,
                        "maestra_usuarios": True,
                    },
                }
            )
            print(f"Usuario admin creado (ID: {admin_id})")
            print("  Usuario:    admin")
            print("  Contrasena: admin")
        else:
            print(f"Base de datos ya inicializada ({len(users)} usuario(s) encontrado(s)).")

        print("Inicializacion completada.")
    except Exception as e:
        print(f"Error durante la inicializacion: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    init_database()
