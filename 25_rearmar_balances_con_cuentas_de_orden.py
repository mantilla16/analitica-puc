"""
Rearma, UNA vez, los balances ya cargados que traen cuentas de orden.

Hasta la migracion 23 el motor descartaba los codigos que empezaban por
8 o 9 al promover el balance. Las filas nunca se perdieron: siguen en
raw.balance_staging. Este script vuelve a promover desde ahi las cargas
vigentes que las tienen, para que aparezcan sin que el auditor tenga que
volver a subir cada archivo.

Lo corre desplegar.sh una sola vez (queda registrado en core.migracion).
Solo toca cargas que:
  · estan asignadas a un encargo (las vigentes del checklist),
  · son de naturaleza BALANCE,
  · tienen en staging al menos un codigo que empieza por 8 o 9.
Una carga que falle se informa y se sigue con las demas: no tumba el
despliegue.
"""
from __future__ import annotations

import db
import servicios as S


def main() -> None:
    db.abrir()
    try:
        cargas = db.varios(
            """SELECT DISTINCT c.id::text AS id, cli.razon_social, ei.tipo
                 FROM core.encargo_insumo ei
                 JOIN core.insumo i ON i.tipo = ei.tipo
                 JOIN core.carga c ON c.id = ei.carga_id
                 JOIN core.cliente cli ON cli.id = c.cliente_id
                WHERE i.naturaleza = 'BALANCE'
                  AND EXISTS (
                        SELECT 1 FROM raw.balance_staging s
                         WHERE s.carga_id = c.id
                           AND left(trim(s.codigo_puc), 1) IN ('8', '9'))
                ORDER BY cli.razon_social, ei.tipo"""
        )
        print(f"  {len(cargas)} balance(s) con cuentas de orden por rearmar")
        for c in cargas:
            try:
                r = S.promover_balance(c["id"])
                print(f"  OK  {c['razon_social'][:40]:40} {c['tipo']:20} "
                      f"{r['del_archivo']} del archivo")
            except Exception as e:
                print(f"  FALLO {c['razon_social'][:40]:40} {c['tipo']:20} "
                      f"{type(e).__name__}: {str(e)[:80]}")
    finally:
        db.cerrar()


if __name__ == "__main__":
    main()
