from datetime import date, datetime

from database import get_db
from logica import movimientos_common as common


def sugerir_unidad_id(id_sustancia):
    db = get_db()
    try:
        rows = db.get_inventario()
    finally:
        db.close()
    for e in sorted(rows, key=lambda x: x.get("id", 0), reverse=True):
        if e.get("estado", "ACTIVA") != "ACTIVA":
            continue
        if e.get("id_sustancia") == id_sustancia and e.get("id_unidad"):
            return e.get("id_unidad")
    return None


def construir_inventario():
    db = get_db()
    try:
        entradas = db.get_inventario()
    finally:
        db.close()

    rows = []
    for e in entradas:
        if e.get("estado", "ACTIVA") != "ACTIVA":
            continue

        fecha_v = str(e.get("fecha_vencimiento", "")).strip()
        alarma_fv = ""
        if fecha_v:
            try:
                fv = datetime.strptime(fecha_v, "%Y-%m-%d").date()
                if fv < date.today():
                    alarma_fv = "VENCIDO"
                elif (fv - date.today()).days <= 30:
                    alarma_fv = "PROXIMO A VENCER"
                else:
                    alarma_fv = "OK"
            except ValueError:
                alarma_fv = ""

        cant_min = common.to_float(e.get("cantidad_minima"))
        # cantidad_actual esta en envases (ver "Cantidad (envases)" en el
        # formulario de entradas); la alarma de minimo sigue comparando envases.
        stock_envases = common.to_float(e.get("cantidad_actual", e.get("cantidad", 0)))

        alarma_stock = ""
        if cant_min > 0:
            alarma_stock = "BAJO MINIMO" if stock_envases < cant_min else "OK"

        cantidad_texto = common.texto_envases(stock_envases)

        # Stock = cantidad real de producto disponible (envases x contenido
        # por envase), no el conteo de envases (eso ya lo muestra "cantidad").
        # Se lee de la columna persistida log_inventario.stock (mantenida al
        # dia por actualizar_stock/actualizar_inventario) en vez de
        # recalcularla aqui; solo se recalcula como respaldo si por alguna
        # razon vino vacia. No se agrega la unidad al texto: ya existe una
        # columna "Unidad" separada en Inventario y Stock Analista.
        stock_col = e.get("stock")
        if stock_col is not None:
            stock_texto = f"{round(common.to_float(stock_col), 4):g}"
        else:
            presentacion_val = common.to_float(e.get("presentacion"))
            if presentacion_val > 0:
                stock_texto = f"{round(stock_envases * presentacion_val, 4):g}"
            else:
                stock_texto = f"{round(stock_envases, 4):g}"

        rows.append({
            **e,
            "alarma_fv": alarma_fv,
            "alarma_stock": alarma_stock,
            "stock": stock_texto,
            "cantidad": cantidad_texto,
        })

    rows.sort(key=lambda r: (str(r.get("codigo", "")), str(r.get("lote", ""))))
    return rows


def guardar_snapshot():
    """No-op: la DB es la fuente de verdad."""
    return construir_inventario()


def cargar_snapshot():
    return construir_inventario()
