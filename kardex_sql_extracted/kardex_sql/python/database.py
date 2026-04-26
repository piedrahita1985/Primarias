"""
database.py  –  Capa de acceso a datos para Kardex de Reactivos
================================================================
Soporta dos motores:
  - SQLite  (desarrollo local, sin servidor)
  - SQL Server (producción, vía pyodbc)

Uso:
    from database import get_db

    db = get_db()          # Lee config.json y elige el motor
    reactivos = db.get_sustancias()
    db.close()

Cambiar de SQLite a SQL Server: solo editar config.json
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Optional

# ── Intenta importar pyodbc (solo necesario en producción) ──────────────────
try:
    import pyodbc
    _PYODBC_DISPONIBLE = True
except ImportError:
    _PYODBC_DISPONIBLE = False


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  CONFIGURACIÓN                                                           ║
# ╚══════════════════════════════════════════════════════════════════════════╝

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

CONFIG_DEFAULT = {
    "motor": "sqlite",                    # "sqlite" o "sqlserver"
    "sqlite": {
        "path": "data/kardex.db"
    },
    "sqlserver": {
        "server":   "NOMBRE_SERVIDOR",
        "database": "KardexReactivos",
        "driver":   "ODBC Driver 17 for SQL Server",
        "trusted_connection": True,       # True = Windows Auth, False = usuario/clave
        "username": "",                   # Solo si trusted_connection = False
        "password": ""
    }
}


def _cargar_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    # Si no existe, crear config por defecto
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(CONFIG_DEFAULT, f, indent=4, ensure_ascii=False)
    return CONFIG_DEFAULT


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  CLASE BASE                                                              ║
# ╚══════════════════════════════════════════════════════════════════════════╝

class KardexDB:
    """
    Interfaz unificada. Todos los métodos funcionan igual
    sin importar si el motor es SQLite o SQL Server.
    """

    def __init__(self, conn):
        self._conn = conn
        self._cursor = conn.cursor()

    def close(self):
        self._conn.close()

    def commit(self):
        self._conn.commit()

    def _execute(self, sql: str, params: tuple = ()):
        """Ejecuta una query y devuelve el cursor."""
        self._cursor.execute(sql, params)
        return self._cursor

    def _fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        """Ejecuta SELECT y devuelve lista de dicts."""
        cur = self._execute(sql, params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def _fetchone(self, sql: str, params: tuple = ()) -> Optional[dict]:
        cur = self._execute(sql, params)
        cols = [c[0] for c in cur.description]
        row = cur.fetchone()
        return dict(zip(cols, row)) if row else None

    def _insert(self, sql: str, params: tuple = ()) -> int:
        """Inserta y devuelve el ID generado."""
        self._execute(sql, params)
        self._conn.commit()
        # SQLite y SQL Server difieren en cómo obtener el last ID
        return self._cursor.lastrowid or self._fetchone(
            "SELECT @@IDENTITY AS id"
        )["id"]

    # ── PLACEHOLDER para SQL Server ──────────────────────────────────────
    def _ph(self) -> str:
        """Devuelve el placeholder correcto según el motor."""
        return "?"   # Igual para sqlite3 y pyodbc


    # ══════════════════════════════════════════════════════════════════════
    # USUARIOS
    # ══════════════════════════════════════════════════════════════════════

    def get_usuario_login(self, usuario: str, contrasena: str) -> Optional[dict]:
        """Valida credenciales. Devuelve el usuario con sus permisos o None."""
        u = self._fetchone(
            """
            SELECT u.*, p.*
              FROM usuarios u
              LEFT JOIN permisos_usuario p ON p.id_usuario = u.id
             WHERE u.usuario = ? AND u.contrasena = ? AND u.estado = 'HABILITADA'
            """,
            (usuario, contrasena)
        )
        return u

    def get_usuarios(self) -> list[dict]:
        return self._fetchall("SELECT * FROM usuarios ORDER BY nombre")

    def crear_usuario(self, datos: dict) -> int:
        ph = self._ph()
        sql = f"""
            INSERT INTO usuarios (usuario, contrasena, nombre, rol, estado, firma_path, firma_password)
            VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph})
        """
        uid = self._insert(sql, (
            datos["usuario"], datos["contrasena"], datos["nombre"],
            datos["rol"], datos.get("estado", "HABILITADA"),
            datos.get("firma_path"), datos.get("firma_password")
        ))
        # Crear permisos vacíos
        permisos = datos.get("permisos", {})
        self._insertar_permisos(uid, permisos)
        return uid

    def _insertar_permisos(self, id_usuario: int, permisos: dict):
        campos = ["entradas","salidas","inventario","bitacora","prestamos",
                  "recibidos","sustancias","tipos_entrada","tipos_salida",
                  "fabricantes","unidades","ubicaciones","condiciones","colores","usuarios"]
        vals = [int(bool(permisos.get(c, False))) for c in campos]
        ph = self._ph()
        cols = ",".join(campos)
        phs  = ",".join([ph]*len(campos))
        self._execute(
            f"INSERT INTO permisos_usuario (id_usuario,{cols}) VALUES ({ph},{phs})",
            (id_usuario, *vals)
        )
        self.commit()

    def actualizar_usuario(self, id_usuario: int, datos: dict):
        ph = self._ph()
        self._execute(
            f"""UPDATE usuarios SET nombre={ph}, rol={ph}, estado={ph},
                firma_path={ph}, firma_password={ph} WHERE id={ph}""",
            (datos["nombre"], datos["rol"], datos.get("estado","HABILITADA"),
             datos.get("firma_path"), datos.get("firma_password"), id_usuario)
        )
        if "contrasena" in datos and datos["contrasena"]:
            self._execute(
                f"UPDATE usuarios SET contrasena={ph} WHERE id={ph}",
                (datos["contrasena"], id_usuario)
            )
        if "permisos" in datos:
            self._actualizar_permisos(id_usuario, datos["permisos"])
        self.commit()

    def _actualizar_permisos(self, id_usuario: int, permisos: dict):
        ph = self._ph()
        campos = ["entradas","salidas","inventario","bitacora","prestamos",
                  "recibidos","sustancias","tipos_entrada","tipos_salida",
                  "fabricantes","unidades","ubicaciones","condiciones","colores","usuarios"]
        sets = ", ".join([f"{c}={ph}" for c in campos])
        vals = [int(bool(permisos.get(c, False))) for c in campos]
        self._execute(
            f"UPDATE permisos_usuario SET {sets} WHERE id_usuario={ph}",
            (*vals, id_usuario)
        )
        self.commit()


    # ══════════════════════════════════════════════════════════════════════
    # CATÁLOGOS (fabricantes, unidades, condiciones, colores, tipos)
    # ══════════════════════════════════════════════════════════════════════

    def get_fabricantes(self) -> list[dict]:
        return self._fetchall("SELECT * FROM fabricantes ORDER BY fabricante")

    def crear_fabricante(self, nombre: str) -> int:
        return self._insert(f"INSERT INTO fabricantes (fabricante) VALUES ({self._ph()})", (nombre,))

    def get_unidades(self) -> list[dict]:
        return self._fetchall("SELECT * FROM unidad ORDER BY unidad")

    def crear_unidad(self, nombre: str) -> int:
        return self._insert(f"INSERT INTO unidad (unidad) VALUES ({self._ph()})", (nombre,))

    def get_condiciones(self) -> list[dict]:
        return self._fetchall("SELECT * FROM condicion_alm ORDER BY condicion")

    def crear_condicion(self, condicion: str) -> int:
        return self._insert(f"INSERT INTO condicion_alm (condicion) VALUES ({self._ph()})", (condicion,))

    def get_colores(self) -> list[dict]:
        return self._fetchall("SELECT * FROM color_refuerzo ORDER BY color_refuerzo")

    def crear_color(self, color: str) -> int:
        return self._insert(f"INSERT INTO color_refuerzo (color_refuerzo) VALUES ({self._ph()})", (color,))

    def get_tipos_entrada(self, solo_habilitados=True) -> list[dict]:
        w = "WHERE estado='HABILITADA'" if solo_habilitados else ""
        return self._fetchall(f"SELECT * FROM tipo_entrada {w} ORDER BY tipo_entrada")

    def crear_tipo_entrada(self, tipo: str) -> int:
        return self._insert(
            f"INSERT INTO tipo_entrada (tipo_entrada, estado) VALUES ({self._ph()},{self._ph()})",
            (tipo, "HABILITADA")
        )

    def get_tipos_salida(self, solo_habilitados=True) -> list[dict]:
        w = "WHERE estado='HABILITADA'" if solo_habilitados else ""
        return self._fetchall(f"SELECT * FROM tipo_salida {w} ORDER BY tipo_salida")

    def crear_tipo_salida(self, tipo: str) -> int:
        return self._insert(
            f"INSERT INTO tipo_salida (tipo_salida, estado) VALUES ({self._ph()},{self._ph()})",
            (tipo, "HABILITADA")
        )

    def get_ubicaciones(self) -> list[dict]:
        return self._fetchall("SELECT * FROM maestras_ubicaciones ORDER BY ubicacion, no_caja")

    def crear_ubicacion(self, ubicacion: str, no_caja: str) -> int:
        return self._insert(
            f"INSERT INTO maestras_ubicaciones (ubicacion, no_caja) VALUES ({self._ph()},{self._ph()})",
            (ubicacion, no_caja)
        )


    # ══════════════════════════════════════════════════════════════════════
    # SUSTANCIAS (maestra de reactivos)
    # ══════════════════════════════════════════════════════════════════════

    def get_sustancias(self) -> list[dict]:
        return self._fetchall("SELECT * FROM maestras_sustancias ORDER BY nombre")

    def get_sustancia(self, id_sustancia: int) -> Optional[dict]:
        return self._fetchone(
            f"SELECT * FROM maestras_sustancias WHERE id={self._ph()}", (id_sustancia,)
        )

    def crear_sustancia(self, datos: dict) -> int:
        ph = self._ph()
        return self._insert(
            f"""INSERT INTO maestras_sustancias
                (codigo, nombre, propiedad, tipo_muestras, uso_previsto, cantidad_minima, codigo_sistema)
                VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph})""",
            (datos["codigo"], datos["nombre"], datos.get("propiedad"),
             datos.get("tipo_muestras"), datos.get("uso_previsto"),
             float(datos.get("cantidad_minima", 0)), datos.get("codigo_sistema"))
        )

    def actualizar_sustancia(self, id_s: int, datos: dict):
        ph = self._ph()
        self._execute(
            f"""UPDATE maestras_sustancias SET codigo={ph}, nombre={ph}, propiedad={ph},
                tipo_muestras={ph}, uso_previsto={ph}, cantidad_minima={ph},
                codigo_sistema={ph} WHERE id={ph}""",
            (datos["codigo"], datos["nombre"], datos.get("propiedad"),
             datos.get("tipo_muestras"), datos.get("uso_previsto"),
             float(datos.get("cantidad_minima", 0)), datos.get("codigo_sistema"), id_s)
        )
        self.commit()


    # ══════════════════════════════════════════════════════════════════════
    # INVENTARIO
    # ══════════════════════════════════════════════════════════════════════

    def get_inventario(self) -> list[dict]:
        """Devuelve inventario con nombres de catálogos (JOIN)."""
        return self._fetchall("""
            SELECT i.*,
                   s.nombre        AS sustancia,
                   s.codigo        AS codigo_sustancia,
                   s.cantidad_minima,
                   f.fabricante,
                   u.unidad,
                   c.condicion,
                   cr.color_refuerzo,
                   ub.ubicacion,
                   ub.no_caja
              FROM inventario i
              JOIN maestras_sustancias s  ON s.id  = i.id_sustancia
              LEFT JOIN fabricantes f     ON f.id  = i.id_fabricante
              LEFT JOIN unidad u          ON u.id  = i.id_unidad
              LEFT JOIN condicion_alm c   ON c.id  = i.id_condicion
              LEFT JOIN color_refuerzo cr ON cr.id = i.id_color
              LEFT JOIN maestras_ubicaciones ub ON ub.id = i.id_ubicacion
             ORDER BY s.nombre
        """)

    def get_inventario_bajo_minimo(self) -> list[dict]:
        return self._fetchall("""
            SELECT i.*, s.nombre AS sustancia, s.cantidad_minima,
                   u.unidad
              FROM inventario i
              JOIN maestras_sustancias s ON s.id = i.id_sustancia
              LEFT JOIN unidad u ON u.id = i.id_unidad
             WHERE i.cantidad_actual < s.cantidad_minima
               AND i.estado = 'ACTIVO'
        """)

    def crear_inventario(self, datos: dict) -> int:
        ph = self._ph()
        return self._insert(
            f"""INSERT INTO inventario
                (id_sustancia, id_ubicacion, id_fabricante, id_unidad,
                 id_condicion, id_color, lote, fecha_vencimiento, cantidad_actual, estado)
                VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})""",
            (datos["id_sustancia"], datos.get("id_ubicacion"), datos.get("id_fabricante"),
             datos.get("id_unidad"), datos.get("id_condicion"), datos.get("id_color"),
             datos.get("lote"), datos.get("fecha_vencimiento"),
             float(datos.get("cantidad_actual", 0)), datos.get("estado", "ACTIVO"))
        )

    def actualizar_stock(self, id_inventario: int, nueva_cantidad: float):
        ph = self._ph()
        estado = "AGOTADO" if nueva_cantidad <= 0 else "ACTIVO"
        self._execute(
            f"UPDATE inventario SET cantidad_actual={ph}, estado={ph} WHERE id={ph}",
            (nueva_cantidad, estado, id_inventario)
        )
        self.commit()


    # ══════════════════════════════════════════════════════════════════════
    # ENTRADAS
    # ══════════════════════════════════════════════════════════════════════

    def get_entradas(self) -> list[dict]:
        return self._fetchall("""
            SELECT e.*,
                   s.nombre      AS sustancia,
                   te.tipo_entrada,
                   u.usuario     AS usuario_nombre,
                   inv.cantidad_actual
              FROM entradas e
              JOIN inventario i       ON i.id  = e.id_inventario
              JOIN maestras_sustancias s ON s.id = i.id_sustancia
              JOIN tipo_entrada te    ON te.id = e.id_tipo_entrada
              JOIN usuarios u        ON u.id  = e.id_usuario
              LEFT JOIN inventario inv ON inv.id = e.id_inventario
             ORDER BY e.fecha_hora DESC
        """)

    def crear_entrada(self, datos: dict, id_usuario: int) -> int:
        ph = self._ph()
        # 1. Insertar entrada
        id_entrada = self._insert(
            f"""INSERT INTO entradas (id_inventario, id_tipo_entrada, id_usuario,
                fecha_hora, cantidad, observacion, certificado)
                VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph})""",
            (datos["id_inventario"], datos["id_tipo_entrada"], id_usuario,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
             float(datos["cantidad"]), datos.get("observacion"), datos.get("certificado"))
        )
        # 2. Actualizar stock
        inv = self._fetchone(
            f"SELECT cantidad_actual FROM inventario WHERE id={ph}", (datos["id_inventario"],)
        )
        nueva = (inv["cantidad_actual"] or 0) + float(datos["cantidad"])
        self.actualizar_stock(datos["id_inventario"], nueva)
        return id_entrada


    # ══════════════════════════════════════════════════════════════════════
    # SALIDAS
    # ══════════════════════════════════════════════════════════════════════

    def get_salidas(self) -> list[dict]:
        return self._fetchall("""
            SELECT sa.*,
                   s.nombre      AS sustancia,
                   ts.tipo_salida,
                   u.usuario     AS usuario_nombre
              FROM salidas sa
              JOIN inventario i          ON i.id  = sa.id_inventario
              JOIN maestras_sustancias s ON s.id  = i.id_sustancia
              JOIN tipo_salida ts        ON ts.id = sa.id_tipo_salida
              JOIN usuarios u            ON u.id  = sa.id_usuario
             ORDER BY sa.fecha_hora DESC
        """)

    def crear_salida(self, datos: dict, id_usuario: int) -> int:
        ph = self._ph()
        inv = self._fetchone(
            f"SELECT cantidad_actual FROM inventario WHERE id={ph}", (datos["id_inventario"],)
        )
        if not inv or (inv["cantidad_actual"] or 0) < float(datos["cantidad"]):
            raise ValueError("Stock insuficiente para realizar la salida.")

        id_salida = self._insert(
            f"""INSERT INTO salidas (id_inventario, id_tipo_salida, id_usuario,
                fecha_hora, cantidad, observacion)
                VALUES ({ph},{ph},{ph},{ph},{ph},{ph})""",
            (datos["id_inventario"], datos["id_tipo_salida"], id_usuario,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
             float(datos["cantidad"]), datos.get("observacion"))
        )
        nueva = (inv["cantidad_actual"] or 0) - float(datos["cantidad"])
        self.actualizar_stock(datos["id_inventario"], nueva)
        return id_salida


    # ══════════════════════════════════════════════════════════════════════
    # PRÉSTAMOS
    # ══════════════════════════════════════════════════════════════════════

    def get_prestamos(self) -> list[dict]:
        return self._fetchall("""
            SELECT p.*,
                   s.nombre  AS sustancia,
                   u.usuario AS usuario_nombre,
                   un.unidad
              FROM prestamos p
              JOIN inventario i          ON i.id  = p.id_inventario
              JOIN maestras_sustancias s ON s.id  = i.id_sustancia
              JOIN usuarios u            ON u.id  = p.id_usuario
              LEFT JOIN unidad un        ON un.id = i.id_unidad
             ORDER BY p.fecha_hora DESC
        """)

    def crear_prestamo(self, datos: dict, id_usuario: int) -> int:
        ph = self._ph()
        inv = self._fetchone(
            f"SELECT cantidad_actual FROM inventario WHERE id={ph}", (datos["id_inventario"],)
        )
        if not inv or (inv["cantidad_actual"] or 0) < float(datos["cantidad"]):
            raise ValueError("Stock insuficiente para el préstamo.")

        id_prestamo = self._insert(
            f"""INSERT INTO prestamos (id_inventario, id_usuario, fecha_hora,
                cantidad, solicitante, observacion, estado)
                VALUES ({ph},{ph},{ph},{ph},{ph},{ph},'PENDIENTE')""",
            (datos["id_inventario"], id_usuario,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
             float(datos["cantidad"]), datos.get("solicitante"), datos.get("observacion"))
        )
        nueva = (inv["cantidad_actual"] or 0) - float(datos["cantidad"])
        self.actualizar_stock(datos["id_inventario"], nueva)
        return id_prestamo

    def devolver_prestamo(self, id_prestamo: int, cantidad_devuelta: float,
                          observacion: str = "") -> None:
        ph = self._ph()
        prestamo = self._fetchone(
            f"SELECT * FROM prestamos WHERE id={ph}", (id_prestamo,)
        )
        if not prestamo:
            raise ValueError("Préstamo no encontrado.")

        devuelto = (prestamo.get("cantidad_devuelta") or 0) + cantidad_devuelta
        pendiente = prestamo["cantidad"] - devuelto
        estado = "DEVUELTO" if pendiente <= 0 else "PARCIAL"

        self._execute(
            f"""UPDATE prestamos SET estado={ph}, fecha_devolucion={ph},
                cantidad_devuelta={ph}, observacion_devolucion={ph} WHERE id={ph}""",
            (estado, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
             devuelto, observacion, id_prestamo)
        )
        # Devolver stock
        inv = self._fetchone(
            f"SELECT cantidad_actual FROM inventario WHERE id={ph}",
            (prestamo["id_inventario"],)
        )
        nueva = (inv["cantidad_actual"] or 0) + cantidad_devuelta
        self.actualizar_stock(prestamo["id_inventario"], nueva)


    # ══════════════════════════════════════════════════════════════════════
    # BITÁCORA
    # ══════════════════════════════════════════════════════════════════════

    def get_bitacora(self, filtro_usuario: str = None,
                     filtro_operacion: str = None) -> list[dict]:
        where = []
        params = []
        if filtro_usuario:
            where.append(f"usuario = {self._ph()}")
            params.append(filtro_usuario)
        if filtro_operacion:
            where.append(f"tipo_operacion = {self._ph()}")
            params.append(filtro_operacion)
        w = ("WHERE " + " AND ".join(where)) if where else ""
        return self._fetchall(
            f"SELECT * FROM bitacora {w} ORDER BY fecha_hora DESC",
            tuple(params)
        )

    def registrar_bitacora(self, usuario: str, tipo_operacion: str,
                           id_registro: int, campo: str,
                           valor_anterior: str = "", valor_nuevo: str = "") -> None:
        ph = self._ph()
        self._execute(
            f"""INSERT INTO bitacora
                (fecha_hora, usuario, tipo_operacion, id_registro, campo, valor_anterior, valor_nuevo)
                VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph})""",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), usuario,
             tipo_operacion, id_registro, campo, valor_anterior, valor_nuevo)
        )
        self.commit()


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  FÁBRICA DE CONEXIONES                                                   ║
# ╚══════════════════════════════════════════════════════════════════════════╝

def get_db() -> KardexDB:
    """
    Lee config.json y devuelve una instancia de KardexDB
    conectada al motor configurado (sqlite o sqlserver).
    """
    cfg = _cargar_config()
    motor = cfg.get("motor", "sqlite").lower()

    if motor == "sqlite":
        db_path = cfg["sqlite"]["path"]
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        return KardexDB(conn)

    elif motor == "sqlserver":
        if not _PYODBC_DISPONIBLE:
            raise RuntimeError(
                "pyodbc no está instalado. Ejecuta: pip install pyodbc"
            )
        ss = cfg["sqlserver"]
        if ss.get("trusted_connection", True):
            cs = (
                f"DRIVER={{{ss['driver']}}};"
                f"SERVER={ss['server']};"
                f"DATABASE={ss['database']};"
                "Trusted_Connection=yes;"
            )
        else:
            cs = (
                f"DRIVER={{{ss['driver']}}};"
                f"SERVER={ss['server']};"
                f"DATABASE={ss['database']};"
                f"UID={ss['username']};"
                f"PWD={ss['password']};"
            )
        conn = pyodbc.connect(cs)
        return KardexDB(conn)

    else:
        raise ValueError(f"Motor desconocido: '{motor}'. Usa 'sqlite' o 'sqlserver'.")
