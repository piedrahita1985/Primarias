-- ============================================================
--  KARDEX DE REACTIVOS - Script SQLite (desarrollo local)
--  Estructura idéntica a SQL Server, adaptada a SQLite
--  Usar con: sqlite3 kardex.db < 01_crear_tablas_sqlite.sql
-- ============================================================

PRAGMA foreign_keys = ON;

-- ============================================================
-- 1. CATÁLOGOS BASE
-- ============================================================

CREATE TABLE IF NOT EXISTS fabricantes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    fabricante TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS unidad (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    unidad TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS condicion_alm (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    condicion TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS color_refuerzo (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    color_refuerzo TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tipo_entrada (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo_entrada TEXT NOT NULL,
    estado       TEXT NOT NULL DEFAULT 'HABILITADA'
                 CHECK(estado IN ('HABILITADA','DESHABILITADA'))
);

CREATE TABLE IF NOT EXISTS tipo_salida (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo_salida TEXT NOT NULL,
    estado      TEXT NOT NULL DEFAULT 'HABILITADA'
                CHECK(estado IN ('HABILITADA','DESHABILITADA'))
);

-- ============================================================
-- 2. UBICACIONES
-- ============================================================

CREATE TABLE IF NOT EXISTS maestras_ubicaciones (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ubicacion TEXT NOT NULL,
    no_caja   TEXT NOT NULL
);

-- ============================================================
-- 3. USUARIOS Y PERMISOS
-- ============================================================

CREATE TABLE IF NOT EXISTS usuarios (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario        TEXT NOT NULL UNIQUE,
    contrasena     TEXT NOT NULL,
    nombre         TEXT NOT NULL,
    rol            TEXT NOT NULL,
    estado         TEXT NOT NULL DEFAULT 'HABILITADA'
                   CHECK(estado IN ('HABILITADA','DESHABILITADA')),
    firma_path     TEXT,
    firma_password TEXT
);

CREATE TABLE IF NOT EXISTS permisos_usuario (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    id_usuario    INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    entradas      INTEGER NOT NULL DEFAULT 0,
    salidas       INTEGER NOT NULL DEFAULT 0,
    inventario    INTEGER NOT NULL DEFAULT 0,
    bitacora      INTEGER NOT NULL DEFAULT 0,
    prestamos     INTEGER NOT NULL DEFAULT 0,
    recibidos     INTEGER NOT NULL DEFAULT 0,
    sustancias    INTEGER NOT NULL DEFAULT 0,
    tipos_entrada INTEGER NOT NULL DEFAULT 0,
    tipos_salida  INTEGER NOT NULL DEFAULT 0,
    fabricantes   INTEGER NOT NULL DEFAULT 0,
    unidades      INTEGER NOT NULL DEFAULT 0,
    ubicaciones   INTEGER NOT NULL DEFAULT 0,
    condiciones   INTEGER NOT NULL DEFAULT 0,
    colores       INTEGER NOT NULL DEFAULT 0,
    usuarios      INTEGER NOT NULL DEFAULT 0
);

-- ============================================================
-- 4. MAESTRA DE SUSTANCIAS
-- ============================================================

CREATE TABLE IF NOT EXISTS maestras_sustancias (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo          TEXT    NOT NULL,
    nombre          TEXT    NOT NULL,
    propiedad       TEXT,
    tipo_muestras   TEXT,
    uso_previsto    TEXT,
    cantidad_minima REAL    NOT NULL DEFAULT 0,
    codigo_sistema  TEXT
);

-- ============================================================
-- 5. INVENTARIO
-- ============================================================

CREATE TABLE IF NOT EXISTS inventario (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    id_sustancia     INTEGER NOT NULL REFERENCES maestras_sustancias(id),
    id_ubicacion     INTEGER REFERENCES maestras_ubicaciones(id),
    id_fabricante    INTEGER REFERENCES fabricantes(id),
    id_unidad        INTEGER REFERENCES unidad(id),
    id_condicion     INTEGER REFERENCES condicion_alm(id),
    id_color         INTEGER REFERENCES color_refuerzo(id),
    lote             TEXT,
    fecha_vencimiento TEXT,   -- ISO: YYYY-MM-DD
    cantidad_actual  REAL    NOT NULL DEFAULT 0,
    estado           TEXT    NOT NULL DEFAULT 'ACTIVO'
                     CHECK(estado IN ('ACTIVO','AGOTADO','VENCIDO'))
);

-- ============================================================
-- 6. ENTRADAS
-- ============================================================

CREATE TABLE IF NOT EXISTS entradas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    id_inventario   INTEGER NOT NULL REFERENCES inventario(id),
    id_tipo_entrada INTEGER NOT NULL REFERENCES tipo_entrada(id),
    id_usuario      INTEGER NOT NULL REFERENCES usuarios(id),
    fecha_hora      TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    cantidad        REAL    NOT NULL,
    observacion     TEXT,
    certificado     TEXT
);

-- ============================================================
-- 7. SALIDAS
-- ============================================================

CREATE TABLE IF NOT EXISTS salidas (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    id_inventario  INTEGER NOT NULL REFERENCES inventario(id),
    id_tipo_salida INTEGER NOT NULL REFERENCES tipo_salida(id),
    id_usuario     INTEGER NOT NULL REFERENCES usuarios(id),
    fecha_hora     TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    cantidad       REAL    NOT NULL,
    observacion    TEXT
);

-- ============================================================
-- 8. PRÉSTAMOS
-- ============================================================

CREATE TABLE IF NOT EXISTS prestamos (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    id_inventario          INTEGER NOT NULL REFERENCES inventario(id),
    id_usuario             INTEGER NOT NULL REFERENCES usuarios(id),
    fecha_hora             TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    cantidad               REAL    NOT NULL,
    solicitante            TEXT,
    observacion            TEXT,
    estado                 TEXT    NOT NULL DEFAULT 'PENDIENTE'
                           CHECK(estado IN ('PENDIENTE','DEVUELTO','PARCIAL')),
    fecha_devolucion       TEXT,
    cantidad_devuelta      REAL,
    observacion_devolucion TEXT
);

-- ============================================================
-- 9. RECIBOS / RECIBIDOS
-- ============================================================

CREATE TABLE IF NOT EXISTS recibos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    id_entrada  INTEGER NOT NULL REFERENCES entradas(id),
    id_usuario  INTEGER NOT NULL REFERENCES usuarios(id),
    fecha_hora  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    observacion TEXT
);

CREATE TABLE IF NOT EXISTS recibidos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    id_recibo   INTEGER NOT NULL REFERENCES recibos(id),
    id_usuario  INTEGER NOT NULL REFERENCES usuarios(id),
    fecha_hora  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    observacion TEXT
);

-- ============================================================
-- 10. CHECKS
-- ============================================================

CREATE TABLE IF NOT EXISTS check_clientes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    id_entrada  INTEGER NOT NULL REFERENCES entradas(id),
    id_usuario  INTEGER NOT NULL REFERENCES usuarios(id),
    fecha_hora  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    estado      TEXT,
    observacion TEXT
);

CREATE TABLE IF NOT EXISTS check_cecif (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    id_entrada  INTEGER NOT NULL REFERENCES entradas(id),
    id_usuario  INTEGER NOT NULL REFERENCES usuarios(id),
    fecha_hora  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    estado      TEXT,
    observacion TEXT
);

-- ============================================================
-- 11. BITÁCORA
-- ============================================================

CREATE TABLE IF NOT EXISTS bitacora (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_hora     TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    usuario        TEXT    NOT NULL,
    tipo_operacion TEXT    NOT NULL,
    id_registro    INTEGER NOT NULL,
    campo          TEXT    NOT NULL,
    valor_anterior TEXT,
    valor_nuevo    TEXT
);

-- Índices
CREATE INDEX IF NOT EXISTS ix_bitacora_usuario     ON bitacora(usuario);
CREATE INDEX IF NOT EXISTS ix_bitacora_tipo        ON bitacora(tipo_operacion);
CREATE INDEX IF NOT EXISTS ix_bitacora_fecha       ON bitacora(fecha_hora);
CREATE INDEX IF NOT EXISTS ix_inventario_sustancia ON inventario(id_sustancia);
CREATE INDEX IF NOT EXISTS ix_entradas_fecha       ON entradas(fecha_hora);
CREATE INDEX IF NOT EXISTS ix_salidas_fecha        ON salidas(fecha_hora);
CREATE INDEX IF NOT EXISTS ix_prestamos_estado     ON prestamos(estado);

SELECT 'Tablas SQLite creadas correctamente.';
