"""
Recalcula la huella de las filas que ya están en staging.

Por qué hace falta correrlo UNA vez:

`huella_balance` y `huella_movimiento` pasaron a comparar el VALOR de cada
cifra en vez de su escritura, porque `37719.9` y `37719.90` producían huellas
distintas para el mismo peso y eso marcaba filas como modificadas sin que
nadie hubiera tocado el archivo.

Las filas ya cargadas conservan la huella vieja. Si no se recalculan, el primer
cotejo después del cambio compara huellas nuevas contra viejas y reporta el
archivo completo como modificado -- justo la alerta falsa que se quiere
eliminar. El staging guarda las cifras como texto, así que la huella se
reconstruye exacta sin volver a leer el Excel.

Va carga por carga y no de un solo golpe: movimiento_staging puede tener cientos
de miles de filas y traerlas todas a memoria en un servidor chico no termina bien.

Es idempotente: correrlo dos veces da el mismo resultado.

    python recalcular_huellas.py            # muestra qué cambiaría, sin escribir
    python recalcular_huellas.py --aplicar  # lo escribe
"""
from __future__ import annotations

import sys

import db
import reglas as R

TABLAS = {
    "raw.balance_staging": R.huella_balance,
    "raw.movimiento_staging": R.huella_movimiento,
}


def _escribir(tabla: str, cambios: list[tuple]) -> None:
    """Las huellas nuevas, en un solo UPDATE.

    Un UPDATE por fila no sirve aquí: el índice de staging es por carga_id, y
    como una carga ES toda la tabla, cada uno termina recorriendo el archivo
    completo. Con 122.795 movimientos eso es cuadrático y no termina nunca.

    Se cargan las huellas a una tabla temporal con COPY y se aplica un único
    UPDATE ... FROM: una pasada, unión por hash, sin depender de índices.
    """
    with db.conn() as c:
        with c.cursor() as cur:
            cur.execute("""CREATE TEMP TABLE huella_nueva (
                             huella text, carga_id uuid, hoja text,
                             fila_origen integer) ON COMMIT DROP""")
            with cur.copy("COPY huella_nueva FROM STDIN") as cp:
                for fila in cambios:
                    cp.write_row(fila)
            cur.execute(f"""
                UPDATE {tabla} t SET huella = n.huella
                  FROM huella_nueva n
                 WHERE t.carga_id = n.carga_id
                   AND t.fila_origen = n.fila_origen
                   AND t.hoja IS NOT DISTINCT FROM n.hoja""")
            escritas = cur.rowcount
        c.commit()
    print(f"    escritas {escritas}")


def main(aplicar: bool) -> None:
    total_rev = total_cam = 0

    for tabla, huella in TABLAS.items():
        cargas = [f["carga_id"] for f in
                  db.varios(f"SELECT DISTINCT carga_id FROM {tabla}")]
        print(f"\n{tabla}: {len(cargas)} cargas")

        for cid in cargas:
            filas = db.varios(f"SELECT * FROM {tabla} WHERE carga_id=%s", (cid,))
            # La fila física se identifica por hoja + número de fila: en un
            # archivo de varias hojas el número de fila se repite.
            cambios = [(h, cid, f["hoja"], f["fila_origen"])
                       for f in filas
                       if (h := huella(f)) != f["huella"]]
            total_rev += len(filas)
            total_cam += len(cambios)
            marca = f"{len(cambios)} a corregir" if cambios else "sin cambios"
            print(f"  {str(cid)[:8]}  {len(filas):>7} filas  {marca}")

            if cambios and aplicar:
                _escribir(tabla, cambios)

    print(f"\n{total_rev} filas revisadas, {total_cam} huellas distintas.")
    if not total_cam:
        print("Nada por hacer.")
    elif aplicar:
        print("Aplicado.")
    else:
        print("Nada se escribió. Para aplicarlo:")
        print("  python recalcular_huellas.py --aplicar")


if __name__ == "__main__":
    db.abrir()
    try:
        main("--aplicar" in sys.argv)
    finally:
        db.cerrar()
