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


def _col_existe_universal(conn, motor: str, tabla: str, columna: str) -> bool:
    """Detecta si una columna existe - compatible con SQLite y SQL Server."""
    if motor == "sqlite":
        cur = conn.execute(f"PRAGMA table_info({tabla})")
        return any(row[1] == columna for row in cur.fetchall())
    else:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_NAME = ? AND COLUMN_NAME = ?",
            (tabla, columna),
        )
        row = cursor.fetchone()
        return bool(row and row[0] > 0)


def _add_column_universal(conn, motor: str, tabla: str, columna: str,
                          tipo: str, default=None) -> None:
    """Agrega una columna - compatible con SQLite y SQL Server."""
    if motor == "sqlite":
        sql = f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}"
        if default is not None:
            sql += f" DEFAULT {default}"
        conn.execute(sql)
    else:
        sql = f"ALTER TABLE {tabla} ADD {columna} {tipo}"
        if default is not None:
            sql += f" CONSTRAINT DF_{tabla}_{columna} DEFAULT ({default})"
        cursor = conn.cursor()
        cursor.execute(sql)
    conn.commit()


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

    if not _col_existe(conn, "prestamos", "fecha_limite"):
        conn.execute("ALTER TABLE prestamos ADD COLUMN fecha_limite TEXT")

    conn.execute("CREATE INDEX IF NOT EXISTS idx_prestamos_usuario ON prestamos(id_usuario)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_prestamos_destino ON prestamos(id_usuario_destino)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_prestamos_estado ON prestamos(estado_recepcion)")

    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()


def _migrar_schema_hibrido(conn, motor: str) -> None:
    """Migración de esquema compatible con ambos motores (idempotente)."""
    if motor == "sqlite":
        _migrar_schema(conn)
        return

    # ── SQL Server: agregar columnas faltantes ────────────────────────────
    catalogos = [
        "fabricantes", "unidad", "condicion_alm",
        "color_refuerzo", "maestras_ubicaciones", "maestras_sustancias",
    ]
    for tabla in catalogos:
        if not _col_existe_universal(conn, motor, tabla, "estado"):
            _add_column_universal(conn, motor, tabla, "estado",
                                  "NVARCHAR(20) NOT NULL", "'HABILITADA'")

    extra_inventario = [
        ("potencia",        "NVARCHAR(MAX)",          None),
        ("catalogo",        "NVARCHAR(MAX)",          None),
        ("presentacion",    "NVARCHAR(MAX)",          None),
        ("certificado_anl", "INT NOT NULL",           "0"),
        ("ficha_seguridad", "INT NOT NULL",           "0"),
        ("factura_compra",  "INT NOT NULL",           "0"),
        ("fecha_entrada",   "NVARCHAR(30)",           None),
        ("factura",         "NVARCHAR(MAX)",          None),
        ("observaciones",   "NVARCHAR(MAX)",          None),
    ]
    for col, tipo, default in extra_inventario:
        if not _col_existe_universal(conn, motor, "inventario", col):
            _add_column_universal(conn, motor, "inventario", col, tipo, default)

    extra_salidas = [
        ("estado",       "NVARCHAR(20) NOT NULL", "'ACTIVA'"),
        ("actividad",    "NVARCHAR(MAX)",          None),
        ("fecha_salida", "NVARCHAR(30)",           None),
        ("factura",      "NVARCHAR(MAX)",          None),
    ]
    for col, tipo, default in extra_salidas:
        if not _col_existe_universal(conn, motor, "salidas", col):
            _add_column_universal(conn, motor, "salidas", col, tipo, default)

    extra_prestamos = [
        ("id_usuario_destino",    "INT",                   None),
        ("firma_presta_path",     "NVARCHAR(MAX)",          None),
        ("fecha_prestamo",        "NVARCHAR(30)",           None),
        ("estado_recepcion",      "NVARCHAR(20) NOT NULL", "'PENDIENTE'"),
        ("fecha_recepcion",       "NVARCHAR(30)",           None),
        ("observacion_recepcion", "NVARCHAR(MAX)",          None),
        ("id_usuario_recibe",     "INT",                   None),
        ("id_salida_prestamo",    "INT",                   None),
        ("estado_devolucion",     "NVARCHAR(20) NOT NULL", "'NO_APLICA'"),
        ("id_usuario_devuelve",   "INT",                   None),
        ("fecha_limite",          "NVARCHAR(30)",           None),
    ]
    for col, tipo, default in extra_prestamos:
        if not _col_existe_universal(conn, motor, "prestamos", col):
            _add_column_universal(conn, motor, "prestamos", col, tipo, default)


def _crear_tablas_sqlserver(conn) -> None:
    """Crea el esquema base en SQL Server (idempotente)."""
    cursor = conn.cursor()

    def _si_no_existe(nombre, ddl):
        cursor.execute(
            f"IF NOT EXISTS (SELECT * FROM INFORMATION_SCHEMA.TABLES "
            f"WHERE TABLE_NAME = '{nombre}') BEGIN {ddl} END"
        )

    _si_no_existe("fabricantes", """
        CREATE TABLE fabricantes (
            id INT IDENTITY(1,1) PRIMARY KEY,
            fabricante NVARCHAR(255) NOT NULL,
            estado NVARCHAR(20) NOT NULL DEFAULT 'HABILITADA',
            CONSTRAINT uq_fabricantes UNIQUE (fabricante)
        )
    """)
    _si_no_existe("unidad", """
        CREATE TABLE unidad (
            id INT IDENTITY(1,1) PRIMARY KEY,
            unidad NVARCHAR(100) NOT NULL,
            estado NVARCHAR(20) NOT NULL DEFAULT 'HABILITADA',
            CONSTRAINT uq_unidad UNIQUE (unidad)
        )
    """)
    _si_no_existe("condicion_alm", """
        CREATE TABLE condicion_alm (
            id INT IDENTITY(1,1) PRIMARY KEY,
            condicion NVARCHAR(255) NOT NULL,
            estado NVARCHAR(20) NOT NULL DEFAULT 'HABILITADA',
            CONSTRAINT uq_condicion_alm UNIQUE (condicion)
        )
    """)
    _si_no_existe("color_refuerzo", """
        CREATE TABLE color_refuerzo (
            id INT IDENTITY(1,1) PRIMARY KEY,
            color_refuerzo NVARCHAR(100) NOT NULL,
            estado NVARCHAR(20) NOT NULL DEFAULT 'HABILITADA',
            CONSTRAINT uq_color_refuerzo UNIQUE (color_refuerzo)
        )
    """)
    _si_no_existe("tipo_entrada", """
        CREATE TABLE tipo_entrada (
            id INT IDENTITY(1,1) PRIMARY KEY,
            tipo_entrada NVARCHAR(255) NOT NULL,
            estado NVARCHAR(20) NOT NULL DEFAULT 'HABILITADA',
            CONSTRAINT uq_tipo_entrada UNIQUE (tipo_entrada)
        )
    """)
    _si_no_existe("tipo_salida", """
        CREATE TABLE tipo_salida (
            id INT IDENTITY(1,1) PRIMARY KEY,
            tipo_salida NVARCHAR(255) NOT NULL,
            estado NVARCHAR(20) NOT NULL DEFAULT 'HABILITADA',
            CONSTRAINT uq_tipo_salida UNIQUE (tipo_salida)
        )
    """)
    _si_no_existe("maestras_ubicaciones", """
        CREATE TABLE maestras_ubicaciones (
            id INT IDENTITY(1,1) PRIMARY KEY,
            ubicacion NVARCHAR(255) NOT NULL,
            no_caja NVARCHAR(100) NOT NULL,
            estado NVARCHAR(20) NOT NULL DEFAULT 'HABILITADA'
        )
    """)
    _si_no_existe("maestras_sustancias", """
        CREATE TABLE maestras_sustancias (
            id INT IDENTITY(1,1) PRIMARY KEY,
            codigo NVARCHAR(100) NOT NULL,
            nombre NVARCHAR(MAX) NOT NULL,
            propiedad NVARCHAR(MAX),
            tipo_muestras NVARCHAR(MAX),
            uso_previsto NVARCHAR(MAX),
            cantidad_minima FLOAT DEFAULT 0,
            codigo_sistema NVARCHAR(100),
            estado NVARCHAR(20) NOT NULL DEFAULT 'HABILITADA',
            CONSTRAINT uq_maestras_sustancias UNIQUE (codigo)
        )
    """)
    _si_no_existe("usuarios", """
        CREATE TABLE usuarios (
            id INT IDENTITY(1,1) PRIMARY KEY,
            usuario NVARCHAR(100) NOT NULL,
            contrasena NVARCHAR(255) NOT NULL,
            nombre NVARCHAR(255) NOT NULL,
            rol NVARCHAR(50),
            estado NVARCHAR(20) NOT NULL DEFAULT 'HABILITADA',
            firma_path NVARCHAR(MAX),
            firma_password NVARCHAR(255),
            CONSTRAINT uq_usuarios UNIQUE (usuario)
        )
    """)
    _si_no_existe("permisos_usuario", """
        CREATE TABLE permisos_usuario (
            id_usuario INT PRIMARY KEY,
            entradas INT DEFAULT 1,
            salidas INT DEFAULT 1,
            inventario INT DEFAULT 1,
            bitacora INT DEFAULT 1,
            prestamos INT DEFAULT 1,
            recibidos INT DEFAULT 1,
            sustancias INT DEFAULT 1,
            tipos_entrada INT DEFAULT 1,
            tipos_salida INT DEFAULT 1,
            fabricantes INT DEFAULT 1,
            unidades INT DEFAULT 1,
            ubicaciones INT DEFAULT 1,
            condiciones INT DEFAULT 1,
            colores INT DEFAULT 1,
            usuarios INT DEFAULT 1,
            FOREIGN KEY (id_usuario) REFERENCES usuarios(id)
        )
    """)
    _si_no_existe("inventario", """
        CREATE TABLE inventario (
            id INT IDENTITY(1,1) PRIMARY KEY,
            id_sustancia INT NOT NULL,
            id_ubicacion INT,
            id_fabricante INT,
            id_unidad INT,
            id_condicion INT,
            id_color INT,
            lote NVARCHAR(100),
            fecha_vencimiento NVARCHAR(30),
            cantidad_actual FLOAT NOT NULL DEFAULT 0,
            estado NVARCHAR(20) NOT NULL DEFAULT 'ACTIVO'
                CHECK (estado IN ('ACTIVO','AGOTADO','VENCIDO','ANULADO')),
            potencia NVARCHAR(MAX),
            catalogo NVARCHAR(MAX),
            presentacion NVARCHAR(MAX),
            certificado_anl INT NOT NULL DEFAULT 0,
            ficha_seguridad INT NOT NULL DEFAULT 0,
            factura_compra INT NOT NULL DEFAULT 0,
            fecha_entrada NVARCHAR(30),
            factura NVARCHAR(MAX),
            observaciones NVARCHAR(MAX),
            FOREIGN KEY (id_sustancia) REFERENCES maestras_sustancias(id)
        )
    """)
    _si_no_existe("entradas", """
        CREATE TABLE entradas (
            id INT IDENTITY(1,1) PRIMARY KEY,
            id_inventario INT NOT NULL,
            id_tipo_entrada INT NOT NULL,
            id_usuario INT NOT NULL,
            fecha_hora NVARCHAR(30) NOT NULL,
            cantidad FLOAT NOT NULL,
            observacion NVARCHAR(MAX),
            certificado INT DEFAULT 0,
            FOREIGN KEY (id_inventario) REFERENCES inventario(id),
            FOREIGN KEY (id_tipo_entrada) REFERENCES tipo_entrada(id),
            FOREIGN KEY (id_usuario) REFERENCES usuarios(id)
        )
    """)
    _si_no_existe("salidas", """
        CREATE TABLE salidas (
            id INT IDENTITY(1,1) PRIMARY KEY,
            id_inventario INT NOT NULL,
            id_tipo_salida INT NOT NULL,
            id_usuario INT NOT NULL,
            fecha_hora NVARCHAR(30) NOT NULL,
            cantidad FLOAT NOT NULL,
            observacion NVARCHAR(MAX),
            estado NVARCHAR(20) NOT NULL DEFAULT 'ACTIVA',
            actividad NVARCHAR(MAX),
            fecha_salida NVARCHAR(30),
            factura NVARCHAR(MAX),
            FOREIGN KEY (id_inventario) REFERENCES inventario(id),
            FOREIGN KEY (id_tipo_salida) REFERENCES tipo_salida(id),
            FOREIGN KEY (id_usuario) REFERENCES usuarios(id)
        )
    """)
    _si_no_existe("prestamos", """
        CREATE TABLE prestamos (
            id INT IDENTITY(1,1) PRIMARY KEY,
            id_inventario INT NOT NULL,
            id_usuario INT NOT NULL,
            fecha_hora NVARCHAR(30) NOT NULL,
            cantidad FLOAT NOT NULL,
            solicitante NVARCHAR(MAX),
            observacion NVARCHAR(MAX),
            estado NVARCHAR(20) NOT NULL DEFAULT 'PENDIENTE',
            fecha_devolucion NVARCHAR(30),
            cantidad_devuelta FLOAT,
            observacion_devolucion NVARCHAR(MAX),
            id_usuario_destino INT,
            firma_presta_path NVARCHAR(MAX),
            fecha_prestamo NVARCHAR(30),
            estado_recepcion NVARCHAR(20) NOT NULL DEFAULT 'PENDIENTE',
            fecha_recepcion NVARCHAR(30),
            observacion_recepcion NVARCHAR(MAX),
            id_usuario_recibe INT,
            id_salida_prestamo INT,
            estado_devolucion NVARCHAR(20) NOT NULL DEFAULT 'NO_APLICA',
            id_usuario_devuelve INT,
            fecha_limite NVARCHAR(30)
        )
    """)
    _si_no_existe("check_cecif", """
        CREATE TABLE check_cecif (
            id INT IDENTITY(1,1) PRIMARY KEY,
            id_entrada INT, id_usuario INT,
            fecha_hora NVARCHAR(30) NOT NULL,
            estado NVARCHAR(20), observacion NVARCHAR(MAX),
            fecha_recepcion NVARCHAR(30), id_proveedor INT,
            no_orden_compra NVARCHAR(100), id_sustancia INT,
            lote NVARCHAR(100), cantidad NVARCHAR(100),
            observacion_producto NVARCHAR(MAX), observaciones NVARCHAR(MAX),
            id_usuario_aprobo INT, id_usuario_verifico INT,
            ver_nombre NVARCHAR(20), ver_no_lote NVARCHAR(20),
            ver_cantidad NVARCHAR(20), ver_rotulo_identificacion NVARCHAR(20),
            ver_fecha_fabricacion NVARCHAR(20), ver_fecha_vencimiento NVARCHAR(20),
            ver_fabricante NVARCHAR(20), ver_rotulos_seguridad NVARCHAR(20),
            ver_ficha_seguridad NVARCHAR(20), ver_certificado_calidad NVARCHAR(20),
            ver_golpes_roturas NVARCHAR(20), ver_cumple_especificaciones NVARCHAR(20)
        )
    """)
    _si_no_existe("check_clientes", """
        CREATE TABLE check_clientes (
            id INT IDENTITY(1,1) PRIMARY KEY,
            id_entrada INT, id_usuario INT,
            fecha_hora NVARCHAR(30) NOT NULL,
            estado NVARCHAR(20), observacion NVARCHAR(MAX),
            fecha_recepcion NVARCHAR(30), nombre_cliente NVARCHAR(MAX),
            id_sustancia INT, cantidad NVARCHAR(100),
            observacion_producto NVARCHAR(MAX), observaciones NVARCHAR(MAX),
            id_usuario_reviso INT, id_usuario_verifico INT,
            vn_nombre NVARCHAR(20), vn_no_lote NVARCHAR(20),
            vn_cantidad NVARCHAR(20), vn_rotulo_identificacion NVARCHAR(20),
            vn_fecha_fabricacion NVARCHAR(20), vn_fecha_vencimiento NVARCHAR(20),
            vn_fabricante NVARCHAR(20), vn_rotulos_seguridad NVARCHAR(20),
            vn_ficha_seguridad NVARCHAR(20), vn_certificado_calidad NVARCHAR(20),
            vn_golpes_roturas NVARCHAR(20), vn_cumple_especificaciones NVARCHAR(20),
            vd_nombre NVARCHAR(20), vd_no_lote NVARCHAR(20),
            vd_rotulo_identificacion NVARCHAR(20), vd_fecha_vencimiento NVARCHAR(20),
            vd_certificado_calidad NVARCHAR(20), vd_ficha_seguridad NVARCHAR(20),
            vd_golpes_roturas NVARCHAR(20),
            vd_condiciones_almacenamiento NVARCHAR(20), vd_carta_correo NVARCHAR(20)
        )
    """)
    _si_no_existe("bitacora", """
        CREATE TABLE bitacora (
            id INT IDENTITY(1,1) PRIMARY KEY,
            fecha_hora NVARCHAR(30) NOT NULL,
            usuario NVARCHAR(100) NOT NULL,
            tipo_operacion NVARCHAR(100) NOT NULL,
            id_registro INT NOT NULL,
            campo NVARCHAR(100),
            valor_anterior NVARCHAR(MAX),
            valor_nuevo NVARCHAR(MAX)
        )
    """)
    conn.commit()


def _crear_tablas_si_no_existen(conn, motor="sqlite"):
    """Crea el esquema base para una base nueva (idempotente)."""
    if motor == "sqlserver":
        _crear_tablas_sqlserver(conn)
        return
    conn.executescript(
        """
        -- 1. Catálogos base
        CREATE TABLE IF NOT EXISTS fabricantes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fabricante TEXT UNIQUE NOT NULL,
            estado TEXT NOT NULL DEFAULT 'HABILITADA'
        );

        CREATE TABLE IF NOT EXISTS unidad (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unidad TEXT UNIQUE NOT NULL,
            estado TEXT NOT NULL DEFAULT 'HABILITADA'
        );

        CREATE TABLE IF NOT EXISTS condicion_alm (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            condicion TEXT UNIQUE NOT NULL,
            estado TEXT NOT NULL DEFAULT 'HABILITADA'
        );

        CREATE TABLE IF NOT EXISTS color_refuerzo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            color_refuerzo TEXT UNIQUE NOT NULL,
            estado TEXT NOT NULL DEFAULT 'HABILITADA'
        );

        CREATE TABLE IF NOT EXISTS tipo_entrada (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_entrada TEXT UNIQUE NOT NULL,
            estado TEXT NOT NULL DEFAULT 'HABILITADA'
        );

        CREATE TABLE IF NOT EXISTS tipo_salida (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_salida TEXT UNIQUE NOT NULL,
            estado TEXT NOT NULL DEFAULT 'HABILITADA'
        );

        CREATE TABLE IF NOT EXISTS maestras_ubicaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ubicacion TEXT NOT NULL,
            no_caja TEXT NOT NULL,
            estado TEXT NOT NULL DEFAULT 'HABILITADA'
        );

        CREATE TABLE IF NOT EXISTS maestras_sustancias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT UNIQUE NOT NULL,
            nombre TEXT NOT NULL,
            propiedad TEXT,
            tipo_muestras TEXT,
            uso_previsto TEXT,
            cantidad_minima REAL DEFAULT 0,
            codigo_sistema TEXT,
            estado TEXT NOT NULL DEFAULT 'HABILITADA'
        );

        -- 2. Usuarios y permisos
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            contrasena TEXT NOT NULL,
            nombre TEXT NOT NULL,
            rol TEXT,
            estado TEXT NOT NULL DEFAULT 'HABILITADA',
            firma_path TEXT,
            firma_password TEXT
        );

        CREATE TABLE IF NOT EXISTS permisos_usuario (
            id_usuario INTEGER PRIMARY KEY REFERENCES usuarios(id) ON DELETE CASCADE,
            entradas INTEGER DEFAULT 1,
            salidas INTEGER DEFAULT 1,
            inventario INTEGER DEFAULT 1,
            bitacora INTEGER DEFAULT 1,
            prestamos INTEGER DEFAULT 1,
            recibidos INTEGER DEFAULT 1,
            sustancias INTEGER DEFAULT 1,
            tipos_entrada INTEGER DEFAULT 1,
            tipos_salida INTEGER DEFAULT 1,
            fabricantes INTEGER DEFAULT 1,
            unidades INTEGER DEFAULT 1,
            ubicaciones INTEGER DEFAULT 1,
            condiciones INTEGER DEFAULT 1,
            colores INTEGER DEFAULT 1,
            usuarios INTEGER DEFAULT 1
        );

        -- 3. Inventario y movimientos
        CREATE TABLE IF NOT EXISTS inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_sustancia INTEGER NOT NULL REFERENCES maestras_sustancias(id),
            id_ubicacion INTEGER REFERENCES maestras_ubicaciones(id),
            id_fabricante INTEGER REFERENCES fabricantes(id),
            id_unidad INTEGER REFERENCES unidad(id),
            id_condicion INTEGER REFERENCES condicion_alm(id),
            id_color INTEGER REFERENCES color_refuerzo(id),
            lote TEXT,
            fecha_vencimiento TEXT,
            cantidad_actual REAL NOT NULL DEFAULT 0,
            estado TEXT NOT NULL DEFAULT 'ACTIVO' CHECK(estado IN ('ACTIVO','AGOTADO','VENCIDO','ANULADO')),
            potencia TEXT,
            catalogo TEXT,
            presentacion TEXT,
            certificado_anl INTEGER NOT NULL DEFAULT 0,
            ficha_seguridad INTEGER NOT NULL DEFAULT 0,
            factura_compra INTEGER NOT NULL DEFAULT 0,
            fecha_entrada TEXT,
            factura TEXT,
            observaciones TEXT
        );

        CREATE TABLE IF NOT EXISTS entradas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_inventario INTEGER NOT NULL REFERENCES inventario(id) ON DELETE RESTRICT,
            id_tipo_entrada INTEGER NOT NULL REFERENCES tipo_entrada(id),
            id_usuario INTEGER NOT NULL REFERENCES usuarios(id),
            fecha_hora TEXT NOT NULL,
            cantidad REAL NOT NULL,
            observacion TEXT,
            certificado INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS salidas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_inventario INTEGER NOT NULL REFERENCES inventario(id) ON DELETE RESTRICT,
            id_tipo_salida INTEGER NOT NULL REFERENCES tipo_salida(id),
            id_usuario INTEGER NOT NULL REFERENCES usuarios(id),
            fecha_hora TEXT NOT NULL,
            cantidad REAL NOT NULL,
            observacion TEXT,
            estado TEXT NOT NULL DEFAULT 'ACTIVA',
            actividad TEXT,
            fecha_salida TEXT,
            factura TEXT
        );

        -- 4. Préstamos
        CREATE TABLE IF NOT EXISTS prestamos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_inventario INTEGER NOT NULL,
            id_usuario INTEGER NOT NULL,
            fecha_hora TEXT NOT NULL,
            cantidad REAL NOT NULL,
            solicitante TEXT,
            observacion TEXT,
            estado TEXT NOT NULL DEFAULT 'PENDIENTE',
            fecha_devolucion TEXT,
            cantidad_devuelta REAL,
            observacion_devolucion TEXT,
            id_usuario_destino INTEGER,
            firma_presta_path TEXT,
            fecha_prestamo TEXT,
            estado_recepcion TEXT NOT NULL DEFAULT 'PENDIENTE',
            fecha_recepcion TEXT,
            observacion_recepcion TEXT,
            id_usuario_recibe INTEGER,
            id_salida_prestamo INTEGER,
            estado_devolucion TEXT NOT NULL DEFAULT 'NO_APLICA',
            id_usuario_devuelve INTEGER,
            fecha_limite TEXT
        );

        -- 5. Checklists
        CREATE TABLE IF NOT EXISTS check_cecif (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_entrada INTEGER,
            id_usuario INTEGER,
            fecha_hora TEXT NOT NULL,
            estado TEXT,
            observacion TEXT,
            fecha_recepcion TEXT,
            id_proveedor INTEGER,
            no_orden_compra TEXT,
            id_sustancia INTEGER,
            lote TEXT,
            cantidad TEXT,
            observacion_producto TEXT,
            observaciones TEXT,
            id_usuario_aprobo INTEGER,
            id_usuario_verifico INTEGER,
            ver_nombre TEXT,
            ver_no_lote TEXT,
            ver_cantidad TEXT,
            ver_rotulo_identificacion TEXT,
            ver_fecha_fabricacion TEXT,
            ver_fecha_vencimiento TEXT,
            ver_fabricante TEXT,
            ver_rotulos_seguridad TEXT,
            ver_ficha_seguridad TEXT,
            ver_certificado_calidad TEXT,
            ver_golpes_roturas TEXT,
            ver_cumple_especificaciones TEXT
        );

        CREATE TABLE IF NOT EXISTS check_clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_entrada INTEGER,
            id_usuario INTEGER,
            fecha_hora TEXT NOT NULL,
            estado TEXT,
            observacion TEXT,
            fecha_recepcion TEXT,
            nombre_cliente TEXT,
            id_sustancia INTEGER,
            cantidad TEXT,
            observacion_producto TEXT,
            observaciones TEXT,
            id_usuario_reviso INTEGER,
            id_usuario_verifico INTEGER,
            vn_nombre TEXT,
            vn_no_lote TEXT,
            vn_cantidad TEXT,
            vn_rotulo_identificacion TEXT,
            vn_fecha_fabricacion TEXT,
            vn_fecha_vencimiento TEXT,
            vn_fabricante TEXT,
            vn_rotulos_seguridad TEXT,
            vn_ficha_seguridad TEXT,
            vn_certificado_calidad TEXT,
            vn_golpes_roturas TEXT,
            vn_cumple_especificaciones TEXT,
            vd_nombre TEXT,
            vd_no_lote TEXT,
            vd_rotulo_identificacion TEXT,
            vd_fecha_vencimiento TEXT,
            vd_certificado_calidad TEXT,
            vd_ficha_seguridad TEXT,
            vd_golpes_roturas TEXT,
            vd_condiciones_almacenamiento TEXT,
            vd_carta_correo TEXT
        );

        -- 6. Bitácora
        CREATE TABLE IF NOT EXISTS bitacora (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora TEXT NOT NULL,
            usuario TEXT NOT NULL,
            tipo_operacion TEXT NOT NULL,
            id_registro INTEGER NOT NULL,
            campo TEXT,
            valor_anterior TEXT,
            valor_nuevo TEXT
        );
        """
    )
    conn.commit()


def _sembrar_admin_si_no_existe(conn, motor="sqlite"):
    """Inserta un admin por defecto en una base nueva sin usuarios."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    row = cursor.fetchone()
    total = int(row[0] if row else 0)
    if total > 0:
        return

    cursor.execute(
        "INSERT INTO usuarios (usuario, contrasena, nombre, rol, estado) "
        "VALUES (?, ?, ?, ?, ?)",
        ("admin", "admin", "Administrador", "ADMIN", "HABILITADA"),
    )
    if motor == "sqlite":
        admin_id = cursor.lastrowid
    else:
        cursor.execute("SELECT SCOPE_IDENTITY() AS id")
        row = cursor.fetchone()
        admin_id = int(row[0]) if row and row[0] is not None else None

    if admin_id:
        cursor.execute(
            "INSERT INTO permisos_usuario "
            "(id_usuario, entradas, salidas, inventario, bitacora, prestamos, "
            "recibidos, sustancias, tipos_entrada, tipos_salida, fabricantes, "
            "unidades, ubicaciones, condiciones, colores, usuarios) "
            "VALUES (?,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1)",
            (admin_id,),
        )
    conn.commit()


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  CLASE PRINCIPAL                                                         ║
# ╚══════════════════════════════════════════════════════════════════════════╝

class KardexDB:
    """Interfaz unificada. Funciona igual con SQLite y SQL Server."""

    def __init__(self, conn, motor="sqlite"):
        self._conn = conn
        self._cursor = conn.cursor()
        self._motor = motor

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
        lid = self._last_insert_id()
        return lid if lid else 0

    def _last_insert_id(self) -> int:
        if self._motor == "sqlite":
            return self._cursor.lastrowid
        else:
            self._cursor.execute("SELECT SCOPE_IDENTITY() AS id")
            row = self._cursor.fetchone()
            return int(row[0]) if row and row[0] is not None else None

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
                 fecha_limite, estado_recepcion, estado_devolucion)
                VALUES ({ph},{ph},{ph},{ph},{ph},{ph},'PENDIENTE',{ph},{ph},{ph},{ph},'PENDIENTE','NO_APLICA')""",
            (
                id_inv, id_usuario, now,
                float(datos.get("cantidad", 0)),
                datos.get("solicitante"),
                datos.get("observacion"),
                datos.get("id_usuario_destino"),
                datos.get("firma_presta_path"),
                datos.get("fecha_prestamo", now[:10]),
                datos.get("fecha_limite") or None,
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
        _crear_tablas_si_no_existen(conn, "sqlite")
        _sembrar_admin_si_no_existe(conn, "sqlite")
        _migrar_schema_hibrido(conn, "sqlite")
        return KardexDB(conn, motor="sqlite")

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
        _crear_tablas_si_no_existen(conn, "sqlserver")
        _sembrar_admin_si_no_existe(conn, "sqlserver")
        _migrar_schema_hibrido(conn, "sqlserver")
        return KardexDB(conn, motor="sqlserver")

    else:
        raise ValueError(f"Motor desconocido: '{motor}'. Usa 'sqlite' o 'sqlserver'.")
