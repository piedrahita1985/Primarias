"""
database.py  –  Capa de acceso a datos para Kardex de Reactivos
================================================================
Soporta dos motores:
  - SQLite  (desarrollo local, sin servidor)
  - SQL Server (producción, vía pyodbc)

Uso:
    from database import get_db

    db = get_db()
    reactivos = db.get_sustancias()
    db.close()

Cambiar de SQLite a SQL Server: solo editar config.json
"""

import sqlite3
import json
import os
import sys
from datetime import datetime
from typing import Optional

try:
    import pyodbc
    _PYODBC_DISPONIBLE = True
except ImportError:
    _PYODBC_DISPONIBLE = False


# ── Resolución de ruta base ─────────────────────────────────────────────────

def _ruta_base() -> str:
    """Devuelve el directorio base del ejecutable o del script."""
    return os.path.dirname(os.path.abspath(__file__))


CONFIG_PATH = os.path.join(_ruta_base(), "config.json")

CONFIG_DEFAULT = {
    "motor": "sqlite",
    "sqlite": {"path": "data/kardex.db"},
    "sqlserver": {
        "server": "NOMBRE_SERVIDOR",
        "database": "KardexReactivos",
        "driver": "ODBC Driver 17 for SQL Server",
        "trusted_connection": True,
        "username": "",
        "password": "",
    },
}


def _cargar_config() -> dict:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(CONFIG_DEFAULT, f, indent=4, ensure_ascii=False)
    return CONFIG_DEFAULT


# ── Normalización de estado ─────────────────────────────────────────────────
# La app usa 'INHABILITADA'. Las tablas con CHECK usan 'DESHABILITADA'.
# Estas funciones traducen en la frontera.

def _a_db_estado(estado: str) -> str:
    """Convierte 'INHABILITADA' → 'DESHABILITADA' para tablas con CHECK."""
    return "DESHABILITADA" if str(estado or "").upper() == "INHABILITADA" else estado


def _de_db_estado(estado: str) -> str:
    """Convierte 'DESHABILITADA' → 'INHABILITADA' para el resto de la app."""
    return "INHABILITADA" if str(estado or "").upper() == "DESHABILITADA" else estado


# ── Migración de esquema ────────────────────────────────────────────────────

def _col_existe(conn, tabla: str, columna: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({tabla})")
    return any(row[1] == columna for row in cur.fetchall())


def _inventario_permite_anulado(conn) -> bool:
    cur = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='inventario'"
    )
    row = cur.fetchone()
    ddl = row[0] if row and row[0] else ""
    return "ANULADO" in ddl.upper()


def _migrar_schema(conn):
    """
    Añade columnas faltantes a tablas existentes (idempotente).
    Reconstruye tablas que necesitan cambios de restricciones.
    """
    conn.execute("PRAGMA foreign_keys = OFF")

    # ── 1. Estado en catálogos simples ──────────────────────────────────────
    catalogos_sin_estado = [
        "fabricantes", "unidad", "condicion_alm",
        "color_refuerzo", "maestras_ubicaciones", "maestras_sustancias",
    ]
    for tabla in catalogos_sin_estado:
        if not _col_existe(conn, tabla, "estado"):
            conn.execute(
                f"ALTER TABLE {tabla} ADD COLUMN estado TEXT NOT NULL DEFAULT 'HABILITADA'"
            )

    # ── 2. Columnas adicionales en inventario ────────────────────────────────
    extra_inventario = [
        ("potencia",         "TEXT"),
        ("catalogo",         "TEXT"),
        ("presentacion",     "TEXT"),
        ("certificado_anl",  "INTEGER NOT NULL DEFAULT 0"),
        ("ficha_seguridad",  "INTEGER NOT NULL DEFAULT 0"),
        ("factura_compra",   "INTEGER NOT NULL DEFAULT 0"),
        ("fecha_entrada",    "TEXT"),
        ("factura",          "TEXT"),
        ("observaciones",    "TEXT"),
    ]
    for col, tipo in extra_inventario:
        if not _col_existe(conn, "inventario", col):
            conn.execute(f"ALTER TABLE inventario ADD COLUMN {col} {tipo}")

    # ── 2.1 Permitir estado ANULADO en inventario (reconstrucción idempotente)
    if not _inventario_permite_anulado(conn):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS inventario_new (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                id_sustancia      INTEGER NOT NULL REFERENCES maestras_sustancias(id),
                id_ubicacion      INTEGER REFERENCES maestras_ubicaciones(id),
                id_fabricante     INTEGER REFERENCES fabricantes(id),
                id_unidad         INTEGER REFERENCES unidad(id),
                id_condicion      INTEGER REFERENCES condicion_alm(id),
                id_color          INTEGER REFERENCES color_refuerzo(id),
                lote              TEXT,
                fecha_vencimiento TEXT,
                cantidad_actual   REAL    NOT NULL DEFAULT 0,
                estado            TEXT    NOT NULL DEFAULT 'ACTIVO'
                                  CHECK(estado IN ('ACTIVO','AGOTADO','VENCIDO','ANULADO')),
                potencia          TEXT,
                catalogo          TEXT,
                presentacion      TEXT,
                certificado_anl   INTEGER NOT NULL DEFAULT 0,
                ficha_seguridad   INTEGER NOT NULL DEFAULT 0,
                factura_compra    INTEGER NOT NULL DEFAULT 0,
                fecha_entrada     TEXT,
                factura           TEXT,
                observaciones     TEXT
            )
        """)
        conn.execute("""
            INSERT INTO inventario_new
                (id, id_sustancia, id_ubicacion, id_fabricante, id_unidad,
                 id_condicion, id_color, lote, fecha_vencimiento,
                 cantidad_actual, estado,
                 potencia, catalogo, presentacion,
                 certificado_anl, ficha_seguridad, factura_compra,
                 fecha_entrada, factura, observaciones)
            SELECT id, id_sustancia, id_ubicacion, id_fabricante, id_unidad,
                   id_condicion, id_color, lote, fecha_vencimiento,
                   cantidad_actual, estado,
                   potencia, catalogo, presentacion,
                   certificado_anl, ficha_seguridad, factura_compra,
                   fecha_entrada, factura, observaciones
              FROM inventario
        """)
        conn.execute("DROP TABLE inventario")
        conn.execute("ALTER TABLE inventario_new RENAME TO inventario")

    # ── 3. Columnas adicionales en salidas ───────────────────────────────────
    extra_salidas = [
        ("estado",       "TEXT NOT NULL DEFAULT 'ACTIVA'"),
        ("actividad",    "TEXT"),
        ("fecha_salida", "TEXT"),
        ("factura",      "TEXT"),
    ]
    for col, tipo in extra_salidas:
        if not _col_existe(conn, "salidas", col):
            conn.execute(f"ALTER TABLE salidas ADD COLUMN {col} {tipo}")

    # ── 4. Reconstruir prestamos (sin CHECK, con columnas extendidas) ─────────
    if not _col_existe(conn, "prestamos", "id_usuario_destino"):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS prestamos_new (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                id_inventario         INTEGER NOT NULL,
                id_usuario            INTEGER NOT NULL,
                fecha_hora            TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
                cantidad              REAL    NOT NULL,
                solicitante           TEXT,
                observacion           TEXT,
                estado                TEXT    NOT NULL DEFAULT 'PENDIENTE',
                fecha_devolucion      TEXT,
                cantidad_devuelta     REAL,
                observacion_devolucion TEXT,
                id_usuario_destino    INTEGER,
                firma_presta_path     TEXT,
                fecha_prestamo        TEXT,
                estado_recepcion      TEXT    NOT NULL DEFAULT 'PENDIENTE',
                fecha_recepcion       TEXT,
                observacion_recepcion TEXT,
                id_usuario_recibe     INTEGER,
                id_salida_prestamo    INTEGER,
                estado_devolucion     TEXT    NOT NULL DEFAULT 'NO_APLICA',
                id_usuario_devuelve   INTEGER
            )
        """)
        conn.execute("""
            INSERT INTO prestamos_new
                (id, id_inventario, id_usuario, fecha_hora, cantidad,
                 solicitante, observacion, estado,
                 fecha_devolucion, cantidad_devuelta, observacion_devolucion)
            SELECT id, id_inventario, id_usuario, fecha_hora, cantidad,
                   solicitante, observacion, estado,
                   fecha_devolucion, cantidad_devuelta, observacion_devolucion
              FROM prestamos
        """)
        conn.execute("DROP TABLE prestamos")
        conn.execute("ALTER TABLE prestamos_new RENAME TO prestamos")

    # ── 5. Reconstruir check_cecif con esquema completo ─────────────────────
    if not _col_existe(conn, "check_cecif", "id_sustancia"):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS check_cecif_new (
                id                       INTEGER PRIMARY KEY AUTOINCREMENT,
                id_entrada               INTEGER,
                id_usuario               INTEGER,
                fecha_hora               TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
                estado                   TEXT,
                observacion              TEXT,
                fecha_recepcion          TEXT,
                id_proveedor             INTEGER,
                no_orden_compra          TEXT,
                id_sustancia             INTEGER,
                lote                     TEXT,
                cantidad                 TEXT,
                observacion_producto     TEXT,
                observaciones            TEXT,
                id_usuario_aprobo        INTEGER,
                id_usuario_verifico      INTEGER,
                ver_nombre               TEXT,
                ver_no_lote              TEXT,
                ver_cantidad             TEXT,
                ver_rotulo_identificacion TEXT,
                ver_fecha_fabricacion    TEXT,
                ver_fecha_vencimiento    TEXT,
                ver_fabricante           TEXT,
                ver_rotulos_seguridad    TEXT,
                ver_ficha_seguridad      TEXT,
                ver_certificado_calidad  TEXT,
                ver_golpes_roturas       TEXT,
                ver_cumple_especificaciones TEXT
            )
        """)
        conn.execute("""
            INSERT INTO check_cecif_new
                (id, id_entrada, id_usuario, fecha_hora, estado, observacion)
            SELECT id, id_entrada, id_usuario, fecha_hora, estado, observacion
              FROM check_cecif
        """)
        conn.execute("DROP TABLE check_cecif")
        conn.execute("ALTER TABLE check_cecif_new RENAME TO check_cecif")

    # ── 6. Reconstruir check_clientes con esquema completo ───────────────────
    if not _col_existe(conn, "check_clientes", "id_sustancia"):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS check_clientes_new (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                id_entrada            INTEGER,
                id_usuario            INTEGER,
                fecha_hora            TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
                estado                TEXT,
                observacion           TEXT,
                fecha_recepcion       TEXT,
                nombre_cliente        TEXT,
                id_sustancia          INTEGER,
                cantidad              TEXT,
                observacion_producto  TEXT,
                observaciones         TEXT,
                id_usuario_reviso     INTEGER,
                id_usuario_verifico   INTEGER,
                vn_nombre             TEXT,
                vn_no_lote            TEXT,
                vn_cantidad           TEXT,
                vn_rotulo_identificacion TEXT,
                vn_fecha_fabricacion  TEXT,
                vn_fecha_vencimiento  TEXT,
                vn_fabricante         TEXT,
                vn_rotulos_seguridad  TEXT,
                vn_ficha_seguridad    TEXT,
                vn_certificado_calidad TEXT,
                vn_golpes_roturas     TEXT,
                vn_cumple_especificaciones TEXT,
                vd_nombre             TEXT,
                vd_no_lote            TEXT,
                vd_rotulo_identificacion TEXT,
                vd_fecha_vencimiento  TEXT,
                vd_certificado_calidad TEXT,
                vd_ficha_seguridad    TEXT,
                vd_golpes_roturas     TEXT,
                vd_condiciones_almacenamiento TEXT,
                vd_carta_correo       TEXT
            )
        """)
        conn.execute("""
            INSERT INTO check_clientes_new
                (id, id_entrada, id_usuario, fecha_hora, estado, observacion)
            SELECT id, id_entrada, id_usuario, fecha_hora, estado, observacion
              FROM check_clientes
        """)
        conn.execute("DROP TABLE check_clientes")
        conn.execute("ALTER TABLE check_clientes_new RENAME TO check_clientes")

    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  CLASE PRINCIPAL                                                         ║
# ╚══════════════════════════════════════════════════════════════════════════╝

class KardexDB:
    """Interfaz unificada. Funciona igual con SQLite y SQL Server."""

    def __init__(self, conn):
        self._conn = conn
        self._cursor = conn.cursor()

    def close(self):
        self._conn.close()

    def commit(self):
        self._conn.commit()

    def _execute(self, sql: str, params: tuple = ()):
        self._cursor.execute(sql, params)
        return self._cursor

    def _fetchall(self, sql: str, params: tuple = ()) -> list:
        cur = self._execute(sql, params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def _fetchone(self, sql: str, params: tuple = ()) -> Optional[dict]:
        cur = self._execute(sql, params)
        cols = [c[0] for c in cur.description]
        row = cur.fetchone()
        return dict(zip(cols, row)) if row else None

    def _insert(self, sql: str, params: tuple = ()) -> int:
        self._execute(sql, params)
        self._conn.commit()
        lid = self._cursor.lastrowid
        if lid:
            return lid
        row = self._fetchone("SELECT @@IDENTITY AS id")
        return row["id"] if row else None

    def _ph(self) -> str:
        return "?"

    # ══════════════════════════════════════════════════════════════════════
    # USUARIOS
    # ══════════════════════════════════════════════════════════════════════

    def get_usuario_login(self, usuario: str, contrasena: str) -> Optional[dict]:
        u = self._fetchone(
            """
            SELECT u.id, u.usuario, u.contrasena, u.nombre, u.rol, u.estado,
                   u.firma_path, u.firma_password,
                   p.entradas, p.salidas, p.inventario, p.bitacora, p.prestamos,
                   p.recibidos, p.sustancias, p.tipos_entrada, p.tipos_salida,
                   p.fabricantes, p.unidades, p.ubicaciones, p.condiciones,
                   p.colores, p.usuarios
              FROM usuarios u
              LEFT JOIN permisos_usuario p ON p.id_usuario = u.id
             WHERE u.usuario = ? AND u.contrasena = ? AND u.estado = 'HABILITADA'
            """,
            (usuario, contrasena),
        )
        if u:
            u["estado"] = _de_db_estado(u.get("estado", "HABILITADA"))
            u = self._normalizar_usuario(u)
        return u

    def get_usuarios(self) -> list:
        rows = self._fetchall(
            """
            SELECT u.id, u.usuario, u.contrasena, u.nombre, u.rol, u.estado,
                   u.firma_path, u.firma_password,
                   p.entradas, p.salidas, p.inventario, p.bitacora, p.prestamos,
                   p.recibidos, p.sustancias, p.tipos_entrada, p.tipos_salida,
                   p.fabricantes, p.unidades, p.ubicaciones, p.condiciones,
                   p.colores, p.usuarios
              FROM usuarios u
              LEFT JOIN permisos_usuario p ON p.id_usuario = u.id
             ORDER BY u.nombre
            """
        )
        result = []
        for u in rows:
            u["estado"] = _de_db_estado(u.get("estado", "HABILITADA"))
            result.append(self._normalizar_usuario(u))
        return result

    def _normalizar_usuario(self, u: dict) -> dict:
        """Construye la estructura {id, usuario, nombre, rol, estado, permisos}."""
        _PERM_CAMPOS = [
            "entradas", "salidas", "inventario", "bitacora", "prestamos",
            "recibidos", "sustancias", "tipos_entrada", "tipos_salida",
            "fabricantes", "unidades", "ubicaciones", "condiciones", "colores", "usuarios",
        ]
        permisos = {c: bool(u.get(c, False)) for c in _PERM_CAMPOS}
        permisos["firma_path"] = u.get("firma_path") or ""
        permisos["firma_password"] = u.get("firma_password") or ""
        return {
            "id": u["id"],
            "usuario": u["usuario"],
            "contrasena": u.get("contrasena", ""),
            "nombre": u["nombre"],
            "rol": u.get("rol", ""),
            "estado": u.get("estado", "HABILITADA"),
            "permisos": permisos,
        }

    def crear_usuario(self, datos: dict) -> int:
        ph = self._ph()
        uid = self._insert(
            f"""INSERT INTO usuarios
                (usuario, contrasena, nombre, rol, estado, firma_path, firma_password)
                VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph})""",
            (
                datos["usuario"], datos["contrasena"], datos["nombre"],
                datos.get("rol", ""), _a_db_estado(datos.get("estado", "HABILITADA")),
                datos.get("permisos", {}).get("firma_path"),
                datos.get("permisos", {}).get("firma_password"),
            ),
        )
        self._insertar_permisos(uid, datos.get("permisos", {}))
        return uid

    def actualizar_usuario(self, id_usuario: int, datos: dict):
        ph = self._ph()
        self._execute(
            f"""UPDATE usuarios SET nombre={ph}, rol={ph}, estado={ph},
                firma_path={ph}, firma_password={ph} WHERE id={ph}""",
            (
                datos["nombre"], datos.get("rol", ""),
                _a_db_estado(datos.get("estado", "HABILITADA")),
                datos.get("permisos", {}).get("firma_path"),
                datos.get("permisos", {}).get("firma_password"),
                id_usuario,
            ),
        )
        if datos.get("contrasena"):
            self._execute(
                f"UPDATE usuarios SET contrasena={ph} WHERE id={ph}",
                (datos["contrasena"], id_usuario),
            )
        if "permisos" in datos:
            self._actualizar_permisos(id_usuario, datos["permisos"])
        self.commit()

    def habilitar_usuario(self, id_usuario: int):
        ph = self._ph()
        self._execute(
            f"UPDATE usuarios SET estado={ph} WHERE id={ph}",
            ("HABILITADA", id_usuario),
        )
        self.commit()

    def inhabilitar_usuario(self, id_usuario: int):
        ph = self._ph()
        self._execute(
            f"UPDATE usuarios SET estado={ph} WHERE id={ph}",
            ("DESHABILITADA", id_usuario),
        )
        self.commit()

    def _insertar_permisos(self, id_usuario: int, permisos: dict):
        campos = [
            "entradas", "salidas", "inventario", "bitacora", "prestamos",
            "recibidos", "sustancias", "tipos_entrada", "tipos_salida",
            "fabricantes", "unidades", "ubicaciones", "condiciones", "colores", "usuarios",
        ]
        vals = [int(bool(permisos.get(c, False))) for c in campos]
        ph = self._ph()
        cols = ",".join(campos)
        phs = ",".join([ph] * len(campos))
        self._execute(
            f"INSERT INTO permisos_usuario (id_usuario,{cols}) VALUES ({ph},{phs})",
            (id_usuario, *vals),
        )
        self.commit()

    def _actualizar_permisos(self, id_usuario: int, permisos: dict):
        ph = self._ph()
        campos = [
            "entradas", "salidas", "inventario", "bitacora", "prestamos",
            "recibidos", "sustancias", "tipos_entrada", "tipos_salida",
            "fabricantes", "unidades", "ubicaciones", "condiciones", "colores", "usuarios",
        ]
        sets = ", ".join([f"{c}={ph}" for c in campos])
        vals = [int(bool(permisos.get(c, False))) for c in campos]
        self._execute(
            f"UPDATE permisos_usuario SET {sets} WHERE id_usuario={ph}",
            (*vals, id_usuario),
        )
        self.commit()

    # ══════════════════════════════════════════════════════════════════════
    # CATÁLOGOS
    # ══════════════════════════════════════════════════════════════════════

    # ── Fabricantes ─────────────────────────────────────────────────────────

    def get_fabricantes(self) -> list:
        rows = self._fetchall("SELECT * FROM fabricantes ORDER BY fabricante")
        for r in rows:
            r.setdefault("estado", "HABILITADA")
        return rows

    def crear_fabricante(self, nombre: str) -> int:
        return self._insert(
            f"INSERT INTO fabricantes (fabricante, estado) VALUES ({self._ph()},{self._ph()})",
            (nombre, "HABILITADA"),
        )

    def actualizar_fabricante(self, id_: int, nombre: str):
        ph = self._ph()
        self._execute(
            f"UPDATE fabricantes SET fabricante={ph} WHERE id={ph}", (nombre, id_)
        )
        self.commit()

    def habilitar_fabricante(self, id_: int):
        ph = self._ph()
        self._execute(
            f"UPDATE fabricantes SET estado={ph} WHERE id={ph}", ("HABILITADA", id_)
        )
        self.commit()

    def inhabilitar_fabricante(self, id_: int):
        ph = self._ph()
        self._execute(
            f"UPDATE fabricantes SET estado={ph} WHERE id={ph}", ("INHABILITADA", id_)
        )
        self.commit()

    # ── Unidades ────────────────────────────────────────────────────────────

    def get_unidades(self) -> list:
        rows = self._fetchall("SELECT * FROM unidad ORDER BY unidad")
        for r in rows:
            r.setdefault("estado", "HABILITADA")
        return rows

    def crear_unidad(self, nombre: str) -> int:
        return self._insert(
            f"INSERT INTO unidad (unidad, estado) VALUES ({self._ph()},{self._ph()})",
            (nombre, "HABILITADA"),
        )

    def actualizar_unidad(self, id_: int, nombre: str):
        ph = self._ph()
        self._execute(f"UPDATE unidad SET unidad={ph} WHERE id={ph}", (nombre, id_))
        self.commit()

    def habilitar_unidad(self, id_: int):
        ph = self._ph()
        self._execute(
            f"UPDATE unidad SET estado={ph} WHERE id={ph}", ("HABILITADA", id_)
        )
        self.commit()

    def inhabilitar_unidad(self, id_: int):
        ph = self._ph()
        self._execute(
            f"UPDATE unidad SET estado={ph} WHERE id={ph}", ("INHABILITADA", id_)
        )
        self.commit()

    # ── Condiciones ─────────────────────────────────────────────────────────

    def get_condiciones(self) -> list:
        rows = self._fetchall("SELECT * FROM condicion_alm ORDER BY condicion")
        for r in rows:
            r.setdefault("estado", "HABILITADA")
        return rows

    def crear_condicion(self, condicion: str) -> int:
        return self._insert(
            f"INSERT INTO condicion_alm (condicion, estado) VALUES ({self._ph()},{self._ph()})",
            (condicion, "HABILITADA"),
        )

    def actualizar_condicion(self, id_: int, condicion: str):
        ph = self._ph()
        self._execute(
            f"UPDATE condicion_alm SET condicion={ph} WHERE id={ph}", (condicion, id_)
        )
        self.commit()

    def habilitar_condicion(self, id_: int):
        ph = self._ph()
        self._execute(
            f"UPDATE condicion_alm SET estado={ph} WHERE id={ph}", ("HABILITADA", id_)
        )
        self.commit()

    def inhabilitar_condicion(self, id_: int):
        ph = self._ph()
        self._execute(
            f"UPDATE condicion_alm SET estado={ph} WHERE id={ph}", ("INHABILITADA", id_)
        )
        self.commit()

    # ── Colores ─────────────────────────────────────────────────────────────

    def get_colores(self) -> list:
        rows = self._fetchall("SELECT * FROM color_refuerzo ORDER BY color_refuerzo")
        for r in rows:
            r.setdefault("estado", "HABILITADA")
        return rows

    def crear_color(self, color: str) -> int:
        return self._insert(
            f"INSERT INTO color_refuerzo (color_refuerzo, estado) VALUES ({self._ph()},{self._ph()})",
            (color, "HABILITADA"),
        )

    def actualizar_color(self, id_: int, color: str):
        ph = self._ph()
        self._execute(
            f"UPDATE color_refuerzo SET color_refuerzo={ph} WHERE id={ph}", (color, id_)
        )
        self.commit()

    def habilitar_color(self, id_: int):
        ph = self._ph()
        self._execute(
            f"UPDATE color_refuerzo SET estado={ph} WHERE id={ph}", ("HABILITADA", id_)
        )
        self.commit()

    def inhabilitar_color(self, id_: int):
        ph = self._ph()
        self._execute(
            f"UPDATE color_refuerzo SET estado={ph} WHERE id={ph}", ("INHABILITADA", id_)
        )
        self.commit()

    # ── Tipos Entrada ───────────────────────────────────────────────────────

    def get_tipos_entrada(self, solo_habilitados: bool = False) -> list:
        sql = (
            "SELECT * FROM tipo_entrada WHERE estado='HABILITADA' ORDER BY tipo_entrada"
            if solo_habilitados
            else "SELECT * FROM tipo_entrada ORDER BY tipo_entrada"
        )
        rows = self._fetchall(sql)
        for r in rows:
            r["estado"] = _de_db_estado(r.get("estado", "HABILITADA"))
        return rows

    def crear_tipo_entrada(self, tipo: str) -> int:
        return self._insert(
            f"INSERT INTO tipo_entrada (tipo_entrada, estado) VALUES ({self._ph()},{self._ph()})",
            (tipo, "HABILITADA"),
        )

    def actualizar_tipo_entrada(self, id_: int, tipo: str, estado: str):
        ph = self._ph()
        self._execute(
            f"UPDATE tipo_entrada SET tipo_entrada={ph}, estado={ph} WHERE id={ph}",
            (tipo, _a_db_estado(estado), id_),
        )
        self.commit()

    def habilitar_tipo_entrada(self, id_: int):
        ph = self._ph()
        self._execute(
            f"UPDATE tipo_entrada SET estado={ph} WHERE id={ph}", ("HABILITADA", id_)
        )
        self.commit()

    def inhabilitar_tipo_entrada(self, id_: int):
        ph = self._ph()
        self._execute(
            f"UPDATE tipo_entrada SET estado={ph} WHERE id={ph}",
            ("DESHABILITADA", id_),
        )
        self.commit()

    # ── Tipos Salida ────────────────────────────────────────────────────────

    def get_tipos_salida(self, solo_habilitados: bool = False) -> list:
        sql = (
            "SELECT * FROM tipo_salida WHERE estado='HABILITADA' ORDER BY tipo_salida"
            if solo_habilitados
            else "SELECT * FROM tipo_salida ORDER BY tipo_salida"
        )
        rows = self._fetchall(sql)
        for r in rows:
            r["estado"] = _de_db_estado(r.get("estado", "HABILITADA"))
        return rows

    def crear_tipo_salida(self, tipo: str) -> int:
        return self._insert(
            f"INSERT INTO tipo_salida (tipo_salida, estado) VALUES ({self._ph()},{self._ph()})",
            (tipo, "HABILITADA"),
        )

    def actualizar_tipo_salida(self, id_: int, tipo: str, estado: str):
        ph = self._ph()
        self._execute(
            f"UPDATE tipo_salida SET tipo_salida={ph}, estado={ph} WHERE id={ph}",
            (tipo, _a_db_estado(estado), id_),
        )
        self.commit()

    def habilitar_tipo_salida(self, id_: int):
        ph = self._ph()
        self._execute(
            f"UPDATE tipo_salida SET estado={ph} WHERE id={ph}", ("HABILITADA", id_)
        )
        self.commit()

    def inhabilitar_tipo_salida(self, id_: int):
        ph = self._ph()
        self._execute(
            f"UPDATE tipo_salida SET estado={ph} WHERE id={ph}",
            ("DESHABILITADA", id_),
        )
        self.commit()

    # ── Ubicaciones ─────────────────────────────────────────────────────────

    def get_ubicaciones(self) -> list:
        rows = self._fetchall(
            "SELECT * FROM maestras_ubicaciones ORDER BY ubicacion, no_caja"
        )
        for r in rows:
            r.setdefault("estado", "HABILITADA")
        return rows

    def crear_ubicacion(self, ubicacion: str, no_caja: str) -> int:
        return self._insert(
            f"INSERT INTO maestras_ubicaciones (ubicacion, no_caja, estado) VALUES ({self._ph()},{self._ph()},{self._ph()})",
            (ubicacion, no_caja, "HABILITADA"),
        )

    def actualizar_ubicacion(self, id_: int, ubicacion: str, no_caja: str):
        ph = self._ph()
        self._execute(
            f"UPDATE maestras_ubicaciones SET ubicacion={ph}, no_caja={ph} WHERE id={ph}",
            (ubicacion, no_caja, id_),
        )
        self.commit()

    def habilitar_ubicacion(self, id_: int):
        ph = self._ph()
        self._execute(
            f"UPDATE maestras_ubicaciones SET estado={ph} WHERE id={ph}",
            ("HABILITADA", id_),
        )
        self.commit()

    def inhabilitar_ubicacion(self, id_: int):
        ph = self._ph()
        self._execute(
            f"UPDATE maestras_ubicaciones SET estado={ph} WHERE id={ph}",
            ("INHABILITADA", id_),
        )
        self.commit()

    # ══════════════════════════════════════════════════════════════════════
    # SUSTANCIAS
    # ══════════════════════════════════════════════════════════════════════

    def get_sustancias(self) -> list:
        rows = self._fetchall(
            "SELECT * FROM maestras_sustancias ORDER BY nombre"
        )
        for r in rows:
            r.setdefault("estado", "HABILITADA")
        return rows

    def get_sustancia(self, id_sustancia: int) -> Optional[dict]:
        r = self._fetchone(
            f"SELECT * FROM maestras_sustancias WHERE id={self._ph()}",
            (id_sustancia,),
        )
        if r:
            r.setdefault("estado", "HABILITADA")
        return r

    def crear_sustancia(self, datos: dict) -> int:
        ph = self._ph()
        return self._insert(
            f"""INSERT INTO maestras_sustancias
                (codigo, nombre, propiedad, tipo_muestras, uso_previsto,
                 cantidad_minima, codigo_sistema, estado)
                VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})""",
            (
                datos["codigo"], datos["nombre"],
                datos.get("propiedad"), datos.get("tipo_muestras"),
                datos.get("uso_previsto"),
                float(datos.get("cantidad_minima") or 0),
                datos.get("codigo_sistema"),
                "HABILITADA",
            ),
        )

    def actualizar_sustancia(self, id_s: int, datos: dict):
        ph = self._ph()
        self._execute(
            f"""UPDATE maestras_sustancias SET
                codigo={ph}, nombre={ph}, propiedad={ph}, tipo_muestras={ph},
                uso_previsto={ph}, cantidad_minima={ph}, codigo_sistema={ph}
                WHERE id={ph}""",
            (
                datos["codigo"], datos["nombre"],
                datos.get("propiedad"), datos.get("tipo_muestras"),
                datos.get("uso_previsto"),
                float(datos.get("cantidad_minima") or 0),
                datos.get("codigo_sistema"), id_s,
            ),
        )
        self.commit()

    def habilitar_sustancia(self, id_: int):
        ph = self._ph()
        self._execute(
            f"UPDATE maestras_sustancias SET estado={ph} WHERE id={ph}",
            ("HABILITADA", id_),
        )
        self.commit()

    def inhabilitar_sustancia(self, id_: int):
        ph = self._ph()
        self._execute(
            f"UPDATE maestras_sustancias SET estado={ph} WHERE id={ph}",
            ("INHABILITADA", id_),
        )
        self.commit()

    # ══════════════════════════════════════════════════════════════════════
    # INVENTARIO (lotes/items)
    # ══════════════════════════════════════════════════════════════════════

    def get_inventario(self) -> list:
        """Devuelve inventario enriquecido con nombres de catálogos."""
        rows = self._fetchall("""
            SELECT i.*,
                   s.nombre          AS nombre,
                   s.codigo          AS codigo,
                   s.propiedad,
                   s.tipo_muestras,
                   s.uso_previsto,
                   s.cantidad_minima,
                   s.codigo_sistema,
                   f.fabricante,
                   u.unidad,
                   c.condicion       AS condicion_alm,
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
        for r in rows:
            # Compatibilidad con nombres JSON antiguos
            r.setdefault("id_entrada", r["id"])
            r.setdefault("id_color_refuerzo", r.get("id_color"))
            r.setdefault("id_condicion_alm", r.get("id_condicion"))
            r.setdefault("cantidad", r.get("cantidad_actual", 0))
            estado_raw = str(r.get("estado", "ACTIVA") or "").upper()
            if estado_raw == "ACTIVO":
                r["estado"] = "ACTIVA"
            elif estado_raw == "ANULADO":
                r["estado"] = "ANULADA"
            else:
                r["estado"] = r.get("estado", "ACTIVA")
            r.setdefault("fecha_entrada", r.get("fecha_entrada", ""))
            r.setdefault("certificado_anl", bool(r.get("certificado_anl", 0)))
            r.setdefault("ficha_seguridad", bool(r.get("ficha_seguridad", 0)))
            r.setdefault("factura_compra", bool(r.get("factura_compra", 0)))
        return rows

    def get_inventario_bajo_minimo(self) -> list:
        return self._fetchall("""
            SELECT i.*, s.nombre, s.cantidad_minima, u.unidad
              FROM inventario i
              JOIN maestras_sustancias s ON s.id = i.id_sustancia
              LEFT JOIN unidad u ON u.id = i.id_unidad
             WHERE i.cantidad_actual < s.cantidad_minima
               AND i.estado = 'ACTIVO'
        """)

    def crear_inventario(self, datos: dict) -> int:
        """Crea un registro de inventario (item/lote) y devuelve su id."""
        ph = self._ph()
        return self._insert(
            f"""INSERT INTO inventario
                (id_sustancia, id_ubicacion, id_fabricante, id_unidad,
                 id_condicion, id_color, lote, fecha_vencimiento,
                 cantidad_actual, estado,
                 potencia, catalogo, presentacion,
                 certificado_anl, ficha_seguridad, factura_compra,
                 fecha_entrada, factura, observaciones)
                VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},
                        {ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})""",
            (
                datos["id_sustancia"],
                datos.get("id_ubicacion"),
                datos.get("id_fabricante"),
                datos.get("id_unidad"),
                datos.get("id_condicion") or datos.get("id_condicion_alm"),
                datos.get("id_color") or datos.get("id_color_refuerzo"),
                datos.get("lote"),
                datos.get("fecha_vencimiento"),
                float(datos.get("cantidad_actual") or datos.get("cantidad", 0)),
                "ACTIVO",
                datos.get("potencia"),
                datos.get("catalogo"),
                datos.get("presentacion"),
                int(bool(datos.get("certificado_anl", False))),
                int(bool(datos.get("ficha_seguridad", False))),
                int(bool(datos.get("factura_compra", False))),
                datos.get("fecha_entrada"),
                datos.get("factura"),
                datos.get("observaciones"),
            ),
        )

    def actualizar_inventario(self, id_inv: int, datos: dict):
        """Actualiza campos editables de un item de inventario."""
        ph = self._ph()
        self._execute(
            f"""UPDATE inventario SET
                id_sustancia={ph}, id_ubicacion={ph}, id_fabricante={ph},
                id_unidad={ph}, id_condicion={ph}, id_color={ph},
                lote={ph}, fecha_vencimiento={ph},
                potencia={ph}, catalogo={ph}, presentacion={ph},
                certificado_anl={ph}, ficha_seguridad={ph}, factura_compra={ph},
                fecha_entrada={ph}, factura={ph}, observaciones={ph}
                WHERE id={ph}""",
            (
                datos.get("id_sustancia"),
                datos.get("id_ubicacion"),
                datos.get("id_fabricante"),
                datos.get("id_unidad"),
                datos.get("id_condicion") or datos.get("id_condicion_alm"),
                datos.get("id_color") or datos.get("id_color_refuerzo"),
                datos.get("lote"),
                datos.get("fecha_vencimiento"),
                datos.get("potencia"),
                datos.get("catalogo"),
                datos.get("presentacion"),
                int(bool(datos.get("certificado_anl", False))),
                int(bool(datos.get("ficha_seguridad", False))),
                int(bool(datos.get("factura_compra", False))),
                datos.get("fecha_entrada"),
                datos.get("factura"),
                datos.get("observaciones"),
                id_inv,
            ),
        )
        self.commit()

    def actualizar_stock(self, id_inventario: int, nueva_cantidad: float):
        ph = self._ph()
        if nueva_cantidad <= 0:
            estado = "AGOTADO"
        else:
            estado = "ACTIVO"
        self._execute(
            f"UPDATE inventario SET cantidad_actual={ph}, estado={ph} WHERE id={ph}",
            (nueva_cantidad, estado, id_inventario),
        )
        self.commit()

    def anular_inventario(self, id_inv: int):
        ph = self._ph()
        self._execute(
            f"UPDATE inventario SET estado={ph} WHERE id={ph}", ("ANULADO", id_inv)
        )
        self.commit()

    # ══════════════════════════════════════════════════════════════════════
    # ENTRADAS (movimientos de compra / ingreso)
    # ══════════════════════════════════════════════════════════════════════

    def get_entradas(self) -> list:
        return self._fetchall("""
            SELECT e.*,
                   s.nombre      AS sustancia,
                   s.codigo      AS codigo_sustancia,
                   te.tipo_entrada,
                   u.usuario     AS usuario_nombre,
                   i.cantidad_actual
              FROM entradas e
              JOIN inventario i          ON i.id  = e.id_inventario
              JOIN maestras_sustancias s ON s.id  = i.id_sustancia
              JOIN tipo_entrada te       ON te.id = e.id_tipo_entrada
              JOIN usuarios u            ON u.id  = e.id_usuario
             ORDER BY e.fecha_hora DESC
        """)

    def crear_entrada(self, datos: dict, id_usuario: int) -> int:
        """
        Crea un movimiento de entrada y actualiza stock en inventario.
        datos debe incluir: id_inventario, id_tipo_entrada, cantidad.
        """
        ph = self._ph()
        id_entrada = self._insert(
            f"""INSERT INTO entradas
                (id_inventario, id_tipo_entrada, id_usuario,
                 fecha_hora, cantidad, observacion, certificado)
                VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph})""",
            (
                datos["id_inventario"], datos["id_tipo_entrada"], id_usuario,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                float(datos["cantidad"]),
                datos.get("observacion"),
                datos.get("certificado"),
            ),
        )
        inv = self._fetchone(
            f"SELECT cantidad_actual FROM inventario WHERE id={ph}",
            (datos["id_inventario"],),
        )
        nueva = (inv["cantidad_actual"] or 0) + float(datos["cantidad"])
        self.actualizar_stock(datos["id_inventario"], nueva)
        return id_entrada

    # ══════════════════════════════════════════════════════════════════════
    # SALIDAS (movimientos de egreso)
    # ══════════════════════════════════════════════════════════════════════

    def get_salidas(self) -> list:
        rows = self._fetchall("""
            SELECT sa.*,
                   s.nombre      AS sustancia,
                   s.codigo      AS codigo_sustancia,
                   ts.tipo_salida,
                   u.usuario     AS usuario_nombre,
                   i.id_sustancia,
                   i.lote
              FROM salidas sa
              JOIN inventario i          ON i.id  = sa.id_inventario
              JOIN maestras_sustancias s ON s.id  = i.id_sustancia
              JOIN tipo_salida ts        ON ts.id = sa.id_tipo_salida
              JOIN usuarios u            ON u.id  = sa.id_usuario
             ORDER BY sa.fecha_hora DESC
        """)
        for r in rows:
            r.setdefault("id_entrada", r.get("id_inventario"))
            r.setdefault("estado", "ACTIVA")
        return rows

    def crear_salida(self, datos: dict, id_usuario: int) -> int:
        """
        Crea un movimiento de salida. Valida stock suficiente.
        datos debe incluir: id_inventario, id_tipo_salida, cantidad.
        """
        ph = self._ph()
        inv = self._fetchone(
            f"SELECT cantidad_actual FROM inventario WHERE id={ph}",
            (datos.get("id_inventario") or datos.get("id_entrada"),),
        )
        id_inv = datos.get("id_inventario") or datos.get("id_entrada")
        if not inv or (inv["cantidad_actual"] or 0) < float(datos["cantidad"]):
            raise ValueError("Stock insuficiente para realizar la salida.")

        id_salida = self._insert(
            f"""INSERT INTO salidas
                (id_inventario, id_tipo_salida, id_usuario,
                 fecha_hora, cantidad, observacion,
                 estado, actividad, fecha_salida, factura)
                VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})""",
            (
                id_inv,
                datos["id_tipo_salida"],
                id_usuario,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                float(datos["cantidad"]),
                datos.get("observacion"),
                "ACTIVA",
                datos.get("actividad"),
                datos.get("fecha_salida"),
                datos.get("factura"),
            ),
        )
        nueva = (inv["cantidad_actual"] or 0) - float(datos["cantidad"])
        self.actualizar_stock(id_inv, nueva)
        return id_salida

    def actualizar_salida(self, id_salida: int, datos: dict):
        ph = self._ph()
        self._execute(
            f"""UPDATE salidas SET
                actividad={ph}, observacion={ph}, fecha_salida={ph}
                WHERE id={ph}""",
            (datos.get("actividad"), datos.get("observacion"),
             datos.get("fecha_salida"), id_salida),
        )
        self.commit()

    def anular_salida(self, id_salida: int):
        """Anula la salida y restaura el stock."""
        ph = self._ph()
        salida = self._fetchone(
            f"SELECT * FROM salidas WHERE id={ph}", (id_salida,)
        )
        if not salida or salida.get("estado") == "ANULADA":
            return
        self._execute(
            f"UPDATE salidas SET estado={ph} WHERE id={ph}", ("ANULADA", id_salida)
        )
        inv = self._fetchone(
            f"SELECT cantidad_actual FROM inventario WHERE id={ph}",
            (salida["id_inventario"],),
        )
        if inv:
            nueva = (inv["cantidad_actual"] or 0) + float(salida.get("cantidad", 0))
            self.actualizar_stock(salida["id_inventario"], nueva)

    # ══════════════════════════════════════════════════════════════════════
    # PRÉSTAMOS (sistema bilateral de préstamos entre usuarios)
    # ══════════════════════════════════════════════════════════════════════

    def _enriquecer_prestamo(self, p: dict) -> dict:
        """Añade nombre de sustancia, lote y nombres de usuario al prestamo."""
        inv = self._fetchone(
            f"SELECT i.*, s.nombre AS sustancia, s.codigo, un.unidad FROM inventario i "
            f"JOIN maestras_sustancias s ON s.id=i.id_sustancia "
            f"LEFT JOIN unidad un ON un.id=i.id_unidad "
            f"WHERE i.id={self._ph()}",
            (p.get("id_inventario"),),
        ) or {}
        presta = self._fetchone(
            f"SELECT nombre, usuario FROM usuarios WHERE id={self._ph()}",
            (p.get("id_usuario"),),
        ) or {}
        destino = self._fetchone(
            f"SELECT nombre, usuario FROM usuarios WHERE id={self._ph()}",
            (p.get("id_usuario_destino"),),
        ) or {}
        return {
            **p,
            "id_entrada": p.get("id_inventario"),
            "id_sustancia": inv.get("id_sustancia"),
            "id_unidad": inv.get("id_unidad"),
            "codigo": inv.get("codigo", ""),
            "nombre": inv.get("sustancia", ""),
            "lote": inv.get("lote", ""),
            "unidad": inv.get("unidad", ""),
            "id_usuario_presta": p.get("id_usuario"),
            "usuario_presta_nombre": presta.get("nombre") or presta.get("usuario", ""),
            "usuario_destino_nombre": destino.get("nombre") or destino.get("usuario", ""),
            "fecha_prestamo": p.get("fecha_prestamo") or p.get("fecha_hora", "")[:10],
        }

    def get_prestamos(self) -> list:
        rows = self._fetchall(
            "SELECT * FROM prestamos ORDER BY fecha_hora DESC"
        )
        return [self._enriquecer_prestamo(p) for p in rows]

    def get_prestamos_emitidos(self, id_usuario: int, mes: str = "", limit: int = 15) -> list:
        rows = self._fetchall(
            f"SELECT * FROM prestamos WHERE id_usuario={self._ph()} ORDER BY fecha_hora DESC",
            (id_usuario,),
        )
        if mes:
            rows = [r for r in rows if str(r.get("fecha_prestamo") or r.get("fecha_hora", "")).startswith(mes)]
        if limit and limit > 0:
            rows = rows[:limit]
        return [self._enriquecer_prestamo(p) for p in rows]

    def get_prestamos_pendientes_para(self, id_usuario_destino: int) -> list:
        rows = self._fetchall(
            f"SELECT * FROM prestamos WHERE id_usuario_destino={self._ph()} AND estado='PENDIENTE' ORDER BY fecha_hora DESC",
            (id_usuario_destino,),
        )
        return [self._enriquecer_prestamo(p) for p in rows]

    def get_recibidos_pendientes_para(self, id_usuario_destino: int) -> list:
        rows = self._fetchall(
            f"SELECT * FROM prestamos WHERE id_usuario_destino={self._ph()} AND estado_recepcion='PENDIENTE' ORDER BY fecha_hora DESC",
            (id_usuario_destino,),
        )
        return [self._enriquecer_prestamo(p) for p in rows]

    def get_devoluciones_pendientes_para(self, id_usuario_destino: int) -> list:
        rows = self._fetchall(
            f"SELECT * FROM prestamos WHERE id_usuario_destino={self._ph()} AND estado_recepcion='RECIBIDO' AND estado_devolucion='PENDIENTE' ORDER BY fecha_hora DESC",
            (id_usuario_destino,),
        )
        return [self._enriquecer_prestamo(p) for p in rows]

    def get_meses_prestamos_emitidos(self, id_usuario: int) -> list:
        rows = self._fetchall(
            f"SELECT fecha_prestamo, fecha_hora FROM prestamos WHERE id_usuario={self._ph()}",
            (id_usuario,),
        )
        meses = set()
        for r in rows:
            fecha = str(r.get("fecha_prestamo") or r.get("fecha_hora", ""))[:7]
            if len(fecha) == 7:
                meses.add(fecha)
        return sorted(meses, reverse=True)

    def crear_prestamo(self, datos: dict, id_usuario: int) -> int:
        """
        Crea un préstamo SIN decrementar stock (el stock se decrementa al ACEPTAR).
        datos: id_inventario (o id_entrada), id_usuario_destino, cantidad, observacion...
        """
        ph = self._ph()
        id_inv = datos.get("id_inventario") or datos.get("id_entrada")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return self._insert(
            f"""INSERT INTO prestamos
                (id_inventario, id_usuario, fecha_hora, cantidad,
                 solicitante, observacion, estado,
                 id_usuario_destino, firma_presta_path, fecha_prestamo,
                 estado_recepcion, estado_devolucion)
                VALUES ({ph},{ph},{ph},{ph},{ph},{ph},'PENDIENTE',{ph},{ph},{ph},'PENDIENTE','NO_APLICA')""",
            (
                id_inv, id_usuario, now,
                float(datos.get("cantidad", 0)),
                datos.get("solicitante"),
                datos.get("observacion"),
                datos.get("id_usuario_destino"),
                datos.get("firma_presta_path"),
                datos.get("fecha_prestamo", now[:10]),
            ),
        )

    def responder_prestamo(
        self,
        id_prestamo: int,
        id_usuario_recibe: int,
        aceptar: bool,
        observacion_recibo: str = "",
        id_usuario_accion: int = None,
    ) -> tuple:
        """Acepta o rechaza un préstamo pendiente. Devuelve (bool, mensaje)."""
        ph = self._ph()
        prestamo = self._fetchone(
            f"SELECT * FROM prestamos WHERE id={ph}", (id_prestamo,)
        )
        if not prestamo:
            return False, "No se encontró el préstamo."
        if prestamo.get("estado") != "PENDIENTE":
            return False, "Este préstamo ya fue respondido."
        if int(prestamo.get("id_usuario_destino") or 0) != int(id_usuario_recibe or 0):
            return False, "El préstamo no corresponde al usuario autenticado."

        if aceptar:
            inv = self._fetchone(
                f"SELECT cantidad_actual FROM inventario WHERE id={ph}",
                (prestamo["id_inventario"],),
            )
            disponible = float(inv.get("cantidad_actual") or 0) if inv else 0
            cantidad = float(prestamo.get("cantidad", 0))
            if disponible < cantidad:
                return False, f"Stock insuficiente. Disponible: {disponible}"

            # Crear salida por el préstamo
            id_salida = self.crear_salida(
                {
                    "id_inventario": prestamo["id_inventario"],
                    "id_tipo_salida": self._get_tipo_salida_prestamo(),
                    "cantidad": cantidad,
                    "actividad": f"PRESTAMO A USUARIO ID {id_usuario_recibe}",
                    "observacion": observacion_recibo,
                },
                id_usuario_accion or id_usuario_recibe,
            )
            nuevo_estado = "RECIBIDO"
            nuevo_est_dev = "PENDIENTE"
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._execute(
                f"""UPDATE prestamos SET
                    estado={ph}, estado_recepcion={ph}, estado_devolucion={ph},
                    fecha_recepcion={ph}, observacion_recepcion={ph},
                    id_usuario_recibe={ph}, id_salida_prestamo={ph}
                    WHERE id={ph}""",
                (
                    nuevo_estado, nuevo_estado, nuevo_est_dev,
                    now, observacion_recibo,
                    id_usuario_recibe, id_salida,
                    id_prestamo,
                ),
            )
        else:
            nuevo_estado = "RECHAZADO"
            self._execute(
                f"""UPDATE prestamos SET
                    estado={ph}, estado_recepcion={ph},
                    id_usuario_recibe={ph}, observacion_recepcion={ph}
                    WHERE id={ph}""",
                (nuevo_estado, nuevo_estado, id_usuario_recibe, observacion_recibo, id_prestamo),
            )
        self.commit()
        return True, "Préstamo procesado correctamente."

    def devolver_prestamo(
        self,
        id_prestamo: int,
        id_usuario_devuelve: int,
        observacion_devolucion: str = "",
        id_usuario_accion: int = None,
    ) -> tuple:
        """Registra la devolución de un préstamo recibido."""
        ph = self._ph()
        prestamo = self._fetchone(
            f"SELECT * FROM prestamos WHERE id={ph}", (id_prestamo,)
        )
        if not prestamo:
            return False, "No se encontró el préstamo."
        if int(prestamo.get("id_usuario_destino") or 0) != int(id_usuario_devuelve or 0):
            return False, "La devolución no corresponde al usuario autenticado."
        if prestamo.get("estado_recepcion") != "RECIBIDO":
            return False, "El préstamo aún no ha sido recibido."
        if prestamo.get("estado_devolucion") == "DEVUELTO":
            return False, "Este préstamo ya fue devuelto."

        cantidad = float(prestamo.get("cantidad", 0))
        inv = self._fetchone(
            f"SELECT cantidad_actual FROM inventario WHERE id={ph}",
            (prestamo["id_inventario"],),
        )
        if inv:
            nueva = (inv["cantidad_actual"] or 0) + cantidad
            self.actualizar_stock(prestamo["id_inventario"], nueva)

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._execute(
            f"""UPDATE prestamos SET
                estado={ph}, estado_devolucion={ph},
                fecha_devolucion={ph}, observacion_devolucion={ph},
                id_usuario_devuelve={ph}
                WHERE id={ph}""",
            ("DEVUELTO", "DEVUELTO", now, observacion_devolucion,
             id_usuario_devuelve, id_prestamo),
        )
        self.commit()
        return True, "Devolución registrada correctamente."

    def _get_tipo_salida_prestamo(self) -> Optional[int]:
        row = self._fetchone(
            "SELECT id FROM tipo_salida WHERE upper(tipo_salida) IN ('PRESTAMO','PRÉSTAMO')"
        )
        return row["id"] if row else None

    # ══════════════════════════════════════════════════════════════════════
    # CHECKS CECIF y CLIENTES
    # ══════════════════════════════════════════════════════════════════════

    def get_check_cecif(self) -> list:
        return self._fetchall("SELECT * FROM check_cecif ORDER BY fecha_hora DESC")

    def crear_check_cecif(self, datos: dict, id_usuario: int) -> int:
        ph = self._ph()
        ver = datos.get("verificacion", {})
        return self._insert(
            f"""INSERT INTO check_cecif
                (id_entrada, id_usuario, fecha_hora,
                 fecha_recepcion, id_proveedor, no_orden_compra,
                 id_sustancia, lote, cantidad,
                 observacion_producto, observaciones,
                 id_usuario_aprobo, id_usuario_verifico,
                 ver_nombre, ver_no_lote, ver_cantidad,
                 ver_rotulo_identificacion, ver_fecha_fabricacion,
                 ver_fecha_vencimiento, ver_fabricante,
                 ver_rotulos_seguridad, ver_ficha_seguridad,
                 ver_certificado_calidad, ver_golpes_roturas,
                 ver_cumple_especificaciones)
                VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},
                        {ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},
                        {ph},{ph},{ph})""",
            (
                datos.get("id_entrada"),
                id_usuario,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                datos.get("fecha_recepcion"),
                datos.get("id_proveedor"),
                datos.get("no_orden_compra"),
                datos.get("id_sustancia"),
                datos.get("lote"),
                datos.get("cantidad"),
                datos.get("observacion_producto"),
                datos.get("observaciones"),
                datos.get("id_usuario_aprobo"),
                datos.get("id_usuario_verifico"),
                ver.get("nombre"), ver.get("no_lote"), ver.get("cantidad"),
                ver.get("rotulo_identificacion"), ver.get("fecha_fabricacion"),
                ver.get("fecha_vencimiento"), ver.get("fabricante"),
                ver.get("rotulos_seguridad"), ver.get("ficha_seguridad"),
                ver.get("certificado_calidad"), ver.get("golpes_roturas"),
                ver.get("cumple_especificaciones"),
            ),
        )

    def _row_to_verificacion_cecif(self, r: dict) -> dict:
        """Reconstruye el dict verificacion desde columnas planas."""
        return {
            "nombre": r.get("ver_nombre", ""),
            "no_lote": r.get("ver_no_lote", ""),
            "cantidad": r.get("ver_cantidad", ""),
            "rotulo_identificacion": r.get("ver_rotulo_identificacion", ""),
            "fecha_fabricacion": r.get("ver_fecha_fabricacion", ""),
            "fecha_vencimiento": r.get("ver_fecha_vencimiento", ""),
            "fabricante": r.get("ver_fabricante", ""),
            "rotulos_seguridad": r.get("ver_rotulos_seguridad", ""),
            "ficha_seguridad": r.get("ver_ficha_seguridad", ""),
            "certificado_calidad": r.get("ver_certificado_calidad", ""),
            "golpes_roturas": r.get("ver_golpes_roturas", ""),
            "cumple_especificaciones": r.get("ver_cumple_especificaciones", ""),
        }

    def get_check_clientes(self) -> list:
        return self._fetchall("SELECT * FROM check_clientes ORDER BY fecha_hora DESC")

    def crear_check_cliente(self, datos: dict, id_usuario: int) -> int:
        ph = self._ph()
        vn = datos.get("verificacion_nuevas", {})
        vd = datos.get("verificacion_destapadas", {})
        return self._insert(
            f"""INSERT INTO check_clientes
                (id_entrada, id_usuario, fecha_hora,
                 fecha_recepcion, nombre_cliente, id_sustancia, cantidad,
                 observacion_producto, observaciones,
                 id_usuario_reviso, id_usuario_verifico,
                 vn_nombre, vn_no_lote, vn_cantidad,
                 vn_rotulo_identificacion, vn_fecha_fabricacion,
                 vn_fecha_vencimiento, vn_fabricante, vn_rotulos_seguridad,
                 vn_ficha_seguridad, vn_certificado_calidad,
                 vn_golpes_roturas, vn_cumple_especificaciones,
                 vd_nombre, vd_no_lote, vd_rotulo_identificacion,
                 vd_fecha_vencimiento, vd_certificado_calidad,
                 vd_ficha_seguridad, vd_golpes_roturas,
                 vd_condiciones_almacenamiento, vd_carta_correo)
                VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},
                        {ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},
                        {ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},
                        {ph},{ph},{ph})""",
            (
                datos.get("id_entrada"),
                id_usuario,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                datos.get("fecha_recepcion"),
                datos.get("nombre_cliente"),
                datos.get("id_sustancia"),
                datos.get("cantidad"),
                datos.get("observacion_producto"),
                datos.get("observaciones"),
                datos.get("id_usuario_reviso"),
                datos.get("id_usuario_verifico"),
                vn.get("nombre"), vn.get("no_lote"), vn.get("cantidad"),
                vn.get("rotulo_identificacion"), vn.get("fecha_fabricacion"),
                vn.get("fecha_vencimiento"), vn.get("fabricante"),
                vn.get("rotulos_seguridad"), vn.get("ficha_seguridad"),
                vn.get("certificado_calidad"), vn.get("golpes_roturas"),
                vn.get("cumple_especificaciones"),
                vd.get("nombre"), vd.get("no_lote"), vd.get("rotulo_identificacion"),
                vd.get("fecha_vencimiento"), vd.get("certificado_calidad"),
                vd.get("ficha_seguridad"), vd.get("golpes_roturas"),
                vd.get("condiciones_almacenamiento"), vd.get("carta_correo"),
            ),
        )

    def _row_to_verificacion_cliente(self, r: dict) -> tuple:
        """Devuelve (verificacion_nuevas, verificacion_destapadas) desde columnas planas."""
        vn = {
            "nombre": r.get("vn_nombre", ""),
            "no_lote": r.get("vn_no_lote", ""),
            "cantidad": r.get("vn_cantidad", ""),
            "rotulo_identificacion": r.get("vn_rotulo_identificacion", ""),
            "fecha_fabricacion": r.get("vn_fecha_fabricacion", ""),
            "fecha_vencimiento": r.get("vn_fecha_vencimiento", ""),
            "fabricante": r.get("vn_fabricante", ""),
            "rotulos_seguridad": r.get("vn_rotulos_seguridad", ""),
            "ficha_seguridad": r.get("vn_ficha_seguridad", ""),
            "certificado_calidad": r.get("vn_certificado_calidad", ""),
            "golpes_roturas": r.get("vn_golpes_roturas", ""),
            "cumple_especificaciones": r.get("vn_cumple_especificaciones", ""),
        }
        vd = {
            "nombre": r.get("vd_nombre", ""),
            "no_lote": r.get("vd_no_lote", ""),
            "rotulo_identificacion": r.get("vd_rotulo_identificacion", ""),
            "fecha_vencimiento": r.get("vd_fecha_vencimiento", ""),
            "certificado_calidad": r.get("vd_certificado_calidad", ""),
            "ficha_seguridad": r.get("vd_ficha_seguridad", ""),
            "golpes_roturas": r.get("vd_golpes_roturas", ""),
            "condiciones_almacenamiento": r.get("vd_condiciones_almacenamiento", ""),
            "carta_correo": r.get("vd_carta_correo", ""),
        }
        return vn, vd

    # ══════════════════════════════════════════════════════════════════════
    # BITÁCORA
    # ══════════════════════════════════════════════════════════════════════

    def get_bitacora(
        self,
        filtro_usuario: str = None,
        filtro_operacion: str = None,
    ) -> list:
        where, params = [], []
        if filtro_usuario:
            where.append(f"usuario = {self._ph()}")
            params.append(filtro_usuario)
        if filtro_operacion:
            where.append(f"tipo_operacion = {self._ph()}")
            params.append(filtro_operacion)
        w = ("WHERE " + " AND ".join(where)) if where else ""
        return self._fetchall(
            f"SELECT * FROM bitacora {w} ORDER BY fecha_hora DESC",
            tuple(params),
        )

    def registrar_bitacora(
        self,
        usuario: str,
        tipo_operacion: str,
        id_registro: int,
        campo: str,
        valor_anterior: str = "",
        valor_nuevo: str = "",
    ) -> None:
        ph = self._ph()
        self._execute(
            f"""INSERT INTO bitacora
                (fecha_hora, usuario, tipo_operacion, id_registro,
                 campo, valor_anterior, valor_nuevo)
                VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph})""",
            (
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                str(usuario or ""),
                str(tipo_operacion or "").upper(),
                id_registro or 0,
                str(campo or ""),
                str(valor_anterior or ""),
                str(valor_nuevo or ""),
            ),
        )
        self.commit()


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  FÁBRICA DE CONEXIONES                                                   ║
# ╚══════════════════════════════════════════════════════════════════════════╝

def get_db() -> KardexDB:
    """
    Lee config.json y devuelve una instancia de KardexDB conectada al motor
    configurado (sqlite o sqlserver). Ejecuta migraciones de esquema.
    """
    cfg = _cargar_config()
    motor = cfg.get("motor", "sqlite").lower()

    if motor == "sqlite":
        db_rel = cfg["sqlite"]["path"]
        # Ruta absoluta desde el directorio de database.py
        db_path = os.path.join(_ruta_base(), db_rel)
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        # Ejecutar migraciones de esquema (idempotente)
        _migrar_schema(conn)
        return KardexDB(conn)

    elif motor == "sqlserver":
        if not _PYODBC_DISPONIBLE:
            raise RuntimeError("pyodbc no está instalado. Ejecuta: pip install pyodbc")
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
