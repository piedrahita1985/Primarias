"""
migrar_json_a_sql.py  –  Migración de datos JSON → base de datos SQL
=====================================================================
Lee todos los archivos .json del sistema original y los inserta
en la base de datos configurada en config.json.

Uso:
    python migrar_json_a_sql.py

    # Para especificar carpeta de datos:
    python migrar_json_a_sql.py --data ./ruta/a/data

El script es IDEMPOTENTE para catálogos (no duplica si ya existe).
Para tablas transaccionales (entradas, salidas, etc.) limpia e inserta.
"""

import json
import os
import sys
import argparse
from datetime import datetime

# Asegura que database.py esté en el path
sys.path.insert(0, os.path.dirname(__file__))
from database import get_db, KardexDB


# ── Utilidades ──────────────────────────────────────────────────────────────

def leer_json(ruta: str) -> list | dict:
    with open(ruta, "r", encoding="utf-8") as f:
        return json.load(f)

def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ── Migración por tabla ──────────────────────────────────────────────────────

def migrar_catalogos_simples(db: KardexDB, data_dir: str):
    """Catálogos de una sola columna: fabricantes, unidades, condiciones, colores."""

    archivos = {
        "fabricante.json":    ("fabricantes",     "fabricantes",     "fabricantes",     "fabricante"),
        "unidad.json":        ("unidad",           "unidad",          "unidad",          "unidad"),
        "condicion_alm.json": ("condicion_alm",    "condicion_alm",   "condicion_alm",   "condicion"),
        "color_refuerzo.json":("color_refuerzo",   "color_refuerzo",  "color_refuerzo",  "color_refuerzo"),
    }

    for archivo, (json_key, tabla, _, col_valor) in archivos.items():
        ruta = os.path.join(data_dir, archivo)
        if not os.path.exists(ruta):
            log(f"  ⚠ No encontrado: {archivo}")
            continue

        datos = leer_json(ruta)
        # La clave puede diferir: fabricantes vs fabricante
        clave = json_key if json_key in datos else list(datos.keys())[0]
        registros = datos[clave]

        # Verificar si ya hay datos (evitar duplicados)
        existentes = db._fetchall(f"SELECT * FROM {tabla}")
        if existentes:
            log(f"  ✓ {tabla}: ya tiene {len(existentes)} registros, saltando...")
            continue

        ph = db._ph()
        for r in registros:
            db._execute(
                f"INSERT INTO {tabla} ({col_valor}) VALUES ({ph})",
                (r[col_valor],)
            )
        db.commit()
        log(f"  ✓ {tabla}: {len(registros)} registros insertados")


def migrar_tipos_entrada_salida(db: KardexDB, data_dir: str):
    for archivo, tabla, json_key, col in [
        ("tipo_entrada.json", "tipo_entrada", "tipos_entrada", "tipo_entrada"),
        ("tipo_salida.json",  "tipo_salida",  "tipos_salida",  "tipo_salida"),
    ]:
        ruta = os.path.join(data_dir, archivo)
        if not os.path.exists(ruta):
            continue
        datos = leer_json(ruta)
        registros = datos.get(json_key, [])

        existentes = db._fetchall(f"SELECT * FROM {tabla}")
        if existentes:
            log(f"  ✓ {tabla}: ya tiene {len(existentes)} registros, saltando...")
            continue

        ph = db._ph()
        for r in registros:
            db._execute(
                f"INSERT INTO {tabla} ({col}, estado) VALUES ({ph},{ph})",
                (r[col], r.get("estado", "HABILITADA"))
            )
        db.commit()
        log(f"  ✓ {tabla}: {len(registros)} registros insertados")


def migrar_ubicaciones(db: KardexDB, data_dir: str):
    ruta = os.path.join(data_dir, "maestrasUbicaciones.json")
    if not os.path.exists(ruta):
        log("  ⚠ No encontrado: maestrasUbicaciones.json")
        return

    datos = leer_json(ruta)
    registros = datos.get("maestrasUbicaciones", [])

    existentes = db._fetchall("SELECT * FROM maestras_ubicaciones")
    if existentes:
        log(f"  ✓ maestras_ubicaciones: ya tiene {len(existentes)} registros, saltando...")
        return

    ph = db._ph()
    for r in registros:
        db._execute(
            f"INSERT INTO maestras_ubicaciones (ubicacion, no_caja) VALUES ({ph},{ph})",
            (r["ubicacion"], r["no_caja"])
        )
    db.commit()
    log(f"  ✓ maestras_ubicaciones: {len(registros)} registros insertados")


def migrar_usuarios(db: KardexDB, data_dir: str):
    ruta = os.path.join(data_dir, "usuarios.json")
    if not os.path.exists(ruta):
        log("  ⚠ No encontrado: usuarios.json")
        return

    datos = leer_json(ruta)
    registros = datos.get("usuarios", [])

    ph = db._ph()
    insertados = 0
    for r in registros:
        # Evitar duplicar por nombre de usuario
        existe = db._fetchone(
            f"SELECT id FROM usuarios WHERE usuario = {ph}", (r["usuario"],)
        )
        if existe:
            log(f"  ✓ Usuario '{r['usuario']}' ya existe, saltando...")
            continue

        # Insertar usuario
        db._execute(
            f"""INSERT INTO usuarios (usuario, contrasena, nombre, rol, estado, firma_path, firma_password)
                VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph})""",
            (r["usuario"], r["contrasena"], r["nombre"], r["rol"],
             r.get("estado", "HABILITADA"),
             r.get("permisos", {}).get("firma_path"),
             r.get("permisos", {}).get("firma_password"))
        )
        db.commit()

        # Obtener ID insertado
        nuevo = db._fetchone(
            f"SELECT id FROM usuarios WHERE usuario = {ph}", (r["usuario"],)
        )
        uid = nuevo["id"]

        # Insertar permisos
        permisos = r.get("permisos", {})
        campos = ["entradas","salidas","inventario","bitacora","prestamos",
                  "recibidos","sustancias","tipos_entrada","tipos_salida",
                  "fabricantes","unidades","ubicaciones","condiciones","colores","usuarios"]
        vals = [int(bool(permisos.get(c, False))) for c in campos]
        cols_str = ",".join(campos)
        phs_str  = ",".join([ph]*len(campos))
        db._execute(
            f"INSERT INTO permisos_usuario (id_usuario,{cols_str}) VALUES ({ph},{phs_str})",
            (uid, *vals)
        )
        db.commit()
        insertados += 1

    log(f"  ✓ usuarios: {insertados} insertados")


def migrar_sustancias(db: KardexDB, data_dir: str):
    ruta = os.path.join(data_dir, "sustancias.json")
    if not os.path.exists(ruta):
        log("  ⚠ No encontrado: sustancias.json")
        return

    datos = leer_json(ruta)
    registros = datos.get("maestrasSustancias", [])

    existentes = db._fetchall("SELECT * FROM maestras_sustancias")
    if existentes:
        log(f"  ✓ maestras_sustancias: ya tiene {len(existentes)} registros, saltando...")
        return

    ph = db._ph()
    for r in registros:
        db._execute(
            f"""INSERT INTO maestras_sustancias
                (codigo, nombre, propiedad, tipo_muestras, uso_previsto, cantidad_minima, codigo_sistema)
                VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph})""",
            (r["codigo"], r["nombre"], r.get("propiedad"), r.get("tipo_muestras"),
             r.get("uso_previsto"), float(r.get("cantidad_minima") or 0),
             r.get("codigo_sistema"))
        )
    db.commit()
    log(f"  ✓ maestras_sustancias: {len(registros)} registros insertados")


def migrar_inventario(db: KardexDB, data_dir: str):
    ruta = os.path.join(data_dir, "inventario.json")
    if not os.path.exists(ruta):
        log("  ⚠ No encontrado: inventario.json")
        return

    datos = leer_json(ruta)
    registros = datos.get("inventario", [])

    if not registros:
        log("  ℹ inventario.json vacío, saltando...")
        return

    ph = db._ph()
    for r in registros:
        db._execute(
            f"""INSERT INTO inventario
                (id_sustancia, id_ubicacion, id_fabricante, id_unidad,
                 id_condicion, id_color, lote, fecha_vencimiento,
                 cantidad_actual, estado)
                VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})""",
            (r.get("id_sustancia"), r.get("id_ubicacion"), r.get("id_fabricante"),
             r.get("id_unidad"), r.get("id_condicion"), r.get("id_color"),
             r.get("lote"), r.get("fecha_vencimiento"),
             float(r.get("cantidad_actual", 0)), r.get("estado", "ACTIVO"))
        )
    db.commit()
    log(f"  ✓ inventario: {len(registros)} registros insertados")


def migrar_transaccionales(db: KardexDB, data_dir: str):
    """Migra entradas, salidas, préstamos, recibos, recibidos."""
    tablas = [
        ("entradas.json",   "entradas",   "entradas",
         ["id_inventario","id_tipo_entrada","id_usuario","fecha_hora","cantidad","observacion","certificado"]),
        ("salidas.json",    "salidas",    "salidas",
         ["id_inventario","id_tipo_salida","id_usuario","fecha_hora","cantidad","observacion"]),
        ("prestamos.json",  "prestamos",  "prestamos",
         ["id_inventario","id_usuario","fecha_hora","cantidad","solicitante","observacion",
          "estado","fecha_devolucion","cantidad_devuelta","observacion_devolucion"]),
        ("recibos.json",    "recibos",    "recibos",
         ["id_entrada","id_usuario","fecha_hora","observacion"]),
        ("recibidos.json",  "recibidos",  "recibidos",
         ["id_recibo","id_usuario","fecha_hora","observacion"]),
    ]

    ph = db._ph()
    for archivo, json_key, tabla, campos in tablas:
        ruta = os.path.join(data_dir, archivo)
        if not os.path.exists(ruta):
            continue
        datos = leer_json(ruta)
        registros = datos.get(json_key, [])
        if not registros:
            log(f"  ℹ {archivo} vacío, saltando...")
            continue

        cols_str = ",".join(campos)
        phs_str  = ",".join([ph]*len(campos))
        for r in registros:
            vals = [r.get(c) for c in campos]
            db._execute(
                f"INSERT INTO {tabla} ({cols_str}) VALUES ({phs_str})", tuple(vals)
            )
        db.commit()
        log(f"  ✓ {tabla}: {len(registros)} registros insertados")


def migrar_bitacora(db: KardexDB, data_dir: str):
    ruta = os.path.join(data_dir, "bitacora.json")
    if not os.path.exists(ruta):
        return

    datos = leer_json(ruta)
    registros = datos.get("bitacora", [])
    if not registros:
        log("  ℹ bitacora.json vacío, saltando...")
        return

    ph = db._ph()
    for r in registros:
        db._execute(
            f"""INSERT INTO bitacora
                (fecha_hora, usuario, tipo_operacion, id_registro, campo, valor_anterior, valor_nuevo)
                VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph})""",
            (r["fecha_hora"], r["usuario"], r["tipo_operacion"],
             r["id_registro"], r["campo"],
             r.get("valor_anterior",""), r.get("valor_nuevo",""))
        )
    db.commit()
    log(f"  ✓ bitacora: {len(registros)} registros insertados")


# ── Punto de entrada ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Migrar JSON → SQL")
    parser.add_argument(
        "--data", default=os.path.join(os.path.dirname(__file__), "..", "data"),
        help="Carpeta con los archivos .json (default: ../data)"
    )
    args = parser.parse_args()
    data_dir = os.path.abspath(args.data)

    if not os.path.isdir(data_dir):
        print(f"❌ Carpeta no encontrada: {data_dir}")
        sys.exit(1)

    log(f"Iniciando migración desde: {data_dir}")
    db = get_db()

    try:
        log("── Catálogos simples ──────────────────────")
        migrar_catalogos_simples(db, data_dir)
        migrar_tipos_entrada_salida(db, data_dir)
        migrar_ubicaciones(db, data_dir)

        log("── Usuarios ───────────────────────────────")
        migrar_usuarios(db, data_dir)

        log("── Sustancias e inventario ────────────────")
        migrar_sustancias(db, data_dir)
        migrar_inventario(db, data_dir)

        log("── Transaccionales ────────────────────────")
        migrar_transaccionales(db, data_dir)

        log("── Bitácora ───────────────────────────────")
        migrar_bitacora(db, data_dir)

        log("✅ Migración completada sin errores.")

    except Exception as e:
        print(f"\n❌ Error durante la migración: {e}")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
