# migrar_inventario.py - VERSIÓN CORREGIDA
import csv
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from database import get_db


_FECHA_VACIA = {"", "SD", "N.A", "N/R", "NO HAY", "SIN ASIGNAR", "V", "VIGENTE"}


def parse_date(val):
    # Comparacion case-insensitive: la fuente trae "Vigente", "VIGENTE", "No Hay",
    # etc. con capitalizacion inconsistente. Compararlas tal cual dejaba pasar
    # "Vigente" (con mayuscula inicial) como si fuera una fecha valida.
    if not val or str(val).strip().upper() in _FECHA_VACIA:
        return ""
    val = str(val).strip()
    if "-" in val and len(val) >= 10:
        try:
            datetime.strptime(val[:10], "%Y-%m-%d")
            return val[:10]
        except:
            pass
    if "/" in val:
        try:
            return datetime.strptime(val, "%d/%m/%Y").strftime("%Y-%m-%d")
        except:
            pass
    print(f"  ⚠️ Fecha no reconocida, se guarda tal cual: {val!r}")
    return val


_FLOAT_VACIO = {"", "N/A", "N.E", "SIN ASIGNAR", "NO HAY", "0.0", "."}


def parse_float(val, campo="", row_num=None, permitir_negativo=True):
    if not val or str(val).strip().upper() in _FLOAT_VACIO:
        return 0.0
    txt = str(val).strip()
    try:
        f = float(txt.replace(",", "."))
    except ValueError:
        ubicacion = f"fila {row_num}, " if row_num else ""
        print(f"  ⚠️ {ubicacion}campo {campo!r}: valor no numerico {val!r}, se usa 0.0")
        return 0.0
    if f < 0 and not permitir_negativo:
        ubicacion = f"fila {row_num}, " if row_num else ""
        print(f"  ⚠️ {ubicacion}campo {campo!r}: valor negativo {val!r}, revisar el dato de origen")
    return f


def parse_bool(val):
    v = str(val).strip().upper()
    return v in ("SI", "SÍ", "YES", "1", "TRUE", "X")


def normalize_text(val):
    if not val:
        return ""
    return str(val).strip().upper()


def get_or_create_fabricante(db, nombre):
    if not nombre:
        return None
    nombre = normalize_text(nombre)
    for f in db.get_fabricantes():
        if normalize_text(f.get("fabricante", "")) == nombre:
            return f["id"]
    return db.crear_fabricante(nombre)


def get_or_create_unidad(db, nombre):
    if not nombre:
        return None
    nombre = normalize_text(nombre)
    for u in db.get_unidades():
        if normalize_text(u.get("unidad", "")) == nombre:
            return u["id"]
    return db.crear_unidad(nombre)


def get_or_create_condicion(db, nombre):
    if not nombre:
        return None
    nombre = normalize_text(nombre)
    for c in db.get_condiciones():
        if normalize_text(c.get("condicion", "")) == nombre:
            return c["id"]
    return db.crear_condicion(nombre)


def get_or_create_color(db, nombre):
    if not nombre:
        return None
    nombre = normalize_text(nombre)
    for c in db.get_colores():
        if normalize_text(c.get("color_refuerzo", "")) == nombre:
            return c["id"]
    return db.crear_color(nombre)


def get_or_create_ubicacion(db, ubicacion, no_caja):
    if not ubicacion or not no_caja:
        return None
    ubicacion = normalize_text(ubicacion)
    no_caja = normalize_text(no_caja)
    for u in db.get_ubicaciones():
        if normalize_text(u.get("ubicacion", "")) == ubicacion and normalize_text(u.get("no_caja", "")) == no_caja:
            return u["id"]
    return db.crear_ubicacion(ubicacion, no_caja)


def get_or_create_sustancia(db, codigo, nombre, propiedad, tipo_muestras, uso_previsto, cantidad_minima, codigo_sistema):
    if not codigo:
        return None
    codigo = normalize_text(codigo)
    for s in db.get_sustancias():
        if normalize_text(s.get("codigo", "")) == codigo:
            return s["id"]
    
    datos = {
        "codigo": codigo,
        "nombre": normalize_text(nombre) if nombre else "",
        "propiedad": normalize_text(propiedad) if propiedad else "",
        "tipo_muestras": normalize_text(tipo_muestras) if tipo_muestras else "",
        "uso_previsto": normalize_text(uso_previsto) if uso_previsto else "",
        "cantidad_minima": parse_float(cantidad_minima),
        "codigo_sistema": normalize_text(codigo_sistema) if codigo_sistema else "",
    }
    return db.crear_sustancia(datos)


def get_or_create_tipo_entrada_inicial(db):
    for t in db.get_tipos_entrada():
        if normalize_text(t.get("tipo_entrada", "")) == "INICIAL":
            return t["id"]
    return db.crear_tipo_entrada("INICIAL")


def get_admin_user_id(db):
    usuarios = db.get_usuarios()
    for u in usuarios:
        if normalize_text(u.get("usuario", "")) == "ADMIN":
            return u["id"]
    if usuarios:
        return usuarios[0]["id"]
    from logica import usuarios_logica as usr
    admin = usr.agregar([], {
        "usuario": "admin",
        "contrasena": "admin",
        "nombre": "Administrador",
        "rol": "ADMIN",
        "estado": "HABILITADA",
        "permisos": {}
    })
    return admin["id"]


def main(csv_path):
    print("=" * 60)
    print("MIGRADOR DE INVENTARIO - SUSTANCIAS DE REFERENCIA")
    print("=" * 60)
    print(f"Archivo: {csv_path}")
    print("Conectando a la base de datos...")
    
    db = get_db()

    try:
        tipo_inicial_id = get_or_create_tipo_entrada_inicial(db)
        print(f"✓ Tipo de entrada 'INICIAL' ID: {tipo_inicial_id}")
        
        admin_id = get_admin_user_id(db)
        print(f"✓ Usuario admin ID: {admin_id}")
        print("-" * 60)

        with open(csv_path, "r", encoding="utf-8-sig") as f:
            # Usar punto y coma como separador
            reader = csv.DictReader(f, delimiter=';')
            # Limpiar espacios en nombres de columnas
            reader.fieldnames = [name.strip() for name in reader.fieldnames]
            
            print("📋 Columnas detectadas:", reader.fieldnames)
            
            total = 0
            errores = 0
            
            for row_num, row in enumerate(reader, start=1):
                # Limpiar espacios en valores
                row = {k: (v.strip() if v else "") for k, v in row.items()}
                
                codigo = row.get("Código de Programación", "").strip()
                if not codigo:
                    print(f"⚠️ Fila {row_num}: Sin código, omitida")
                    continue

                nombre = row.get("Nombre", "").strip()
                propiedad = row.get("Propiedad", "").strip()
                fabricante = row.get("Fabricante", "").strip()
                tipo_muestras = row.get("Tipo Muestras", "").strip()
                uso_previsto = row.get("Uso Previsto", "").strip()
                cantidad_minima = row.get("Cantidad Mínima", "").strip()
                ubicacion = row.get("Ubicación", "").strip()
                no_caja = row.get("No Caja", "").strip()
                condicion = row.get("Condición Almacenamiento", "").strip()
                color = row.get("Color Refuerzo", "").strip()
                lote = row.get("Lote", "").strip()
                catalogo = row.get("Catalogo", "").strip()
                fecha_ingreso = parse_date(row.get("Fecha de Ingreso", ""))
                fecha_vencimiento = parse_date(row.get("Fecha de Vencimiento", ""))
                unidad = row.get("Unidad", "").strip()
                presentacion = parse_float(row.get("Presentación", ""), campo="Presentación", row_num=row_num)
                potencia = row.get("Potencia", "").strip()
                codigo_sistema = row.get("Código del Sistema", "").strip()

                existencia_total = row.get("Existencia Total", "").strip()
                cantidad_envases = parse_float(
                    existencia_total, campo="Existencia Total", row_num=row_num, permitir_negativo=False
                )

                certificado_anl = parse_bool(row.get("Certificado Analítico", ""))
                ficha_seguridad = parse_bool(row.get("Ficha de Seguridad", ""))
                factura_compra = parse_bool(row.get("Factura de compra", ""))

                # No usar "Propiedad" como fabricante cuando "Fabricante" viene
                # vacio: son columnas distintas (Propiedad describe la sustancia,
                # no quien la fabrica) y mezclarlas ensuciaba el catalogo de
                # fabricantes con valores como "CECIF" o "Vacio".
                id_fabricante = get_or_create_fabricante(db, fabricante)
                id_unidad = get_or_create_unidad(db, unidad)
                id_condicion = get_or_create_condicion(db, condicion)
                id_color = get_or_create_color(db, color)
                id_ubicacion = get_or_create_ubicacion(db, ubicacion, no_caja)

                id_sustancia = get_or_create_sustancia(
                    db, 
                    codigo, 
                    nombre, 
                    propiedad,
                    tipo_muestras, 
                    uso_previsto, 
                    cantidad_minima,
                    codigo_sistema
                )
                
                if not id_sustancia:
                    print(f"❌ Fila {row_num}: Error al crear sustancia {codigo}")
                    errores += 1
                    continue

                cursor = db._conn.cursor()
                cursor.execute(
                    "SELECT id FROM log_inventario WHERE id_sustancia = ? AND lote = ? AND catalogo = ?",
                    (id_sustancia, lote, catalogo)
                )
                if cursor.fetchone():
                    print(f"⏭️ Fila {row_num}: Duplicado {codigo} - lote {lote}, omitido")
                    continue

                stock_total = cantidad_envases * (presentacion if presentacion > 0 else 1)
                estado = "ACTIVO" if cantidad_envases > 0 else "AGOTADO"
                
                cursor.execute("""
                    INSERT INTO log_inventario (
                        id_sustancia, id_ubicacion, id_fabricante, id_unidad,
                        id_condicion, id_color, lote, fecha_vencimiento,
                        cantidad_actual, estado, potencia, catalogo,
                        presentacion, certificado_anl, ficha_seguridad,
                        factura_compra, fecha_entrada, factura, observaciones,
                        costo_unitario, costo_total, stock
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    id_sustancia,
                    id_ubicacion,
                    id_fabricante,
                    id_unidad,
                    id_condicion,
                    id_color,
                    lote,
                    fecha_vencimiento,
                    cantidad_envases,
                    estado,
                    potencia,
                    catalogo,
                    presentacion,
                    1 if certificado_anl else 0,
                    1 if ficha_seguridad else 0,
                    1 if factura_compra else 0,
                    fecha_ingreso,
                    "",
                    "",
                    0.0,
                    0.0,
                    stock_total
                ))
                id_inventario = cursor.lastrowid

                if cantidad_envases > 0:
                    cursor.execute("""
                        INSERT INTO log_entradas (
                            id_inventario, id_tipo_entrada, id_usuario,
                            fecha_hora, cantidad, observacion, certificado
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        id_inventario,
                        tipo_inicial_id,
                        admin_id,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        cantidad_envases,
                        f"Carga inicial - {codigo}",
                        1 if certificado_anl else 0
                    ))

                db._conn.commit()
                total += 1
                
                if total % 10 == 0:
                    print(f"📦 Progreso: {total} registros importados...")
                else:
                    print(f"✓ {codigo} - {nombre[:35] if nombre else 'Sin nombre'}... ({cantidad_envases} {unidad if unidad else 'unid'})")

            print("-" * 60)
            print(f"✅ ¡MIGRACIÓN COMPLETADA!")
            print(f"   • Registros importados: {total}")
            print(f"   • Errores: {errores}")
            print("=" * 60)

    except FileNotFoundError:
        print(f"❌ ERROR: No se encontró el archivo '{csv_path}'")
        print("   Asegúrate de que el archivo esté en la misma carpeta")
    except Exception as e:
        print(f"❌ ERROR: {e}")
        db._conn.rollback()
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("=" * 60)
        print("MIGRADOR DE INVENTARIO")
        print("=" * 60)
        print("Uso: python migrar_inventario.py <archivo.csv>")
        print("Ejemplo: python migrar_inventario.py inventario.csv")
        print("=" * 60)
        sys.exit(1)
    main(sys.argv[1])