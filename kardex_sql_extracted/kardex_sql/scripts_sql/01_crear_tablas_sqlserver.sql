-- ============================================================
--  KARDEX DE REACTIVOS - Script de creación de tablas
--  Motor: SQL Server
--  Generado a partir de la estructura JSON del sistema actual
-- ============================================================

-- Ejecutar en orden. Las tablas de catálogos primero,
-- luego las transaccionales que dependen de ellas.

USE [KardexReactivos];  -- Cambia al nombre de tu BD
GO

-- ============================================================
-- 1. CATÁLOGOS BASE (sin dependencias)
-- ============================================================

CREATE TABLE fabricantes (
    id          INT IDENTITY(1,1) PRIMARY KEY,
    fabricante  NVARCHAR(100) NOT NULL
);
GO

CREATE TABLE unidad (
    id      INT IDENTITY(1,1) PRIMARY KEY,
    unidad  NVARCHAR(50) NOT NULL
);
GO

CREATE TABLE condicion_alm (
    id        INT IDENTITY(1,1) PRIMARY KEY,
    condicion NVARCHAR(200) NOT NULL
);
GO

CREATE TABLE color_refuerzo (
    id             INT IDENTITY(1,1) PRIMARY KEY,
    color_refuerzo NVARCHAR(100) NOT NULL
);
GO

CREATE TABLE tipo_entrada (
    id           INT IDENTITY(1,1) PRIMARY KEY,
    tipo_entrada NVARCHAR(100) NOT NULL,
    estado       NVARCHAR(20)  NOT NULL DEFAULT 'HABILITADA'
        CONSTRAINT chk_tipo_entrada_estado CHECK (estado IN ('HABILITADA','DESHABILITADA'))
);
GO

CREATE TABLE tipo_salida (
    id          INT IDENTITY(1,1) PRIMARY KEY,
    tipo_salida NVARCHAR(100) NOT NULL,
    estado      NVARCHAR(20)  NOT NULL DEFAULT 'HABILITADA'
        CONSTRAINT chk_tipo_salida_estado CHECK (estado IN ('HABILITADA','DESHABILITADA'))
);
GO

-- ============================================================
-- 2. UBICACIONES
-- ============================================================

CREATE TABLE maestras_ubicaciones (
    id       INT IDENTITY(1,1) PRIMARY KEY,
    ubicacion NVARCHAR(100) NOT NULL,   -- FREEZER, NEVERA, CABINA...
    no_caja   NVARCHAR(50)  NOT NULL
);
GO

-- ============================================================
-- 3. USUARIOS Y PERMISOS
-- ============================================================

CREATE TABLE usuarios (
    id             INT IDENTITY(1,1) PRIMARY KEY,
    usuario        NVARCHAR(50)  NOT NULL UNIQUE,
    contrasena     NVARCHAR(255) NOT NULL,           -- hash en producción
    nombre         NVARCHAR(150) NOT NULL,
    rol            NVARCHAR(50)  NOT NULL,
    estado         NVARCHAR(20)  NOT NULL DEFAULT 'HABILITADA'
        CONSTRAINT chk_usuario_estado CHECK (estado IN ('HABILITADA','DESHABILITADA')),
    firma_path     NVARCHAR(500) NULL,
    firma_password NVARCHAR(255) NULL
);
GO

-- Permisos por módulo (un registro por usuario)
CREATE TABLE permisos_usuario (
    id            INT IDENTITY(1,1) PRIMARY KEY,
    id_usuario    INT NOT NULL
        CONSTRAINT fk_permisos_usuario REFERENCES usuarios(id) ON DELETE CASCADE,
    entradas      BIT NOT NULL DEFAULT 0,
    salidas       BIT NOT NULL DEFAULT 0,
    inventario    BIT NOT NULL DEFAULT 0,
    bitacora      BIT NOT NULL DEFAULT 0,
    prestamos     BIT NOT NULL DEFAULT 0,
    recibidos     BIT NOT NULL DEFAULT 0,
    sustancias    BIT NOT NULL DEFAULT 0,
    tipos_entrada BIT NOT NULL DEFAULT 0,
    tipos_salida  BIT NOT NULL DEFAULT 0,
    fabricantes   BIT NOT NULL DEFAULT 0,
    unidades      BIT NOT NULL DEFAULT 0,
    ubicaciones   BIT NOT NULL DEFAULT 0,
    condiciones   BIT NOT NULL DEFAULT 0,
    colores       BIT NOT NULL DEFAULT 0,
    usuarios      BIT NOT NULL DEFAULT 0
);
GO

-- ============================================================
-- 4. MAESTRA DE SUSTANCIAS (catálogo principal de reactivos)
-- ============================================================

CREATE TABLE maestras_sustancias (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    codigo          NVARCHAR(50)  NOT NULL,
    nombre          NVARCHAR(200) NOT NULL,
    propiedad       NVARCHAR(100) NULL,       -- cliente dueño del reactivo
    tipo_muestras   NVARCHAR(100) NULL,
    uso_previsto    NVARCHAR(100) NULL,
    cantidad_minima DECIMAL(18,4) NOT NULL DEFAULT 0,
    codigo_sistema  NVARCHAR(100) NULL
);
GO

-- ============================================================
-- 5. INVENTARIO (stock actual por lote/entrada)
-- ============================================================

CREATE TABLE inventario (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    id_sustancia    INT NOT NULL
        CONSTRAINT fk_inv_sustancia REFERENCES maestras_sustancias(id),
    id_ubicacion    INT NULL
        CONSTRAINT fk_inv_ubicacion REFERENCES maestras_ubicaciones(id),
    id_fabricante   INT NULL
        CONSTRAINT fk_inv_fabricante REFERENCES fabricantes(id),
    id_unidad       INT NULL
        CONSTRAINT fk_inv_unidad REFERENCES unidad(id),
    id_condicion    INT NULL
        CONSTRAINT fk_inv_condicion REFERENCES condicion_alm(id),
    id_color        INT NULL
        CONSTRAINT fk_inv_color REFERENCES color_refuerzo(id),
    lote            NVARCHAR(100) NULL,
    fecha_vencimiento DATE        NULL,
    cantidad_actual  DECIMAL(18,4) NOT NULL DEFAULT 0,
    estado          NVARCHAR(20)  NOT NULL DEFAULT 'ACTIVO'
        CONSTRAINT chk_inv_estado CHECK (estado IN ('ACTIVO','AGOTADO','VENCIDO'))
);
GO

-- ============================================================
-- 6. ENTRADAS
-- ============================================================

CREATE TABLE entradas (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    id_inventario   INT NOT NULL
        CONSTRAINT fk_ent_inventario REFERENCES inventario(id),
    id_tipo_entrada INT NOT NULL
        CONSTRAINT fk_ent_tipo REFERENCES tipo_entrada(id),
    id_usuario      INT NOT NULL
        CONSTRAINT fk_ent_usuario REFERENCES usuarios(id),
    fecha_hora      DATETIME     NOT NULL DEFAULT GETDATE(),
    cantidad        DECIMAL(18,4) NOT NULL,
    observacion     NVARCHAR(500) NULL,
    certificado     NVARCHAR(500) NULL      -- ruta al archivo si aplica
);
GO

-- ============================================================
-- 7. SALIDAS
-- ============================================================

CREATE TABLE salidas (
    id             INT IDENTITY(1,1) PRIMARY KEY,
    id_inventario  INT NOT NULL
        CONSTRAINT fk_sal_inventario REFERENCES inventario(id),
    id_tipo_salida INT NOT NULL
        CONSTRAINT fk_sal_tipo REFERENCES tipo_salida(id),
    id_usuario     INT NOT NULL
        CONSTRAINT fk_sal_usuario REFERENCES usuarios(id),
    fecha_hora     DATETIME      NOT NULL DEFAULT GETDATE(),
    cantidad       DECIMAL(18,4) NOT NULL,
    observacion    NVARCHAR(500) NULL
);
GO

-- ============================================================
-- 8. PRÉSTAMOS
-- ============================================================

CREATE TABLE prestamos (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    id_inventario   INT NOT NULL
        CONSTRAINT fk_prest_inventario REFERENCES inventario(id),
    id_usuario      INT NOT NULL
        CONSTRAINT fk_prest_usuario REFERENCES usuarios(id),
    fecha_hora      DATETIME      NOT NULL DEFAULT GETDATE(),
    cantidad        DECIMAL(18,4) NOT NULL,
    solicitante     NVARCHAR(200) NULL,
    observacion     NVARCHAR(500) NULL,
    estado          NVARCHAR(20)  NOT NULL DEFAULT 'PENDIENTE'
        CONSTRAINT chk_prest_estado CHECK (estado IN ('PENDIENTE','DEVUELTO','PARCIAL')),
    fecha_devolucion DATETIME     NULL,
    cantidad_devuelta DECIMAL(18,4) NULL,
    observacion_devolucion NVARCHAR(500) NULL
);
GO

-- ============================================================
-- 9. RECIBOS / RECIBIDOS
-- ============================================================

CREATE TABLE recibos (
    id          INT IDENTITY(1,1) PRIMARY KEY,
    id_entrada  INT NOT NULL
        CONSTRAINT fk_recibo_entrada REFERENCES entradas(id),
    id_usuario  INT NOT NULL
        CONSTRAINT fk_recibo_usuario REFERENCES usuarios(id),
    fecha_hora  DATETIME     NOT NULL DEFAULT GETDATE(),
    observacion NVARCHAR(500) NULL
);
GO

CREATE TABLE recibidos (
    id          INT IDENTITY(1,1) PRIMARY KEY,
    id_recibo   INT NOT NULL
        CONSTRAINT fk_recibido_recibo REFERENCES recibos(id),
    id_usuario  INT NOT NULL
        CONSTRAINT fk_recibido_usuario REFERENCES usuarios(id),
    fecha_hora  DATETIME     NOT NULL DEFAULT GETDATE(),
    observacion NVARCHAR(500) NULL
);
GO

-- ============================================================
-- 10. CHECK CLIENTES / CECIF (listas de verificación)
-- ============================================================

CREATE TABLE check_clientes (
    id         INT IDENTITY(1,1) PRIMARY KEY,
    id_entrada INT NOT NULL
        CONSTRAINT fk_chkc_entrada REFERENCES entradas(id),
    id_usuario INT NOT NULL
        CONSTRAINT fk_chkc_usuario REFERENCES usuarios(id),
    fecha_hora DATETIME NOT NULL DEFAULT GETDATE(),
    estado     NVARCHAR(50) NULL,
    observacion NVARCHAR(500) NULL
);
GO

CREATE TABLE check_cecif (
    id         INT IDENTITY(1,1) PRIMARY KEY,
    id_entrada INT NOT NULL
        CONSTRAINT fk_chkcecif_entrada REFERENCES entradas(id),
    id_usuario INT NOT NULL
        CONSTRAINT fk_chkcecif_usuario REFERENCES usuarios(id),
    fecha_hora DATETIME NOT NULL DEFAULT GETDATE(),
    estado     NVARCHAR(50) NULL,
    observacion NVARCHAR(500) NULL
);
GO

-- ============================================================
-- 11. BITÁCORA (auditoría de todas las operaciones)
-- ============================================================

CREATE TABLE bitacora (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    fecha_hora      DATETIME     NOT NULL DEFAULT GETDATE(),
    usuario         NVARCHAR(50) NOT NULL,
    tipo_operacion  NVARCHAR(100) NOT NULL,   -- ENTRADAS-CREAR, SALIDAS-EDITAR...
    id_registro     INT          NOT NULL,    -- ID del registro afectado
    campo           NVARCHAR(100) NOT NULL,
    valor_anterior  NVARCHAR(MAX) NULL,
    valor_nuevo     NVARCHAR(MAX) NULL
);
GO

-- ============================================================
-- ÍNDICES recomendados para performance
-- ============================================================

CREATE INDEX ix_bitacora_usuario       ON bitacora(usuario);
CREATE INDEX ix_bitacora_tipo          ON bitacora(tipo_operacion);
CREATE INDEX ix_bitacora_fecha         ON bitacora(fecha_hora);
CREATE INDEX ix_inventario_sustancia   ON inventario(id_sustancia);
CREATE INDEX ix_entradas_fecha         ON entradas(fecha_hora);
CREATE INDEX ix_salidas_fecha          ON salidas(fecha_hora);
CREATE INDEX ix_prestamos_estado       ON prestamos(estado);
GO

PRINT 'Tablas creadas correctamente.';
GO
