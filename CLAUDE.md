# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Kardex de Estándares Primarios — desktop inventory management system (Tkinter) for tracking primary
chemical standards: entries (`entradas`), withdrawals (`salidas`), loans (`préstamos`), and stock
movements, with role-based permissions and digital signatures on operations.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
python main.py

# Initialize the database (creates admin user if none exists)
python init_db_hybrid.py

# Migrate legacy inventory CSV into the DB
python migrar_inventario.py
```

There is no test suite, linter, or build config in this repo — verify changes by running the app
(`python main.py`) and exercising the relevant screen.

Default seeded credentials: `admin` / `admin` (or `admin123` per README — check `init_db_hybrid.py`
for the current value). Change on first login in a real deployment.

## Architecture

Three-layer, strictly one-directional: **UI → logica → database**. UI code never imports `sqlite3`/
`pyodbc` or writes SQL directly; `logica/` never imports `tkinter`.

- **`database.py`** — single `KardexDB` class wrapping either SQLite or SQL Server (chosen via
  `config.json`, `motor: "sqlite"|"sqlserver"`) behind one interface. Get a connection via
  `get_db()`, which reads `config.json`, opens a **fresh connection**, runs schema
  migrations idempotently on every call, and returns a `KardexDB`. There is no persistent/singleton
  connection — every `logica/` function does `db = get_db(); try: ... finally: db.close()`. Follow
  that pattern for any new logica function.
  - `_migrar_schema_hibrido` and friends (`_add_column_universal`, `_col_existe_universal`, etc.)
    apply additive, idempotent schema migrations on startup for both engines — there is no separate
    migration tool/versioning system. New schema changes go here, guarded by existence checks.
  - `EPSILON_STOCK = 1e-6` is used everywhere stock quantities are compared, to absorb float noise
    from repeated envases↔contenido (container↔content) conversions via `presentacion`. Reuse it;
    don't compare stock floats with bare `==`/`<`.
- **`logica/*_logica.py`** — one module per domain entity (usuarios, entradas, salidas, préstamos,
  sustancias, ubicaciones, etc.), each a thin functional wrapper (`cargar`, `agregar`, `actualizar`,
  `habilitar`/`inhabilitar`) around `KardexDB` calls. `logica/movimientos_common.py` holds shared
  helpers (`to_float`, `cargar_maestras`, text formatting) used by entrada/salida/préstamo logic.
  Business rules that used to live in `KardexDB` (stock validation, quantity adjustments) were
  deliberately pulled out into `entradas_mov_logica.py` / `salidas_mov_logica.py` — keep new
  business logic there, not in `database.py`.
- **`UI/`** — Tkinter views. Two base classes drive most screens:
  - `UI/_base_maestra.py` (`MaestraBase`, a `Toplevel`) — generic CRUD window for catalog/"maestra"
    tables (sustancias, ubicaciones, colores, fabricantes, etc.). Subclasses set class attributes
    (`TITLE`, `LOGICA_MODULE`, `LIST_TITLE`, ...) and implement `_build_form`, `_get_form_data`,
    `_set_form_data`, `_clear_form`, `_list_label`, `_validate`.
  - `UI/_base_movimientos.py` (`MovimientosBase`) — base for entradas/salidas windows: pagination,
    keyboard shortcuts (Ctrl+G save, F5 refresh, Esc close), progress bar, status messages.
  - `UI/_mov_utils.py`, `UI/_searchable_treeview.py`, `UI/_smart_combobox.py` — shared widget
    helpers (uppercasing text vars, numeric-only entry, sortable treeviews, searchable comboboxes).
  - Navigation: `main.py` → `UI/login.py` (`LoginApp`) authenticates via `logica/usuarios_logica.py`
    → opens `UI/menu.py` (`MenuApp`), which gates each module behind the logged-in user's
    per-module permission flags.
- **`auth.py`** — bcrypt hashing for `contrasena` and `firma_password`. `verify_password` accepts
  both bcrypt hashes and legacy plaintext, and callers must rehash-on-success (lazy migration) after
  a successful plaintext verification — see `get_usuario_login` in `database.py` for the pattern to
  copy if you add another password-bearing field.
- **`config.json`** — selects the DB engine (`sqlite` for dev, `sqlserver` for production via
  `pyodbc`). `config/config.py` holds only UI constants (`COLORS`, window size, `PROJECT_NAME`).

## Notable conventions / gotchas

- `data/kardex.db` **is tracked in git** (intentionally — see commit `ed4b63c`, "volver a trackear
  ... para desarrollo compartido en equipo") despite `.gitignore` generally excluding `data/*.db`;
  it's allow-listed with `!data/kardex.db`. Don't assume DB changes are purely local/gitignored —
  check `git status` before broad DB-touching operations, and never commit real credentials into it.
- Text fields (lote, catálogo, potencia, factura, observaciones, etc.) are normalized to upper case
  and whitespace-collapsed before persisting (see `_normalize_text`/`_normalize_record_fields` in
  `logica/entradas_mov_logica.py`) — follow the same normalization for new free-text fields.
- Status/state vocabulary is unified to `HABILITADA`/`INHABILITADA` across all tables — a legacy
  `DESHABILITADA` CHECK constraint was removed by migration; don't reintroduce that spelling.
- Stock-affecting operations (editing entrada/salida quantity or type) must validate sufficient
  stock *before* mutating anything, and keep `log_entradas`/`log_salidas` in sync with `cantidad_actual`
  on the inventory row — see `salidas_mov_logica.py`'s `actualizar_salida` as the reference
  implementation for "validate fully, then commit."
