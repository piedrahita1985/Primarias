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
        stock_val = common.to_float(e.get("cantidad_actual", e.get("cantidad", 0)))

        alarma_stock = ""
        if cant_min > 0:
            alarma_stock = "BAJO MINIMO" if stock_val < cant_min else "OK"

        rows.append({
            **e,
            "alarma_fv": alarma_fv,
            "alarma_stock": alarma_stock,
            "stock": round(stock_val, 4),
        })

    rows.sort(key=lambda r: (str(r.get("codigo", "")), str(r.get("lote", ""))))
    return rows


def guardar_snapshot():
    """No-op: la DB es la fuente de verdad."""
    return construir_inventario()


def cargar_snapshot():
    return construir_inventario()
