"""
Acceso a Postgres. Solo SELECT / INSERT / UPDATE sobre tablas.
La base no tiene funciones ni vistas: toda la lógica está en reglas.py.
"""
from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import date, datetime
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
        """SELECT fase_activa, pct_variacion, pct_trivialidad,
                  aplica_variacion, aplica_trivialidad
           FROM core.encargo WHERE id=%s""", (encargo_id,)) or {}


def guardar_parametros(encargo_id: str, pct_variacion, pct_trivialidad,
                       aplica_variacion: bool, aplica_trivialidad: bool) -> None:
    ejecutar(
        """UPDATE core.encargo
              SET pct_variacion=%s, pct_trivialidad=%s,
                  aplica_variacion=%s, aplica_trivialidad=%s
            WHERE id=%s""",
        (pct_variacion, pct_trivialidad, aplica_variacion,
         aplica_trivialidad, encargo_id))


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


def eliminar_encargo(encargo_id: str) -> None:
    """Borra el encargo y TODAS las cargas creadas bajo él -- no solo la
    que quedó asignada al final en el checklist, también las intermedias
    que una recarga fue dejando huérfanas por el camino -- salvo que
    algún OTRO encargo las esté usando todavía (ej. movimientos
    reutilizados como MOV_ANTERIOR de un año distinto; ese caso sigue
    vivo). Si no se barren también las intermedias, carga_previa() puede
    terminar comparando contra una de esas huérfanas vacías en vez del
    original."""
    huerfanas = varios(
        """SELECT c.id FROM core.carga c
           WHERE c.encargo_id=%s
             AND NOT EXISTS (
               SELECT 1 FROM core.encargo_insumo ei
               WHERE ei.carga_id = c.id AND ei.encargo_id <> %s
             )""",
        (encargo_id, encargo_id),
    )
    ejecutar("DELETE FROM core.encargo WHERE id=%s", (encargo_id,))
    for f in huerfanas:
        ejecutar("DELETE FROM core.carga WHERE id=%s", (f["carga_id"],))


def checklist(encargo_id: str) -> list[dict]:
    """Una fila por insumo esperado, con la carga asignada si existe."""
    return varios(
        """SELECT i.orden, i.tipo, i.nombre AS insumo, i.requerido,
                  (c.id IS NOT NULL) AS cargado,
                  c.id AS carga_id, c.archivo, c.estado, c.filas_cargadas,
                  (SELECT count(*) FROM core.hallazgo h WHERE h.carga_id=c.id)
                    AS n_hallazgos,
                  (SELECT count(*) FROM core.balance b WHERE b.carga_id=c.id)
                    AS filas_en_balance
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
    """Última carga VÁLIDA del mismo cliente, tipo y periodo -- base del
    cotejo. Excluye REEMPLAZADA/RECHAZADA: son recargas sin cambios o que
    fallaron al procesar, no representan el dato bueno. Sin este filtro,
    una cadena de recargas idénticas termina comparando contra la última
    de esas en vez de contra la que sí tiene el balance."""
    return uno(
        """SELECT * FROM core.carga
           WHERE cliente_id=%s AND tipo=%s AND id <> %s
             AND periodo_ini IS NOT DISTINCT FROM %s
             AND periodo_fin IS NOT DISTINCT FROM %s
             AND estado NOT IN ('REEMPLAZADA', 'RECHAZADA')
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


def cuadre_documentos(carga_id: str, limite: int = 100) -> dict:
    """¿Cada documento contable cuadra en sí mismo?

    Es un control sobre el archivo de MOVIMIENTOS, que es la única fuente
    independiente que tiene el papel. Si un documento no cuadra, ese
    documento llegó incompleto, y toda cuenta que toque queda con una suma
    de movimientos que no se sostiene -- aunque el balance, por su lado,
    cuadre perfectamente. Es el caso exacto que el cruce contra movimientos
    no puede ver por sí solo: suma por cuenta, no por documento.

    El control declara su propia confiabilidad. Agrupar por `num_doc`
    supone que ese número identifica UN documento; si el ERP reusa el
    consecutivo, un documento agrupado abarcaría varias fechas y los
    descuadres reportados serían falsos. Eso se cuenta y se devuelve, en vez
    de suponer que el supuesto se cumple.
    """
    base = """FROM raw.movimiento_staging
              WHERE carga_id=%s AND num_doc IS NOT NULL AND num_doc <> ''"""

    tot = uno(
        f"""WITH doc AS (
                SELECT num_doc,
                       sum(debito::numeric - credito::numeric) AS diferencia,
                       count(DISTINCT fecha) AS fechas
                {base}
                GROUP BY num_doc)
            SELECT count(*) AS documentos,
                   count(*) FILTER (WHERE diferencia <> 0) AS descuadrados,
                   coalesce(sum(abs(diferencia)) FILTER (WHERE diferencia <> 0), 0)
                     AS monto_descuadrado,
                   count(*) FILTER (WHERE fechas > 1) AS multi_fecha
              FROM doc""",
        (carga_id,),
    )

    sin_doc = uno(
        """SELECT count(*) AS n FROM raw.movimiento_staging
           WHERE carga_id=%s AND (num_doc IS NULL OR num_doc = '')""",
        (carga_id,),
    )["n"]

    detalle = varios(
        f"""WITH doc AS (
                SELECT num_doc, count(*) AS lineas,
                       min(fecha) AS fecha,
                       sum(debito::numeric)  AS debito,
                       sum(credito::numeric) AS credito,
                       sum(debito::numeric - credito::numeric) AS diferencia
                {base}
                GROUP BY num_doc)
            SELECT * FROM doc WHERE diferencia <> 0
             ORDER BY abs(diferencia) DESC LIMIT %s""",
        (carga_id, limite),
    )

    # Las cuentas que quedan contaminadas: son exactamente aquellas donde el
    # cruce contra movimientos no puede concluir nada.
    cuentas = varios(
        f"""WITH malos AS (
                SELECT num_doc
                {base}
                GROUP BY num_doc
                HAVING sum(debito::numeric - credito::numeric) <> 0)
            SELECT left(m.codigo_puc, 4) AS cuenta, count(*) AS lineas,
                   sum(abs(m.debito::numeric - m.credito::numeric)) AS monto
              FROM raw.movimiento_staging m
              JOIN malos ON malos.num_doc = m.num_doc
             WHERE m.carga_id=%s AND m.codigo_puc IS NOT NULL
             GROUP BY 1 ORDER BY 3 DESC LIMIT 50""",
        (carga_id, carga_id),
    )

    return {**tot, "lineas_sin_documento": sin_doc,
            "detalle": detalle, "cuentas_afectadas": cuentas}


def hallazgos_detalle(carga_id: str) -> list[dict]:
    """Los hallazgos con el nombre y las cifras de la cuenta al lado.

    Sin esto el hallazgo dice que la línea no cuadra pero no con qué
    números, y el auditor tiene que ir a buscarlos al balance a mano --
    que es justo el trabajo que la herramienta debería ahorrarle.

    El balance promovido no guarda `fila_origen`, así que la unión va por
    código; el DISTINCT ON evita que un código repetido en el archivo
    multiplique el hallazgo en la respuesta.
    """
    return varios(
        """SELECT h.id, h.tipo, h.severidad, h.codigo_puc, h.monto,
                  h.descripcion, h.fila_origen, h.detectado_en,
                  b.nombre_cuenta, b.saldo_inicial, b.debito, b.credito,
                  b.saldo_final
           FROM core.hallazgo h
           LEFT JOIN (
               SELECT DISTINCT ON (codigo_puc)
                      codigo_puc, nombre_cuenta, saldo_inicial,
                      debito, credito, saldo_final
                 FROM core.balance
                WHERE carga_id=%s
                ORDER BY codigo_puc
           ) b ON b.codigo_puc = h.codigo_puc
          WHERE h.carga_id=%s
          ORDER BY h.severidad, h.codigo_puc NULLS FIRST, h.id""",
        (carga_id, carga_id),
    )


def hallazgos(carga_id: str) -> list[dict]:
    return varios(
        "SELECT * FROM core.hallazgo WHERE carga_id=%s ORDER BY detectado_en",
        (carga_id,),
    )


# =====================================================================
# USUARIOS Y SESIONES
# =====================================================================

def usuario_por_nombre(usuario: str) -> dict | None:
    return uno("SELECT * FROM core.usuario WHERE usuario=%s", (usuario,))


def usuario_por_id(usuario_id: str) -> dict | None:
    return uno("SELECT * FROM core.usuario WHERE id=%s", (usuario_id,))


def usuarios() -> list[dict]:
    return varios(
        """SELECT id, usuario, nombre, correo, rol, activo, creado_en, ultimo_acceso
           FROM core.usuario ORDER BY activo DESC, usuario"""
    )


def usuarios_activos() -> list[dict]:
    """Auditores activos: los que pueden ser responsables de un encargo.
    Se excluye ADMIN porque es un rol de administración del sistema, no
    alguien a quien se le asigne un encargo. Devuelve solo usuario y
    nombre, y no exige rol ADMIN para consultarse: cualquier auditor
    necesita poder elegir a un colega."""
    return varios(
        """SELECT usuario, nombre FROM core.usuario
           WHERE activo AND rol = 'AUDITOR' ORDER BY nombre"""
    )


def hay_usuarios() -> bool:
    return (uno("SELECT count(*) AS n FROM core.usuario") or {}).get("n", 0) > 0


def crear_usuario(usuario: str, nombre: str, correo: str | None,
                  clave_hash: str, rol: str) -> dict:
    return uno(
        """INSERT INTO core.usuario (usuario, nombre, correo, clave_hash, rol)
           VALUES (%s,%s,%s,%s,%s)
           RETURNING id, usuario, nombre, correo, rol, activo, creado_en""",
        (usuario, nombre, correo, clave_hash, rol),
    )


def actualizar_usuario(usuario_id: str, **campos: Any) -> dict | None:
    if not campos:
        return usuario_por_id(usuario_id)
    sets = ", ".join(f"{k}=%s" for k in campos)
    return uno(
        f"""UPDATE core.usuario SET {sets} WHERE id=%s
            RETURNING id, usuario, nombre, correo, rol, activo, creado_en""",
        (*campos.values(), usuario_id),
    )


def crear_sesion(token_hash: str, usuario_id: str, expira_en: datetime,
                 agente: str | None) -> None:
    with conn() as c:
        c.execute(
            """INSERT INTO core.sesion (token_hash, usuario_id, expira_en, agente)
               VALUES (%s,%s,%s,%s)""",
            (token_hash, usuario_id, expira_en, agente),
        )
        c.execute("UPDATE core.usuario SET ultimo_acceso=now() WHERE id=%s",
                  (usuario_id,))
        # Limpieza oportunista: sin esto la tabla crece indefinidamente
        # con sesiones muertas, y no hay proceso programado que lo haga.
        c.execute("DELETE FROM core.sesion WHERE expira_en < now()")
        c.commit()


def usuario_de_sesion(token_hash: str) -> dict | None:
    """El usuario dueño de una sesión viva. Un usuario desactivado deja
    de entrar de inmediato, aunque su sesión siga vigente."""
    return uno(
        """SELECT u.id, u.usuario, u.nombre, u.correo, u.rol, u.activo
           FROM core.sesion s JOIN core.usuario u ON u.id = s.usuario_id
           WHERE s.token_hash=%s AND s.expira_en > now() AND u.activo""",
        (token_hash,),
    )


def borrar_sesion(token_hash: str) -> None:
    ejecutar("DELETE FROM core.sesion WHERE token_hash=%s", (token_hash,))


def borrar_sesiones_de(usuario_id: str) -> None:
    """Al cambiar la contraseña o desactivar a alguien, sus sesiones
    abiertas dejan de servir."""
    ejecutar("DELETE FROM core.sesion WHERE usuario_id=%s", (usuario_id,))


# =====================================================================
# BITÁCORA
# =====================================================================

def registrar(**d: Any) -> None:
    """Inserta una entrada. `detalle` va como jsonb con cast explícito
    porque puede traer Decimal y fechas."""
    detalle = d.pop("detalle", None)
    cols = list(d) + (["detalle"] if detalle is not None else [])
    ph = ", ".join(["%s"] * len(d) + (["%s::jsonb"] if detalle is not None else []))
    valores = list(d.values()) + (
        [json.dumps(detalle, default=str)] if detalle is not None else []
    )
    ejecutar(f"INSERT INTO core.bitacora ({', '.join(cols)}) VALUES ({ph})",
             tuple(valores))


def bitacora(usuario: str | None = None, accion: str | None = None,
             encargo_id: str | None = None, desde: date | None = None,
             hasta: date | None = None, limite: int = 200,
             desplazamiento: int = 0) -> list[dict]:
    where, args = ["true"], []
    if usuario:
        where.append("b.usuario = %s"); args.append(usuario)
    if accion:
        where.append("b.accion = %s"); args.append(accion)
    if encargo_id:
        where.append("b.encargo_id = %s"); args.append(encargo_id)
    if desde:
        where.append("b.creado_en >= %s"); args.append(desde)
    if hasta:
        # El filtro es por día: se incluye el día completo indicado.
        where.append("b.creado_en < (%s::date + 1)"); args.append(hasta)
    return varios(
        f"""SELECT b.*, cl.razon_social, e.fecha_corte
            FROM core.bitacora b
            LEFT JOIN core.encargo e ON e.id = b.encargo_id
            LEFT JOIN core.cliente cl ON cl.id = e.cliente_id
            WHERE {' AND '.join(where)}
            ORDER BY b.creado_en DESC
            LIMIT {int(limite)} OFFSET {int(desplazamiento)}""",
        tuple(args),
    )


def acciones_registradas() -> list[dict]:
    """Para poblar el filtro sin inventar una lista fija que se
    desactualice cuando aparezcan acciones nuevas."""
    return varios(
        "SELECT accion, count(*) AS n FROM core.bitacora GROUP BY accion ORDER BY accion"
    )


# =====================================================================
# OBSERVACIONES DE IA
# =====================================================================

def guardar_observacion_ia(cliente_id: str, encargo_id: str, fase: str,
                           codigo_puc: str, texto: str, verificado: bool,
                           cifras: list, entrada: dict, instruccion: str | None,
                           modelo: str | None, usuario: str | None) -> dict:
    """Append-only: cada llamada crea una versión nueva, nunca sobrescribe.
    Los jsonb van con cast explícito -- `entrada` trae Decimal, así que se
    serializa con default=str en vez de dejárselo al adaptador."""
    with conn() as c:
        v = c.execute(
            """SELECT coalesce(max(version),0)+1 AS v FROM core.observacion_ia
               WHERE encargo_id=%s AND fase=%s AND codigo_puc=%s""",
            (encargo_id, fase, codigo_puc),
        ).fetchone()["v"]
        fila = c.execute(
            """INSERT INTO core.observacion_ia
                 (cliente_id, encargo_id, fase, codigo_puc, version, texto,
                  verificado, cifras_no_verificadas, entrada,
                  instruccion_auditor, modelo, creado_por)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s)
               RETURNING *""",
            (cliente_id, encargo_id, fase, codigo_puc, v, texto, verificado,
             json.dumps(cifras or []), json.dumps(entrada, default=str),
             instruccion, modelo, usuario),
        ).fetchone()
        c.commit()
        return fila


def observaciones_ia_vigentes(encargo_id: str, fase: str) -> list[dict]:
    """La versión más reciente por cuenta. Es lo que pinta Variaciones al
    abrirse, sin volver a llamar al modelo."""
    return varios(
        """SELECT DISTINCT ON (codigo_puc)
                  codigo_puc, version, texto, verificado, cifras_no_verificadas,
                  instruccion_auditor, modelo, creado_por, creado_en
           FROM core.observacion_ia
           WHERE encargo_id=%s AND fase=%s
           ORDER BY codigo_puc, version DESC""",
        (encargo_id, fase),
    )


def observacion_ia_ultima(encargo_id: str, fase: str, codigo_puc: str) -> dict | None:
    return uno(
        """SELECT * FROM core.observacion_ia
           WHERE encargo_id=%s AND fase=%s AND codigo_puc=%s
           ORDER BY version DESC LIMIT 1""",
        (encargo_id, fase, codigo_puc),
    )


def historia_observaciones_ia(cliente_id: str, codigo_puc: str | None = None,
                              limite: int = 200) -> list[dict]:
    """Todo lo que la IA ha redactado para este CLIENTE, en cualquier
    encargo o fase -- el repositorio completo, no solo el corte actual."""
    where = ["o.cliente_id=%s"]
    args: list = [cliente_id]
    if codigo_puc:
        where.append("o.codigo_puc=%s")
        args.append(codigo_puc)
    return varios(
        f"""SELECT o.id, o.codigo_puc, o.version, o.texto, o.verificado,
                   o.instruccion_auditor, o.modelo, o.creado_por, o.creado_en,
                   o.fase, e.fecha_corte
            FROM core.observacion_ia o
            LEFT JOIN core.encargo e ON e.id = o.encargo_id
            WHERE {' AND '.join(where)}
            ORDER BY o.creado_en DESC
            LIMIT {int(limite)}""",
        tuple(args),
    )
