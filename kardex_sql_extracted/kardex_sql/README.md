# Kardex de Reactivos — Migración a SQL

## Archivos entregados

```
kardex_sql/
├── scripts_sql/
│   ├── 01_crear_tablas_sqlserver.sql   ← Ejecutar en SQL Server (producción)
│   └── 02_crear_tablas_sqlite.sql      ← Ejecutar para desarrollo local
└── python/
    ├── config.json                     ← Configuración del motor (editar aquí)
    ├── database.py                     ← Capa de acceso a datos (reemplaza los JSON)
    └── migrar_json_a_sql.py            ← Script de migración JSON → BD
```

---

## Paso 1 — Instalar dependencias

```bash
pip install pyodbc        # Solo necesario para SQL Server en producción
# sqlite3 ya viene incluido en Python
```

---

## Paso 2 — Crear la base de datos local (SQLite)

```bash
sqlite3 data/kardex.db < scripts_sql/02_crear_tablas_sqlite.sql
```

O también se crea automáticamente al correr la migración.

---

## Paso 3 — Migrar los datos JSON

Coloca los archivos `.json` en la carpeta `data/` y ejecuta:

```bash
cd python/
python migrar_json_a_sql.py
# Si tus JSON están en otra carpeta:
python migrar_json_a_sql.py --data C:\ruta\a\tus\data
```

---

## Paso 4 — Usar database.py en tu código Tkinter

### Antes (con JSON):
```python
with open("data/sustancias.json") as f:
    data = json.load(f)
sustancias = data["maestrasSustancias"]
```

### Ahora (con SQL):
```python
from database import get_db

db = get_db()
sustancias = db.get_sustancias()   # Devuelve lista de dicts — igual que antes
db.close()
```

La interfaz es idéntica: lista de diccionarios. Tu código Tkinter cambia mínimo.

---

## Paso 5 — Pasar a SQL Server (cuando tengas acceso)

1. Editar `python/config.json`:
```json
{
    "motor": "sqlserver",
    "sqlserver": {
        "server":   "SERVIDOR\\INSTANCIA",
        "database": "KardexReactivos",
        "driver":   "ODBC Driver 17 for SQL Server",
        "trusted_connection": true
    }
}
```

2. Ejecutar `scripts_sql/01_crear_tablas_sqlserver.sql` en SQL Server Management Studio.

3. Volver a correr la migración (apuntará ahora a SQL Server):
```bash
python migrar_json_a_sql.py
```

**Eso es todo.** El código Python no cambia nada más.

---

## Métodos disponibles en database.py

| Módulo | Métodos |
|---|---|
| Usuarios | `get_usuario_login`, `get_usuarios`, `crear_usuario`, `actualizar_usuario` |
| Sustancias | `get_sustancias`, `get_sustancia`, `crear_sustancia`, `actualizar_sustancia` |
| Inventario | `get_inventario`, `get_inventario_bajo_minimo`, `crear_inventario`, `actualizar_stock` |
| Entradas | `get_entradas`, `crear_entrada` |
| Salidas | `get_salidas`, `crear_salida` |
| Préstamos | `get_prestamos`, `crear_prestamo`, `devolver_prestamo` |
| Bitácora | `get_bitacora`, `registrar_bitacora` |
| Catálogos | `get_fabricantes`, `get_unidades`, `get_condiciones`, `get_colores`, `get_tipos_entrada`, `get_tipos_salida`, `get_ubicaciones` + sus `crear_*` |

---

## Notas importantes

- **Contraseñas**: Actualmente se guardan en texto plano (igual que en los JSON).
  Para producción se recomienda usar `hashlib` o `bcrypt`.
- **SQLite vs SQL Server**: La única diferencia es la conexión. Toda la lógica SQL
  es compatible entre ambos motores.
- **El código Tkinter no necesita cambios mayores**: solo reemplaza las lecturas
  de JSON por llamadas a `db.get_*()`.
