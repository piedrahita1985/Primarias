# Kardex de Estándares Primarios

Sistema de gestión de inventario de estándares primarios. Permite registrar entradas, salidas, préstamos y movimientos de sustancias, con control de usuarios, permisos por rol y firma digital de operaciones.

## Tecnologías

- **Python 3.12** con interfaz gráfica en **Tkinter**
- **SQLite** (desarrollo) / **SQL Server** (producción)
- **Pillow** — imágenes en la UI y firmas de usuarios
- **pyodbc** — conexión a SQL Server

## Requisitos previos

- Python 3.12 o superior
- Si se usa SQL Server: [ODBC Driver 17 for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)

## Instalación

```bash
# 1. Clonar el repositorio
git clone <url-del-repositorio>
cd Primarias

# 2. Crear entorno virtual
python -m venv .venv

# 3. Activar entorno virtual
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux / macOS

# 4. Instalar dependencias
pip install -r requirements.txt
```

## Configuración

El archivo `config.json` controla qué motor de base de datos se usa. Se crea automáticamente al ejecutar la app por primera vez, o puedes crearlo manualmente:

**SQLite (desarrollo):**
```json
{
    "motor": "sqlite",
    "sqlite": {
        "path": "data/kardex.db"
    }
}
```

**SQL Server (producción):**
```json
{
    "motor": "sqlserver",
    "sqlserver": {
        "server": "SERVIDOR\\INSTANCIA",
        "database": "KardexReactivos",
        "driver": "ODBC Driver 17 for SQL Server",
        "trusted_connection": true,
        "username": "",
        "password": ""
    }
}
```

> Si `trusted_connection` es `true`, el acceso usa autenticación de Windows y `username`/`password` se ignoran.

## Ejecución

```bash
python main.py
```

Al primer arranque se crea la base de datos y el usuario administrador por defecto:

| Campo    | Valor         |
|----------|---------------|
| Usuario  | `admin`       |
| Contraseña | `admin123`  |

> **Cambia la contraseña del administrador tras el primer inicio de sesión.**

## Estructura del proyecto

```
├── main.py                  # Punto de entrada
├── database.py              # Capa de acceso a datos (SQLite / SQL Server)
├── config.json              # Configuración del motor de base de datos
├── requirements.txt         # Dependencias Python
├── config/
│   └── config.py            # Constantes de colores y UI
├── logica/                  # Lógica de negocio por módulo
├── UI/                      # Vistas Tkinter
├── data/                    # Base de datos SQLite (generada en runtime)
├── firmas/                  # Imágenes de firmas (generadas en runtime)
└── imagenes/                # Assets gráficos de la aplicación
```

## Roles de usuario

| Rol        | Descripción                                              |
|------------|----------------------------------------------------------|
| `admin`    | Acceso total al sistema y gestión de usuarios            |
| `analista` | Firma como responsable en operaciones de préstamo        |
| `usuario`  | Operaciones de entrada, salida, inventario y préstamos   |

Los permisos por módulo se configuran individualmente desde la sección **Usuarios** del menú.
