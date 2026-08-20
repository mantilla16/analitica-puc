"""
Acceso a Postgres. Solo SELECT / INSERT / UPDATE sobre tablas.
La base no tiene funciones ni vistas: toda la lógica está en reglas.py.
"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from typing import Any, Iterable, Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

DSN = os.getenv(
    "AUDITORIA_DSN",
    "postgresql://postgres:postgres@localhost:5432/auditoria_puc",
)

pool = ConnectionPool(DSN, min_size=1, max_size=8, open=False)


def abrir() -> None:
    pool.open()


def cerrar() -> None:
    pool.close()


@contextmanager
def conn() -> Iterator[psycopg.Connection]:
    with pool.connection() as c:
        c.row_factory = dict_row
        yield c


def uno(sql: str, p: tuple = ()) -> dict | None:
    with conn() as c:
        return c.execute(sql, p).fetchone()


def varios(sql: str, p: tuple = ()) -> list[dict]:
    with conn() as c:
        return c.execute(sql, p).fetchall()


def ejecutar(sql: str, p: tuple = ()) -> None:
    with conn() as c:
        c.execute(sql, p)


# =====================================================================
# CATÁLOGO
# =====================================================================

def campos_estandar(naturaleza: str) -> list[dict]:
    return varios(
        """SELECT campo, etiqueta, tipo, requerido, es_llave, orden, ayuda
           FROM core.campo_canonico WHERE naturaleza=%s ORDER BY orden""",
        (naturaleza,),
    )


def sinonimos(naturaleza: str) -> dict[str, str]:
    """{norm: campo} para sugerir el mapeo."""
    filas = varios(
        "SELECT norm, campo FROM core.campo_sinonimo WHERE naturaleza=%s",
        (naturaleza,),
    )
    return {f["norm"]: f["campo"] for f in filas}


def insumo(tipo: str) -> dict | None:
    return uno("SELECT * FROM core.insumo WHERE tipo=%s", (tipo,))


def niveles_cargables() -> dict[str, dict]:
    filas = varios("SELECT * FROM core.nivel_cargable ORDER BY orden")
    return {f["nivel"]: f for f in filas}


def excepciones_naturaleza() -> dict[str, str]:
    filas = varios("SELECT codigo, naturaleza FROM core.puc WHERE naturaleza IS NOT NULL")
    return {f["codigo"]: f["naturaleza"] for f in filas}


def signo_por_clase() -> dict[str, int]:
    filas = varios("SELECT clase, signo FROM core.puc_clase")
    return {f["clase"]: f["signo"] for f in filas}


def nombres_puc() -> dict[str, str]:
    filas = varios("SELECT codigo, nombre FROM core.puc")
    return {f["codigo"]: f["nombre"] for f in filas}


# =====================================================================
# CLIENTE / ENCARGO
# =====================================================================

def cliente_por_nit(nit: str) -> dict | None:
    return uno("SELECT * FROM core.cliente WHERE nit=%s", (nit,))


def crear_cliente(nit: str, razon_social: str, seudonimo: str) -> dict:
    return uno(
        """INSERT INTO core.cliente (nit, razon_social, seudonimo)
           VALUES (%s,%s,%s) RETURNING *""",
        (nit, razon_social, seudonimo),
    )


def encargo_por_corte(cliente_id: str, fecha_corte: date) -> dict | None:
    return uno(
        "SELECT * FROM core.encargo WHERE cliente_id=%s AND fecha_corte=%s",
        (cliente_id, fecha_corte),
    )


def crear_encargo(cliente_id: str, fecha_corte: date, cierre_ant: date,
                  corte_ant: date, responsable: str | None) -> dict:
    return uno(
        """INSERT INTO core.encargo
             (cliente_id, fecha_corte, fecha_cierre_anterior,
              fecha_corte_anterior, responsable)
           VALUES (%s,%s,%s,%s,%s) RETURNING *""",
        (cliente_id, fecha_corte, cierre_ant, corte_ant, responsable),
    )


MATERIALIDADES_DEFECTO = [
    ("PLANEACION", "Materialidad de planeación", None),
    ("EJECUCION",  "Materialidad de desempeño", 75.00),
    ("CIERRE",     "Materialidad de cierre",     50.00),
]


def sembrar_materialidades(encargo_id: str) -> None:
    """Crea las tres filas vacías. El auditor digita los valores."""
    with conn() as c:
        for fase, nombre, pct in MATERIALIDADES_DEFECTO:
            c.execute(
                """INSERT INTO core.materialidad (encargo_id, fase, nombre, porcentaje)
                   VALUES (%s,%s,%s,%s) ON CONFLICT (encargo_id, fase) DO NOTHING""",
                (encargo_id, fase, nombre, pct),
            )
        c.commit()


def materialidades(encargo_id: str) -> list[dict]:
    return varios(
        """SELECT m.*, f.nombre AS fase_nombre, f.orden
           FROM core.materialidad m JOIN core.fase f ON f.fase = m.fase
           WHERE m.encargo_id=%s ORDER BY f.orden""",
        (encargo_id,),
    )


def materialidad_de_fase(encargo_id: str, fase: str) -> dict | None:
    return uno(
        "SELECT * FROM core.materialidad WHERE encargo_id=%s AND fase=%s",
        (encargo_id, fase),
    )


def guardar_materialidad(encargo_id: str, fase: str, valor, porcentaje,
                         aplicar: bool, nombre, usuario) -> dict:
    with conn() as c:
        fila = c.execute(
            """UPDATE core.materialidad
                  SET valor=%s, porcentaje=%s, aplicar=%s,
                      nombre=coalesce(%s, nombre),
                      aprobado_por=%s, actualizado=now()
                WHERE encargo_id=%s AND fase=%s RETURNING *""",
            (valor, porcentaje, aplicar, nombre, usuario, encargo_id, fase),
        ).fetchone()
        if fila:
            c.execute(
                """INSERT INTO core.materialidad_historia
                     (encargo_id, fase, nombre, valor, porcentaje, aplicar, cambiado_por)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (encargo_id, fase, fila["nombre"], valor, porcentaje, aplicar, usuario),
            )
        c.commit()
        return fila


def fases() -> list[dict]:
    return varios("SELECT * FROM core.fase ORDER BY orden")


def fijar_fase(encargo_id: str, fase: str) -> None:
    ejecutar("UPDATE core.encargo SET fase_activa=%s WHERE id=%s", (fase, encargo_id))


def parametros(encargo_id: str) -> dict:
    return uno(
        """SELECT fase_activa, pct_variacion, pct_trivialidad
           FROM core.encargo WHERE id=%s""", (encargo_id,)) or {}


def guardar_parametros(encargo_id: str, pct_variacion, pct_trivialidad) -> None:
    ejecutar(
        "UPDATE core.encargo SET pct_variacion=%s, pct_trivialidad=%s WHERE id=%s",
        (pct_variacion, pct_trivialidad, encargo_id))


def encargo(encargo_id: str) -> dict | None:
    return uno(
        """SELECT e.*, cl.razon_social, cl.nit, cl.seudonimo
           FROM core.encargo e JOIN core.cliente cl ON cl.id=e.cliente_id
           WHERE e.id=%s""",
        (encargo_id,),
    )


def encargos() -> list[dict]:
    return varios(
        """SELECT e.*, cl.razon_social, cl.nit
           FROM core.encargo e JOIN core.cliente cl ON cl.id=e.cliente_id
           ORDER BY e.fecha_corte DESC"""
    )


def checklist(encargo_id: str) -> list[dict]:
    """Una fila por insumo esperado, con la carga asignada si existe."""
    return varios(
        """SELECT i.orden, i.tipo, i.nombre AS insumo, i.requerido,
                  (c.id IS NOT NULL) AS cargado,
                  c.id AS carga_id, c.archivo, c.estado, c.filas_cargadas
           FROM core.insumo i
           LEFT JOIN core.encargo_insumo ei
                  ON ei.tipo=i.tipo AND ei.encargo_id=%s
           LEFT JOIN core.carga c ON c.id=ei.carga_id
           ORDER BY i.orden""",
        (encargo_id,),
    )


# =====================================================================
# PERFIL DE MAPEO
# =====================================================================

def perfil_vigente(cliente_id: str, tipo: str) -> dict | None:
    return uno(
        """SELECT * FROM core.perfil_mapeo
           WHERE cliente_id=%s AND tipo=%s AND vigente""",
        (cliente_id, tipo),
    )


def guardar_perfil(cliente_id: str, tipo: str, mapeo: dict,
                   usuario: str | None) -> dict:
    with conn() as c:
        v = c.execute(
            """SELECT coalesce(max(version),0)+1 AS v FROM core.perfil_mapeo
               WHERE cliente_id=%s AND tipo=%s""",
            (cliente_id, tipo),
        ).fetchone()["v"]
        c.execute(
            """UPDATE core.perfil_mapeo SET vigente=false
               WHERE cliente_id=%s AND tipo=%s AND vigente""",
            (cliente_id, tipo),
        )
        fila = c.execute(
            """INSERT INTO core.perfil_mapeo
                 (cliente_id, tipo, version, mapeo, creado_por)
               VALUES (%s,%s,%s,%s,%s) RETURNING *""",
            (cliente_id, tipo, v, json.dumps(mapeo), usuario),
        ).fetchone()
        c.commit()
        return fila


# =====================================================================
# CARGAS
# =====================================================================

def carga(carga_id: str) -> dict | None:
    return uno(
        """SELECT c.*, i.naturaleza, cl.razon_social
           FROM core.carga c
           JOIN core.insumo i ON i.tipo=c.tipo
           JOIN core.cliente cl ON cl.id=c.cliente_id
           WHERE c.id=%s""",
        (carga_id,),
    )


def carga_por_hash(cliente_id: str, hash_: str) -> dict | None:
    return uno(
        """SELECT * FROM core.carga
           WHERE cliente_id=%s AND hash_sha256=%s AND estado <> 'REEMPLAZADA'
           ORDER BY fecha_carga DESC LIMIT 1""",
        (cliente_id, hash_),
    )


def carga_previa(cliente_id: str, tipo: str, ini: date | None,
                 fin: date | None, excluir: str) -> dict | None:
    """Última carga del mismo cliente, tipo y periodo. Base del cotejo."""
    return uno(
        """SELECT * FROM core.carga
           WHERE cliente_id=%s AND tipo=%s AND id <> %s
             AND periodo_ini IS NOT DISTINCT FROM %s
             AND periodo_fin IS NOT DISTINCT FROM %s
           ORDER BY fecha_carga DESC LIMIT 1""",
        (cliente_id, tipo, excluir, ini, fin),
    )


def crear_carga(cliente_id: str, encargo_id: str, tipo: str, archivo: str,
                hash_: str, ini: date | None, fin: date | None,
                perfil_id: int | None, usuario: str | None) -> dict:
    return uno(
        """INSERT INTO core.carga
             (cliente_id, encargo_id, tipo, archivo, hash_sha256,
              periodo_ini, periodo_fin, perfil_id, subido_por)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
        (cliente_id, encargo_id, tipo, archivo, hash_, ini, fin, perfil_id, usuario),
    )


def actualizar_carga(carga_id: str, **campos: Any) -> None:
    if not campos:
        return
    sets = ", ".join(f"{k}=%s" for k in campos)
    ejecutar(f"UPDATE core.carga SET {sets} WHERE id=%s",
             (*campos.values(), carga_id))


def asignar_insumo(encargo_id: str, tipo: str, carga_id: str) -> None:
    ejecutar(
        """INSERT INTO core.encargo_insumo (encargo_id, tipo, carga_id)
           VALUES (%s,%s,%s)
           ON CONFLICT (encargo_id, tipo)
           DO UPDATE SET carga_id=EXCLUDED.carga_id, asignado_en=now()""",
        (encargo_id, tipo, carga_id),
    )


# =====================================================================
# STAGING
# =====================================================================

COLS = {
    "BALANCE": ["carga_id", "fila_origen", "hoja", "codigo_puc", "nombre_cuenta",
                "nivel", "transaccional", "saldo_inicial", "debito", "credito",
                "saldo_final", "llave", "huella"],
    "MOVIMIENTO": ["carga_id", "fila_origen", "hoja", "fecha", "num_doc",
                   "secuencia", "codigo_puc", "nombre_cuenta", "tercero_nit",
                   "tercero_nombre", "centro_costo", "descripcion", "detalle",
                   "debito", "credito", "llave", "huella"],
}
TABLA = {"BALANCE": "raw.balance_staging", "MOVIMIENTO": "raw.movimiento_staging"}


def copiar_staging(carga_id: str, naturaleza: str, filas: Iterable[dict]) -> int:
    """COPY en streaming: no materializa 122k filas en memoria."""
    cols, tabla, n = COLS[naturaleza], TABLA[naturaleza], 0
    with conn() as c:
        with c.cursor() as cur:
            cur.execute(f"DELETE FROM {tabla} WHERE carga_id=%s", (carga_id,))
            with cur.copy(f"COPY {tabla} ({', '.join(cols)}) FROM STDIN") as cp:
                for f in filas:
                    f["carga_id"] = carga_id
                    cp.write_row([f.get(k) for k in cols])
                    n += 1
        c.commit()
    return n


def huellas_staging(carga_id: str, naturaleza: str) -> dict[str, str]:
    return {
        f["llave"]: f["huella"]
        for f in varios(
            f"SELECT llave, huella FROM {TABLA[naturaleza]} WHERE carga_id=%s",
            (carga_id,),
        )
    }


def staging_balance(carga_id: str) -> list[dict]:
    return varios(
        "SELECT * FROM raw.balance_staging WHERE carga_id=%s ORDER BY fila_origen",
        (carga_id,),
    )


def staging_por_llaves(carga_id: str, naturaleza: str,
                       llaves: list[str]) -> dict[str, dict]:
    if not llaves:
        return {}
    filas = varios(
        f"SELECT * FROM {TABLA[naturaleza]} WHERE carga_id=%s AND llave = ANY(%s)",
        (carga_id, llaves),
    )
    return {f["llave"]: f for f in filas}


# =====================================================================
# PROMOCIÓN A core
# =====================================================================

def promover_balance(carga_id: str, cliente_id: str, filas: list[dict]) -> int:
    cols = ["carga_id", "cliente_id", "codigo_puc", "nombre_cuenta", "nivel",
            "digitos", "clase", "cuenta", "subcuenta", "saldo_inicial",
            "debito", "credito", "saldo_final", "signo", "saldo_natural"]
    with conn() as c:
        with c.cursor() as cur:
            cur.execute("DELETE FROM core.balance WHERE carga_id=%s", (carga_id,))
            with cur.copy(
                f"COPY core.balance ({', '.join(cols)}) FROM STDIN"
            ) as cp:
                for f in filas:
                    f["carga_id"] = carga_id
                    f["cliente_id"] = cliente_id
                    cp.write_row([f.get(k) for k in cols])
        c.commit()
    return len(filas)


def balance_de_carga(carga_id: str) -> list[dict]:
    return varios("SELECT * FROM core.balance WHERE carga_id=%s", (carga_id,))


# =====================================================================
# EVIDENCIA
# =====================================================================

def crear_cotejo(**d: Any) -> dict:
    cols = list(d)
    ph = ", ".join(["%s"] * len(cols))
    return uno(
        f"INSERT INTO core.cotejo ({', '.join(cols)}) VALUES ({ph}) RETURNING *",
        tuple(d.values()),
    )


def insertar_cotejo_detalle(cotejo_id: int, detalles: list[dict]) -> int:
    if not detalles:
        return 0
    cols = ["cotejo_id", "cambio", "llave", "codigo_puc", "num_doc",
            "fecha", "fuera_periodo", "valor_antes", "valor_ahora"]
    with conn() as c:
        with c.cursor() as cur:
            with cur.copy(
                f"COPY core.cotejo_detalle ({', '.join(cols)}) FROM STDIN"
            ) as cp:
                for d in detalles:
                    d["cotejo_id"] = cotejo_id
                    cp.write_row([
                        json.dumps(d[k]) if k in ("valor_antes", "valor_ahora")
                        and d.get(k) is not None else d.get(k)
                        for k in cols
                    ])
        c.commit()
    return len(detalles)


def cotejo_de_carga(carga_id: str) -> dict | None:
    return uno(
        """SELECT * FROM core.cotejo WHERE carga_nueva=%s
           ORDER BY ejecutado_en DESC LIMIT 1""",
        (carga_id,),
    )


def evidencia(cotejo_id: int, solo_fuera: bool, limite: int) -> list[dict]:
    filas = varios(
        """SELECT cambio, codigo_puc, num_doc, fecha, fuera_periodo,
                  valor_antes, valor_ahora
           FROM core.cotejo_detalle
           WHERE cotejo_id=%s AND (NOT %s OR fuera_periodo)
           ORDER BY fuera_periodo DESC, fecha LIMIT %s""",
        (cotejo_id, solo_fuera, limite),
    )
    for f in filas:
        f["descuadre_linea"] = _descuadre_linea(f.get("valor_ahora"))
    return filas


def _descuadre_linea(v: dict | None) -> Decimal | None:
    """saldo_inicial + debito - credito - saldo_final del valor 'ahora'.
    Solo aplica a BALANCE: MOVIMIENTO no trae saldo_inicial/saldo_final."""
    if not v or "saldo_final" not in v:
        return None
    si, d, c, sf = (Decimal(str(v.get(k) or 0))
                    for k in ("saldo_inicial", "debito", "credito", "saldo_final"))
    dif = (si + d - c - sf).quantize(Decimal("0.01"))
    return dif if dif != 0 else None


def crear_alerta(**d: Any) -> dict:
    cols = list(d)
    ph = ", ".join(["%s"] * len(cols))
    return uno(
        f"INSERT INTO core.alerta ({', '.join(cols)}) VALUES ({ph}) RETURNING *",
        tuple(d.values()),
    )


def alertas(estado: str | None = None) -> list[dict]:
    if estado:
        return varios(
            """SELECT a.*, cl.razon_social FROM core.alerta a
               JOIN core.cliente cl ON cl.id=a.cliente_id
               WHERE a.estado=%s ORDER BY a.creada_en DESC LIMIT 100""",
            (estado,),
        )
    return varios(
        """SELECT a.*, cl.razon_social FROM core.alerta a
           JOIN core.cliente cl ON cl.id=a.cliente_id
           ORDER BY a.creada_en DESC LIMIT 100"""
    )


def marcar_alerta(alerta_id: int, **campos: Any) -> None:
    sets = ", ".join(f"{k}=%s" for k in campos)
    ejecutar(f"UPDATE core.alerta SET {sets} WHERE id=%s",
             (*campos.values(), alerta_id))


def crear_hallazgo(**d: Any) -> None:
    cols = list(d)
    ph = ", ".join(["%s"] * len(cols))
    ejecutar(f"INSERT INTO core.hallazgo ({', '.join(cols)}) VALUES ({ph})",
             tuple(d.values()))


def hallazgos(carga_id: str) -> list[dict]:
    return varios(
        "SELECT * FROM core.hallazgo WHERE carga_id=%s ORDER BY detectado_en",
        (carga_id,),
    )
