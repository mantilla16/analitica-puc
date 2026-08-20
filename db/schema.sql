--
-- PostgreSQL database dump
--

\restrict BQcDdPbTcPi2y5mqCBXwiTkPg9A2dBAqlDqh0WjyQekrgkYfpFVGEhZhlq9ZsUN

-- Dumped from database version 18.6
-- Dumped by pg_dump version 18.6

-- =====================================================================
-- Estructura completa de auditoria_puc + datos de catálogo (PUC, campos
-- canónicos, sinónimos, fases, niveles). Sin datos de clientes ni de
-- encargos -- ver db/ESQUEMA.md para qué es cada tabla.
--
-- Es un dump de la base ya al día: incluye todo lo de 08_materialidad.sql
-- (esa migración queda en la raíz del repo solo como registro histórico,
-- NO hay que volver a correrla sobre una base creada con este archivo).
--
-- Para levantar una base nueva:
--   createdb -h localhost -U postgres auditoria_puc
--   psql -h localhost -U postgres -d auditoria_puc -v ON_ERROR_STOP=1 -f db/schema.sql
-- =====================================================================

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: core; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA core;


--
-- Name: raw; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA raw;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alerta; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.alerta (
    id bigint NOT NULL,
    cliente_id uuid NOT NULL,
    encargo_id uuid,
    cotejo_id bigint,
    tipo text NOT NULL,
    severidad text NOT NULL,
    titulo text NOT NULL,
    cuerpo text NOT NULL,
    destinatario text,
    canal text DEFAULT 'SIMULADO'::text NOT NULL,
    estado text DEFAULT 'PENDIENTE'::text NOT NULL,
    creada_en timestamp with time zone DEFAULT now() NOT NULL,
    enviada_en timestamp with time zone,
    reconocida_por text,
    reconocida_en timestamp with time zone
);


--
-- Name: alerta_id_seq; Type: SEQUENCE; Schema: core; Owner: -
--

CREATE SEQUENCE core.alerta_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: alerta_id_seq; Type: SEQUENCE OWNED BY; Schema: core; Owner: -
--

ALTER SEQUENCE core.alerta_id_seq OWNED BY core.alerta.id;


--
-- Name: balance; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.balance (
    id bigint NOT NULL,
    carga_id uuid NOT NULL,
    cliente_id uuid NOT NULL,
    codigo_puc text NOT NULL,
    nombre_cuenta text,
    nivel text NOT NULL,
    digitos smallint NOT NULL,
    clase text NOT NULL,
    cuenta text,
    subcuenta text,
    saldo_inicial numeric(19,2) DEFAULT 0 NOT NULL,
    debito numeric(19,2) DEFAULT 0 NOT NULL,
    credito numeric(19,2) DEFAULT 0 NOT NULL,
    saldo_final numeric(19,2) DEFAULT 0 NOT NULL,
    signo smallint NOT NULL,
    saldo_natural numeric(19,2)
);


--
-- Name: balance_id_seq; Type: SEQUENCE; Schema: core; Owner: -
--

CREATE SEQUENCE core.balance_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: balance_id_seq; Type: SEQUENCE OWNED BY; Schema: core; Owner: -
--

ALTER SEQUENCE core.balance_id_seq OWNED BY core.balance.id;


--
-- Name: campo_canonico; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.campo_canonico (
    naturaleza text NOT NULL,
    campo text NOT NULL,
    etiqueta text NOT NULL,
    tipo text NOT NULL,
    requerido boolean DEFAULT false NOT NULL,
    es_llave boolean DEFAULT false NOT NULL,
    orden smallint NOT NULL,
    ayuda text
);


--
-- Name: campo_sinonimo; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.campo_sinonimo (
    naturaleza text NOT NULL,
    campo text NOT NULL,
    sinonimo text NOT NULL,
    norm text NOT NULL
);


--
-- Name: carga; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.carga (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    cliente_id uuid NOT NULL,
    encargo_id uuid,
    tipo text NOT NULL,
    archivo text NOT NULL,
    hoja text,
    hash_sha256 text NOT NULL,
    perfil_id bigint,
    periodo_ini date,
    periodo_fin date,
    filas_origen integer,
    filas_staging integer,
    filas_cargadas integer,
    subido_por text,
    fecha_carga timestamp with time zone DEFAULT now() NOT NULL,
    estado text DEFAULT 'CARGADA'::text NOT NULL
);


--
-- Name: cliente; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.cliente (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    nit text NOT NULL,
    razon_social text NOT NULL,
    seudonimo text NOT NULL,
    activo boolean DEFAULT true NOT NULL,
    creado_en timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: cotejo; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.cotejo (
    id bigint NOT NULL,
    carga_nueva uuid NOT NULL,
    carga_previa uuid,
    encargo_id uuid,
    resultado text NOT NULL,
    filas_previas bigint DEFAULT 0 NOT NULL,
    filas_nuevas bigint DEFAULT 0 NOT NULL,
    n_nuevas bigint DEFAULT 0 NOT NULL,
    n_modificadas bigint DEFAULT 0 NOT NULL,
    n_eliminadas bigint DEFAULT 0 NOT NULL,
    n_fuera_periodo bigint DEFAULT 0 NOT NULL,
    monto_fuera_periodo numeric(19,2) DEFAULT 0 NOT NULL,
    mensaje text NOT NULL,
    ejecutado_en timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: cotejo_detalle; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.cotejo_detalle (
    id bigint NOT NULL,
    cotejo_id bigint NOT NULL,
    cambio text NOT NULL,
    llave text NOT NULL,
    codigo_puc text,
    num_doc text,
    fecha date,
    fuera_periodo boolean DEFAULT false NOT NULL,
    valor_antes jsonb,
    valor_ahora jsonb
);


--
-- Name: cotejo_detalle_id_seq; Type: SEQUENCE; Schema: core; Owner: -
--

CREATE SEQUENCE core.cotejo_detalle_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cotejo_detalle_id_seq; Type: SEQUENCE OWNED BY; Schema: core; Owner: -
--

ALTER SEQUENCE core.cotejo_detalle_id_seq OWNED BY core.cotejo_detalle.id;


--
-- Name: cotejo_id_seq; Type: SEQUENCE; Schema: core; Owner: -
--

CREATE SEQUENCE core.cotejo_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: cotejo_id_seq; Type: SEQUENCE OWNED BY; Schema: core; Owner: -
--

ALTER SEQUENCE core.cotejo_id_seq OWNED BY core.cotejo.id;


--
-- Name: encargo; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.encargo (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    cliente_id uuid NOT NULL,
    fecha_corte date NOT NULL,
    fecha_cierre_anterior date NOT NULL,
    fecha_corte_anterior date NOT NULL,
    estado text DEFAULT 'ABIERTO'::text NOT NULL,
    responsable text,
    creado_en timestamp with time zone DEFAULT now() NOT NULL,
    fase_activa text DEFAULT 'PLANEACION'::text,
    pct_variacion numeric(5,2) DEFAULT 20.00 NOT NULL,
    pct_trivialidad numeric(5,2) DEFAULT 5.00 NOT NULL
);


--
-- Name: COLUMN encargo.pct_variacion; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.encargo.pct_variacion IS 'Variación porcentual que marca una cuenta aunque no supere el umbral en pesos';


--
-- Name: COLUMN encargo.pct_trivialidad; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.encargo.pct_trivialidad IS 'Piso de ruido, como porcentaje de la materialidad de la fase activa';


--
-- Name: encargo_insumo; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.encargo_insumo (
    encargo_id uuid NOT NULL,
    tipo text NOT NULL,
    carga_id uuid NOT NULL,
    asignado_en timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: fase; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.fase (
    fase text NOT NULL,
    nombre text NOT NULL,
    orden smallint NOT NULL
);


--
-- Name: hallazgo; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.hallazgo (
    id bigint NOT NULL,
    encargo_id uuid,
    carga_id uuid,
    tipo text NOT NULL,
    severidad text NOT NULL,
    codigo_puc text,
    monto numeric(19,2),
    descripcion text NOT NULL,
    fila_origen integer,
    detectado_en timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: hallazgo_id_seq; Type: SEQUENCE; Schema: core; Owner: -
--

CREATE SEQUENCE core.hallazgo_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: hallazgo_id_seq; Type: SEQUENCE OWNED BY; Schema: core; Owner: -
--

ALTER SEQUENCE core.hallazgo_id_seq OWNED BY core.hallazgo.id;


--
-- Name: insumo; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.insumo (
    tipo text NOT NULL,
    nombre text NOT NULL,
    naturaleza text NOT NULL,
    requerido boolean DEFAULT true NOT NULL,
    rol_comparativo text,
    orden smallint NOT NULL
);


--
-- Name: materialidad; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.materialidad (
    id bigint NOT NULL,
    encargo_id uuid NOT NULL,
    fase text NOT NULL,
    nombre text NOT NULL,
    valor numeric(19,2),
    porcentaje numeric(5,2),
    aplicar boolean DEFAULT false NOT NULL,
    base_calculo text,
    aprobado_por text,
    actualizado timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: materialidad_historia; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.materialidad_historia (
    id bigint NOT NULL,
    encargo_id uuid NOT NULL,
    fase text NOT NULL,
    nombre text NOT NULL,
    valor numeric(19,2),
    porcentaje numeric(5,2),
    aplicar boolean NOT NULL,
    cambiado_por text,
    cambiado_en timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: materialidad_historia_id_seq; Type: SEQUENCE; Schema: core; Owner: -
--

CREATE SEQUENCE core.materialidad_historia_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: materialidad_historia_id_seq; Type: SEQUENCE OWNED BY; Schema: core; Owner: -
--

ALTER SEQUENCE core.materialidad_historia_id_seq OWNED BY core.materialidad_historia.id;


--
-- Name: materialidad_id_seq; Type: SEQUENCE; Schema: core; Owner: -
--

CREATE SEQUENCE core.materialidad_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: materialidad_id_seq; Type: SEQUENCE OWNED BY; Schema: core; Owner: -
--

ALTER SEQUENCE core.materialidad_id_seq OWNED BY core.materialidad.id;


--
-- Name: movimiento; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.movimiento (
    id bigint NOT NULL,
    carga_id uuid NOT NULL,
    cliente_id uuid NOT NULL,
    encargo_id uuid,
    fecha date NOT NULL,
    num_doc text,
    secuencia text,
    codigo_puc text NOT NULL,
    nombre_cuenta text,
    clase text NOT NULL,
    cuenta text,
    subcuenta text,
    tercero_nit text,
    tercero_nombre text,
    centro_costo text,
    descripcion text,
    detalle text,
    desc_norm text,
    debito numeric(19,2) DEFAULT 0 NOT NULL,
    credito numeric(19,2) DEFAULT 0 NOT NULL,
    neto numeric(19,2)
)
PARTITION BY RANGE (fecha);


--
-- Name: movimiento_id_seq; Type: SEQUENCE; Schema: core; Owner: -
--

CREATE SEQUENCE core.movimiento_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: movimiento_id_seq; Type: SEQUENCE OWNED BY; Schema: core; Owner: -
--

ALTER SEQUENCE core.movimiento_id_seq OWNED BY core.movimiento.id;


--
-- Name: movimiento_2024; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.movimiento_2024 (
    id bigint DEFAULT nextval('core.movimiento_id_seq'::regclass) CONSTRAINT movimiento_id_not_null NOT NULL,
    carga_id uuid CONSTRAINT movimiento_carga_id_not_null NOT NULL,
    cliente_id uuid CONSTRAINT movimiento_cliente_id_not_null NOT NULL,
    encargo_id uuid,
    fecha date CONSTRAINT movimiento_fecha_not_null NOT NULL,
    num_doc text,
    secuencia text,
    codigo_puc text CONSTRAINT movimiento_codigo_puc_not_null NOT NULL,
    nombre_cuenta text,
    clase text CONSTRAINT movimiento_clase_not_null NOT NULL,
    cuenta text,
    subcuenta text,
    tercero_nit text,
    tercero_nombre text,
    centro_costo text,
    descripcion text,
    detalle text,
    desc_norm text,
    debito numeric(19,2) DEFAULT 0 CONSTRAINT movimiento_debito_not_null NOT NULL,
    credito numeric(19,2) DEFAULT 0 CONSTRAINT movimiento_credito_not_null NOT NULL,
    neto numeric(19,2)
);


--
-- Name: movimiento_2025; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.movimiento_2025 (
    id bigint DEFAULT nextval('core.movimiento_id_seq'::regclass) CONSTRAINT movimiento_id_not_null NOT NULL,
    carga_id uuid CONSTRAINT movimiento_carga_id_not_null NOT NULL,
    cliente_id uuid CONSTRAINT movimiento_cliente_id_not_null NOT NULL,
    encargo_id uuid,
    fecha date CONSTRAINT movimiento_fecha_not_null NOT NULL,
    num_doc text,
    secuencia text,
    codigo_puc text CONSTRAINT movimiento_codigo_puc_not_null NOT NULL,
    nombre_cuenta text,
    clase text CONSTRAINT movimiento_clase_not_null NOT NULL,
    cuenta text,
    subcuenta text,
    tercero_nit text,
    tercero_nombre text,
    centro_costo text,
    descripcion text,
    detalle text,
    desc_norm text,
    debito numeric(19,2) DEFAULT 0 CONSTRAINT movimiento_debito_not_null NOT NULL,
    credito numeric(19,2) DEFAULT 0 CONSTRAINT movimiento_credito_not_null NOT NULL,
    neto numeric(19,2)
);


--
-- Name: movimiento_2026; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.movimiento_2026 (
    id bigint DEFAULT nextval('core.movimiento_id_seq'::regclass) CONSTRAINT movimiento_id_not_null NOT NULL,
    carga_id uuid CONSTRAINT movimiento_carga_id_not_null NOT NULL,
    cliente_id uuid CONSTRAINT movimiento_cliente_id_not_null NOT NULL,
    encargo_id uuid,
    fecha date CONSTRAINT movimiento_fecha_not_null NOT NULL,
    num_doc text,
    secuencia text,
    codigo_puc text CONSTRAINT movimiento_codigo_puc_not_null NOT NULL,
    nombre_cuenta text,
    clase text CONSTRAINT movimiento_clase_not_null NOT NULL,
    cuenta text,
    subcuenta text,
    tercero_nit text,
    tercero_nombre text,
    centro_costo text,
    descripcion text,
    detalle text,
    desc_norm text,
    debito numeric(19,2) DEFAULT 0 CONSTRAINT movimiento_debito_not_null NOT NULL,
    credito numeric(19,2) DEFAULT 0 CONSTRAINT movimiento_credito_not_null NOT NULL,
    neto numeric(19,2)
);


--
-- Name: movimiento_2027; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.movimiento_2027 (
    id bigint DEFAULT nextval('core.movimiento_id_seq'::regclass) CONSTRAINT movimiento_id_not_null NOT NULL,
    carga_id uuid CONSTRAINT movimiento_carga_id_not_null NOT NULL,
    cliente_id uuid CONSTRAINT movimiento_cliente_id_not_null NOT NULL,
    encargo_id uuid,
    fecha date CONSTRAINT movimiento_fecha_not_null NOT NULL,
    num_doc text,
    secuencia text,
    codigo_puc text CONSTRAINT movimiento_codigo_puc_not_null NOT NULL,
    nombre_cuenta text,
    clase text CONSTRAINT movimiento_clase_not_null NOT NULL,
    cuenta text,
    subcuenta text,
    tercero_nit text,
    tercero_nombre text,
    centro_costo text,
    descripcion text,
    detalle text,
    desc_norm text,
    debito numeric(19,2) DEFAULT 0 CONSTRAINT movimiento_debito_not_null NOT NULL,
    credito numeric(19,2) DEFAULT 0 CONSTRAINT movimiento_credito_not_null NOT NULL,
    neto numeric(19,2)
);


--
-- Name: movimiento_default; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.movimiento_default (
    id bigint DEFAULT nextval('core.movimiento_id_seq'::regclass) CONSTRAINT movimiento_id_not_null NOT NULL,
    carga_id uuid CONSTRAINT movimiento_carga_id_not_null NOT NULL,
    cliente_id uuid CONSTRAINT movimiento_cliente_id_not_null NOT NULL,
    encargo_id uuid,
    fecha date CONSTRAINT movimiento_fecha_not_null NOT NULL,
    num_doc text,
    secuencia text,
    codigo_puc text CONSTRAINT movimiento_codigo_puc_not_null NOT NULL,
    nombre_cuenta text,
    clase text CONSTRAINT movimiento_clase_not_null NOT NULL,
    cuenta text,
    subcuenta text,
    tercero_nit text,
    tercero_nombre text,
    centro_costo text,
    descripcion text,
    detalle text,
    desc_norm text,
    debito numeric(19,2) DEFAULT 0 CONSTRAINT movimiento_debito_not_null NOT NULL,
    credito numeric(19,2) DEFAULT 0 CONSTRAINT movimiento_credito_not_null NOT NULL,
    neto numeric(19,2)
);


--
-- Name: nivel_cargable; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.nivel_cargable (
    nivel text NOT NULL,
    digitos smallint NOT NULL,
    es_comparativo boolean DEFAULT false NOT NULL,
    nivel_completo boolean DEFAULT false NOT NULL,
    orden smallint NOT NULL,
    nota text
);


--
-- Name: nota_alcance; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.nota_alcance (
    id bigint NOT NULL,
    encargo_id uuid NOT NULL,
    fase text NOT NULL,
    nota text NOT NULL,
    pct_variacion numeric(5,2) NOT NULL,
    umbral numeric(19,2),
    residuo numeric(19,2) NOT NULL,
    autor text,
    creado_en timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE nota_alcance; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.nota_alcance IS 'Append-only. La vigente es la fila más reciente por (encargo_id, fase).';


--
-- Name: nota_alcance_id_seq; Type: SEQUENCE; Schema: core; Owner: -
--

CREATE SEQUENCE core.nota_alcance_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: nota_alcance_id_seq; Type: SEQUENCE OWNED BY; Schema: core; Owner: -
--

ALTER SEQUENCE core.nota_alcance_id_seq OWNED BY core.nota_alcance.id;


--
-- Name: perfil_mapeo; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.perfil_mapeo (
    id bigint NOT NULL,
    cliente_id uuid NOT NULL,
    tipo text NOT NULL,
    version integer DEFAULT 1 NOT NULL,
    mapeo jsonb NOT NULL,
    vigente boolean DEFAULT true NOT NULL,
    creado_por text,
    creado_en timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: perfil_mapeo_id_seq; Type: SEQUENCE; Schema: core; Owner: -
--

CREATE SEQUENCE core.perfil_mapeo_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: perfil_mapeo_id_seq; Type: SEQUENCE OWNED BY; Schema: core; Owner: -
--

ALTER SEQUENCE core.perfil_mapeo_id_seq OWNED BY core.perfil_mapeo.id;


--
-- Name: puc; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.puc (
    codigo text NOT NULL,
    nombre text NOT NULL,
    clase text NOT NULL,
    digitos smallint NOT NULL,
    naturaleza text,
    origen text DEFAULT 'derivado'::text NOT NULL,
    validado boolean DEFAULT false NOT NULL,
    activo boolean DEFAULT true NOT NULL
);


--
-- Name: puc_clase; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.puc_clase (
    clase text NOT NULL,
    nombre text NOT NULL,
    naturaleza text NOT NULL,
    signo smallint NOT NULL,
    tipo_estado text NOT NULL,
    comparativo text NOT NULL
);


--
-- Name: puc_nivel; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.puc_nivel (
    nivel text NOT NULL,
    digitos smallint NOT NULL,
    orden smallint NOT NULL
);


--
-- Name: balance_staging; Type: TABLE; Schema: raw; Owner: -
--

CREATE TABLE raw.balance_staging (
    carga_id uuid NOT NULL,
    fila_origen integer NOT NULL,
    hoja text,
    codigo_puc text,
    nombre_cuenta text,
    nivel text,
    transaccional text,
    saldo_inicial text,
    debito text,
    credito text,
    saldo_final text,
    llave text,
    huella text
);


--
-- Name: movimiento_staging; Type: TABLE; Schema: raw; Owner: -
--

CREATE TABLE raw.movimiento_staging (
    carga_id uuid NOT NULL,
    fila_origen integer NOT NULL,
    hoja text,
    fecha text,
    num_doc text,
    secuencia text,
    codigo_puc text,
    nombre_cuenta text,
    tercero_nit text,
    tercero_nombre text,
    centro_costo text,
    descripcion text,
    detalle text,
    debito text,
    credito text,
    llave text,
    huella text
);


--
-- Name: movimiento_2024; Type: TABLE ATTACH; Schema: core; Owner: -
--

ALTER TABLE ONLY core.movimiento ATTACH PARTITION core.movimiento_2024 FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');


--
-- Name: movimiento_2025; Type: TABLE ATTACH; Schema: core; Owner: -
--

ALTER TABLE ONLY core.movimiento ATTACH PARTITION core.movimiento_2025 FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');


--
-- Name: movimiento_2026; Type: TABLE ATTACH; Schema: core; Owner: -
--

ALTER TABLE ONLY core.movimiento ATTACH PARTITION core.movimiento_2026 FOR VALUES FROM ('2026-01-01') TO ('2027-01-01');


--
-- Name: movimiento_2027; Type: TABLE ATTACH; Schema: core; Owner: -
--

ALTER TABLE ONLY core.movimiento ATTACH PARTITION core.movimiento_2027 FOR VALUES FROM ('2027-01-01') TO ('2028-01-01');


--
-- Name: movimiento_default; Type: TABLE ATTACH; Schema: core; Owner: -
--

ALTER TABLE ONLY core.movimiento ATTACH PARTITION core.movimiento_default DEFAULT;


--
-- Name: alerta id; Type: DEFAULT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.alerta ALTER COLUMN id SET DEFAULT nextval('core.alerta_id_seq'::regclass);


--
-- Name: balance id; Type: DEFAULT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.balance ALTER COLUMN id SET DEFAULT nextval('core.balance_id_seq'::regclass);


--
-- Name: cotejo id; Type: DEFAULT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.cotejo ALTER COLUMN id SET DEFAULT nextval('core.cotejo_id_seq'::regclass);


--
-- Name: cotejo_detalle id; Type: DEFAULT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.cotejo_detalle ALTER COLUMN id SET DEFAULT nextval('core.cotejo_detalle_id_seq'::regclass);


--
-- Name: hallazgo id; Type: DEFAULT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.hallazgo ALTER COLUMN id SET DEFAULT nextval('core.hallazgo_id_seq'::regclass);


--
-- Name: materialidad id; Type: DEFAULT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.materialidad ALTER COLUMN id SET DEFAULT nextval('core.materialidad_id_seq'::regclass);


--
-- Name: materialidad_historia id; Type: DEFAULT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.materialidad_historia ALTER COLUMN id SET DEFAULT nextval('core.materialidad_historia_id_seq'::regclass);


--
-- Name: movimiento id; Type: DEFAULT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.movimiento ALTER COLUMN id SET DEFAULT nextval('core.movimiento_id_seq'::regclass);


--
-- Name: nota_alcance id; Type: DEFAULT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.nota_alcance ALTER COLUMN id SET DEFAULT nextval('core.nota_alcance_id_seq'::regclass);


--
-- Name: perfil_mapeo id; Type: DEFAULT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.perfil_mapeo ALTER COLUMN id SET DEFAULT nextval('core.perfil_mapeo_id_seq'::regclass);


--
-- Data for Name: campo_canonico; Type: TABLE DATA; Schema: core; Owner: -
--

COPY core.campo_canonico (naturaleza, campo, etiqueta, tipo, requerido, es_llave, orden, ayuda) FROM stdin;
BALANCE	codigo_puc	Código de cuenta	texto	t	t	1	Código contable. Determina clase, nivel y naturaleza.
BALANCE	nombre_cuenta	Nombre de la cuenta	texto	f	f	2	Denominación según el catálogo del cliente.
BALANCE	nivel	Nivel	texto	f	f	3	Clase, Grupo, Cuenta, Subcuenta, Auxiliar. Si no existe se infiere por longitud del código.
BALANCE	transaccional	Transaccional	booleano	f	f	4	Marca las filas de detalle. CRÍTICO: sin esto se suman totales con detalle. Si no existe se infiere.
BALANCE	saldo_inicial	Saldo inicial	numero	f	f	5	\N
BALANCE	debito	Movimiento débito	numero	t	f	6	\N
BALANCE	credito	Movimiento crédito	numero	t	f	7	\N
BALANCE	saldo_final	Saldo final	numero	t	f	8	\N
MOVIMIENTO	codigo_puc	Código de cuenta	texto	t	t	1	\N
MOVIMIENTO	nombre_cuenta	Nombre de la cuenta	texto	f	f	2	\N
MOVIMIENTO	num_doc	Comprobante	texto	t	t	3	Identificador del asiento. Parte de la llave que detecta cambios entre cargas.
MOVIMIENTO	secuencia	Secuencia	texto	t	t	4	Renglón dentro del comprobante. Completa la llave única.
MOVIMIENTO	fecha	Fecha	fecha	t	f	5	Fecha del asiento. Define si un cambio cae en periodo ya auditado.
MOVIMIENTO	tercero_nit	NIT del tercero	texto	f	f	6	\N
MOVIMIENTO	tercero_nombre	Nombre del tercero	texto	f	f	7	\N
MOVIMIENTO	descripcion	Descripción	texto	f	f	8	Texto principal del asiento. Es el que se agrupa en patrones.
MOVIMIENTO	detalle	Detalle	texto	f	f	9	Texto secundario. Suele venir vacío en la mayoría de las filas.
MOVIMIENTO	centro_costo	Centro de costo	texto	f	f	10	\N
MOVIMIENTO	debito	Débito	numero	t	f	11	\N
MOVIMIENTO	credito	Crédito	numero	t	f	12	\N
\.


--
-- Data for Name: campo_sinonimo; Type: TABLE DATA; Schema: core; Owner: -
--

COPY core.campo_sinonimo (naturaleza, campo, sinonimo, norm) FROM stdin;
BALANCE	codigo_puc	Código cuenta contable	codigo cuenta contable
BALANCE	codigo_puc	Código contable	codigo contable
BALANCE	codigo_puc	Cuenta	cuenta
BALANCE	codigo_puc	Cta.	cta
BALANCE	codigo_puc	Código	codigo
BALANCE	codigo_puc	Código PUC	codigo puc
BALANCE	nombre_cuenta	Nombre cuenta contable	nombre cuenta contable
BALANCE	nombre_cuenta	Nombre de la cuenta	nombre de la cuenta
BALANCE	nombre_cuenta	Descripción cuenta	descripcion cuenta
BALANCE	nombre_cuenta	Nombre	nombre
BALANCE	nivel	Nivel	nivel
BALANCE	nivel	Nivel cuenta	nivel cuenta
BALANCE	transaccional	Transaccional	transaccional
BALANCE	transaccional	Es transaccional	es transaccional
BALANCE	transaccional	Movimiento	movimiento
BALANCE	saldo_inicial	Saldo inicial	saldo inicial
BALANCE	saldo_inicial	Saldo anterior	saldo anterior
BALANCE	saldo_inicial	Saldo inicial periodo	saldo inicial periodo
BALANCE	debito	Movimiento débito	movimiento debito
BALANCE	debito	Débito	debito
BALANCE	debito	Débitos	debitos
BALANCE	debito	Debe	debe
BALANCE	credito	Movimiento crédito	movimiento credito
BALANCE	credito	Crédito	credito
BALANCE	credito	Créditos	creditos
BALANCE	credito	Haber	haber
BALANCE	saldo_final	Saldo final	saldo final
BALANCE	saldo_final	Nuevo saldo	nuevo saldo
BALANCE	saldo_final	Saldo actual	saldo actual
MOVIMIENTO	codigo_puc	Código contable	codigo contable
MOVIMIENTO	codigo_puc	Código cuenta contable	codigo cuenta contable
MOVIMIENTO	codigo_puc	Cuenta	cuenta
MOVIMIENTO	nombre_cuenta	Cuenta contable	cuenta contable
MOVIMIENTO	nombre_cuenta	Nombre cuenta	nombre cuenta
MOVIMIENTO	num_doc	Comprobante	comprobante
MOVIMIENTO	num_doc	Documento	documento
MOVIMIENTO	num_doc	Número documento	numero documento
MOVIMIENTO	num_doc	Núm. comprobante	num comprobante
MOVIMIENTO	secuencia	Secuencia	secuencia
MOVIMIENTO	secuencia	Renglón	renglon
MOVIMIENTO	secuencia	Línea	linea
MOVIMIENTO	secuencia	Consecutivo	consecutivo
MOVIMIENTO	fecha	Fecha elaboración	fecha elaboracion
MOVIMIENTO	fecha	Fecha	fecha
MOVIMIENTO	fecha	Fecha documento	fecha documento
MOVIMIENTO	fecha	Fecha movimiento	fecha movimiento
MOVIMIENTO	tercero_nit	Identificación	identificacion
MOVIMIENTO	tercero_nit	NIT	nit
MOVIMIENTO	tercero_nit	Documento tercero	documento tercero
MOVIMIENTO	tercero_nombre	Nombre del tercero	nombre del tercero
MOVIMIENTO	tercero_nombre	Tercero	tercero
MOVIMIENTO	tercero_nombre	Razón social	razon social
MOVIMIENTO	descripcion	Descripción	descripcion
MOVIMIENTO	descripcion	Concepto	concepto
MOVIMIENTO	descripcion	Glosa	glosa
MOVIMIENTO	detalle	Detalle	detalle
MOVIMIENTO	detalle	Observación	observacion
MOVIMIENTO	centro_costo	Centro de costo	centro de costo
MOVIMIENTO	centro_costo	C. Costo	c costo
MOVIMIENTO	debito	Débito	debito
MOVIMIENTO	debito	Débitos	debitos
MOVIMIENTO	debito	Debe	debe
MOVIMIENTO	credito	Crédito	credito
MOVIMIENTO	credito	Créditos	creditos
MOVIMIENTO	credito	Haber	haber
\.


--
-- Data for Name: fase; Type: TABLE DATA; Schema: core; Owner: -
--

COPY core.fase (fase, nombre, orden) FROM stdin;
PLANEACION	Planeación	1
EJECUCION	Ejecución	2
CIERRE	Cierre	3
\.


--
-- Data for Name: insumo; Type: TABLE DATA; Schema: core; Owner: -
--

COPY core.insumo (tipo, nombre, naturaleza, requerido, rol_comparativo, orden) FROM stdin;
BAL_ACTUAL	Balance a la fecha de corte	BALANCE	t	ACTUAL	1
BAL_CIERRE_ANTERIOR	Balance al 31-dic del año anterior	BALANCE	t	CIERRE_ANTERIOR	2
BAL_CORTE_ANTERIOR	Balance al mismo corte del año ant.	BALANCE	t	MISMO_PERIODO	3
MOV_ACTUAL	Movimientos del año actual	MOVIMIENTO	t	\N	4
MOV_ANTERIOR	Movimientos del año anterior	MOVIMIENTO	f	\N	5
PRECOMPROBANTE	Precomprobantes	MOVIMIENTO	f	\N	6
\.


--
-- Data for Name: nivel_cargable; Type: TABLE DATA; Schema: core; Owner: -
--

COPY core.nivel_cargable (nivel, digitos, es_comparativo, nivel_completo, orden, nota) FROM stdin;
Clase	1	f	t	1	Resumen por clase.
Cuenta	4	t	t	2	Nivel del comparativo del reporte.
Subcuenta	6	f	t	3	Último nivel completo del árbol.
Auxiliar	8	f	f	4	Drill-down. No cuadra solo.
\.


--
-- Data for Name: nota_alcance; Type: TABLE DATA; Schema: core; Owner: -
--

COPY core.nota_alcance (id, encargo_id, fase, nota, pct_variacion, umbral, residuo, autor, creado_en) FROM stdin;
\.


--
-- Data for Name: puc; Type: TABLE DATA; Schema: core; Owner: -
--

COPY core.puc (codigo, nombre, clase, digitos, naturaleza, origen, validado, activo) FROM stdin;
11	Disponible	1	2	\N	decreto2650	t	t
1105	Caja	1	4	\N	decreto2650	t	t
1110	Bancos	1	4	\N	decreto2650	t	t
1115	Remesas en tránsito	1	4	\N	decreto2650	t	t
1120	Cuentas de ahorro	1	4	\N	decreto2650	t	t
1125	Fondos	1	4	\N	decreto2650	t	t
12	Inversiones	1	2	\N	decreto2650	t	t
1205	Acciones	1	4	\N	decreto2650	t	t
1210	Cuotas o partes de interés social	1	4	\N	decreto2650	t	t
1215	Bonos	1	4	\N	decreto2650	t	t
1220	Cédulas	1	4	\N	decreto2650	t	t
1225	Certificados	1	4	\N	decreto2650	t	t
1230	Papeles comerciales	1	4	\N	decreto2650	t	t
1235	Títulos	1	4	\N	decreto2650	t	t
1240	Aceptaciones bancarias o financieras	1	4	\N	decreto2650	t	t
1245	Derechos fiduciarios	1	4	\N	decreto2650	t	t
1250	Derechos de recompra de inversiones negociadas (repos)	1	4	\N	decreto2650	t	t
1255	Obligatorias	1	4	\N	decreto2650	t	t
1260	Cuentas en participación	1	4	\N	decreto2650	t	t
1295	Otras inversiones	1	4	\N	decreto2650	t	t
1299	Provisiones	1	4	C	decreto2650	t	t
13	Deudores	1	2	\N	decreto2650	t	t
1305	Clientes	1	4	\N	decreto2650	t	t
1310	Cuentas corrientes comerciales	1	4	\N	decreto2650	t	t
1315	Cuentas por cobrar a casa matriz	1	4	\N	decreto2650	t	t
1320	Cuentas por cobrar a vinculados económicos	1	4	\N	decreto2650	t	t
1323	Cuentas por cobrar a directores	1	4	\N	decreto2650	t	t
1325	Cuentas por cobrar a socios y accionistas	1	4	\N	decreto2650	t	t
1328	Aportes por cobrar	1	4	\N	decreto2650	t	t
1330	Anticipos y avances	1	4	\N	decreto2650	t	t
1332	Cuentas de operación conjunta	1	4	\N	decreto2650	t	t
1335	Depósitos	1	4	\N	decreto2650	t	t
1340	Promesas de compra venta	1	4	\N	decreto2650	t	t
1345	Ingresos por cobrar	1	4	\N	decreto2650	t	t
1350	Retención sobre contratos	1	4	\N	decreto2650	t	t
1355	Anticipo de impuestos y contribuciones o saldos a favor	1	4	\N	decreto2650	t	t
1360	Reclamaciones	1	4	\N	decreto2650	t	t
1365	Cuentas por cobrar a trabajadores	1	4	\N	decreto2650	t	t
1370	Préstamos a particulares	1	4	\N	decreto2650	t	t
1380	Deudores varios	1	4	\N	decreto2650	t	t
1385	Derechos de recompra de cartera negociada	1	4	\N	decreto2650	t	t
1390	Deudas de difícil cobro	1	4	\N	decreto2650	t	t
1399	Provisiones	1	4	C	decreto2650	t	t
14	Inventarios	1	2	\N	decreto2650	t	t
1405	Materias primas	1	4	\N	decreto2650	t	t
1410	Productos en proceso	1	4	\N	decreto2650	t	t
1415	Obras de construcción en curso	1	4	\N	decreto2650	t	t
1417	Obras de urbanismo	1	4	\N	decreto2650	t	t
1420	Contratos en ejecución	1	4	\N	decreto2650	t	t
1425	Cultivos en desarrollo	1	4	\N	decreto2650	t	t
1428	Plantaciones agrícolas	1	4	\N	decreto2650	t	t
1430	Productos terminados	1	4	\N	decreto2650	t	t
1435	Mercancías no fabricadas por la empresa	1	4	\N	decreto2650	t	t
1440	Bienes raíces para la venta	1	4	\N	decreto2650	t	t
1445	Semovientes	1	4	\N	decreto2650	t	t
1450	Terrenos	1	4	\N	decreto2650	t	t
1455	Materiales, repuestos y accesorios	1	4	\N	decreto2650	t	t
1460	Envases y empaques	1	4	\N	decreto2650	t	t
1465	Inventarios en tránsito	1	4	\N	decreto2650	t	t
1499	Provisiones	1	4	C	decreto2650	t	t
15	Propiedades, planta y equipo	1	2	\N	decreto2650	t	t
1504	Terrenos	1	4	\N	decreto2650	t	t
1506	Materiales proyectos petroleros	1	4	\N	decreto2650	t	t
1508	Construcciones en curso	1	4	\N	decreto2650	t	t
1512	Maquinaria y equipos en montaje	1	4	\N	decreto2650	t	t
1516	Construcciones y edificaciones	1	4	\N	decreto2650	t	t
1520	Maquinaria y equipo	1	4	\N	decreto2650	t	t
1524	Equipo de oficina	1	4	\N	decreto2650	t	t
1528	Equipo de computación y comunicación	1	4	\N	decreto2650	t	t
1532	Equipo médico-científico	1	4	\N	decreto2650	t	t
1536	Equipo de hoteles y restaurantes	1	4	\N	decreto2650	t	t
1540	Flota y equipo de transporte	1	4	\N	decreto2650	t	t
1544	Flota y equipo fluvial y/o marítimo	1	4	\N	decreto2650	t	t
1548	Flota y equipo aéreo	1	4	\N	decreto2650	t	t
1552	Flota y equipo férreo	1	4	\N	decreto2650	t	t
1556	Acueductos, plantas y redes	1	4	\N	decreto2650	t	t
1560	Armamento de vigilancia	1	4	\N	decreto2650	t	t
1562	Envases y empaques	1	4	\N	decreto2650	t	t
1564	Plantaciones agrícolas y forestales	1	4	\N	decreto2650	t	t
1568	Vías de comunicación	1	4	\N	decreto2650	t	t
1572	Minas y canteras	1	4	\N	decreto2650	t	t
1576	Pozos artesianos	1	4	\N	decreto2650	t	t
1580	Yacimientos	1	4	\N	decreto2650	t	t
1584	Semovientes	1	4	\N	decreto2650	t	t
1588	Propiedades, planta y equipo en tránsito	1	4	\N	decreto2650	t	t
1592	Depreciación acumulada	1	4	C	decreto2650	t	t
1596	Depreciación diferida	1	4	\N	decreto2650	t	t
1597	Amortización acumulada	1	4	C	decreto2650	t	t
1598	Agotamiento acumulado	1	4	C	decreto2650	t	t
1599	Provisiones	1	4	C	decreto2650	t	t
16	Intangibles	1	2	\N	decreto2650	t	t
1605	Crédito mercantil	1	4	\N	decreto2650	t	t
1610	Marcas	1	4	\N	decreto2650	t	t
1615	Patentes	1	4	\N	decreto2650	t	t
1620	Concesiones y franquicias	1	4	\N	decreto2650	t	t
1625	Derechos	1	4	\N	decreto2650	t	t
1630	Know how	1	4	\N	decreto2650	t	t
1635	Licencias	1	4	\N	decreto2650	t	t
1698	Depreciación y/o amortización acumulada	1	4	C	decreto2650	t	t
1699	Provisiones	1	4	C	decreto2650	t	t
17	Diferidos	1	2	\N	decreto2650	t	t
1705	Gastos pagados por anticipado	1	4	\N	decreto2650	t	t
1710	Cargos diferidos	1	4	\N	decreto2650	t	t
1715	Costos de exploración por amortizar	1	4	\N	decreto2650	t	t
1720	Costos de explotación y desarrollo	1	4	\N	decreto2650	t	t
1730	Cargos por corrección monetaria diferida	1	4	\N	decreto2650	t	t
1798	Amortización acumulada	1	4	C	decreto2650	t	t
18	Otros activos	1	2	\N	decreto2650	t	t
1805	Bienes de arte y cultura	1	4	\N	decreto2650	t	t
1895	Diversos	1	4	\N	decreto2650	t	t
1899	Provisiones	1	4	C	decreto2650	t	t
19	Valorizaciones	1	2	\N	decreto2650	t	t
1905	De inversiones	1	4	\N	decreto2650	t	t
1910	De propiedades, planta y equipo	1	4	\N	decreto2650	t	t
1995	De otros activos	1	4	\N	decreto2650	t	t
21	Obligaciones financieras	2	2	\N	decreto2650	t	t
2105	Bancos nacionales	2	4	\N	decreto2650	t	t
2110	Bancos del exterior	2	4	\N	decreto2650	t	t
2115	Corporaciones financieras	2	4	\N	decreto2650	t	t
2120	Compañías de financiamiento comercial	2	4	\N	decreto2650	t	t
2125	Corporaciones de ahorro y vivienda	2	4	\N	decreto2650	t	t
2130	Entidades financieras del exterior	2	4	\N	decreto2650	t	t
2135	Compromisos de recompra de inversiones negociadas	2	4	\N	decreto2650	t	t
2140	Compromisos de recompra de cartera negociada	2	4	\N	decreto2650	t	t
2145	Obligaciones gubernamentales	2	4	\N	decreto2650	t	t
2195	Otras obligaciones	2	4	\N	decreto2650	t	t
22	Proveedores	2	2	\N	decreto2650	t	t
2205	Nacionales	2	4	\N	decreto2650	t	t
2210	Del exterior	2	4	\N	decreto2650	t	t
2215	Cuentas corrientes comerciales	2	4	\N	decreto2650	t	t
2220	Casa matriz	2	4	\N	decreto2650	t	t
2225	Compañías vinculadas	2	4	\N	decreto2650	t	t
23	Cuentas por pagar	2	2	\N	decreto2650	t	t
2305	Cuentas corrientes comerciales	2	4	\N	decreto2650	t	t
2310	A casa matriz	2	4	\N	decreto2650	t	t
2315	A compañías vinculadas	2	4	\N	decreto2650	t	t
2320	A contratistas	2	4	\N	decreto2650	t	t
2330	Órdenes de compra por utilizar	2	4	\N	decreto2650	t	t
2335	Costos y gastos por pagar	2	4	\N	decreto2650	t	t
2340	Instalamentos por pagar	2	4	\N	decreto2650	t	t
2345	Acreedores oficiales	2	4	\N	decreto2650	t	t
2350	Regalías por pagar	2	4	\N	decreto2650	t	t
2355	Deudas con accionistas o socios	2	4	\N	decreto2650	t	t
2357	Deudas con directores	2	4	\N	decreto2650	t	t
2360	Dividendos o participaciones por pagar	2	4	\N	decreto2650	t	t
2365	Retención en la fuente	2	4	\N	decreto2650	t	t
2367	Impuesto a las ventas retenido	2	4	\N	decreto2650	t	t
2368	Impuesto de industria y comercio retenido	2	4	\N	decreto2650	t	t
2370	Retenciones y aportes de nómina	2	4	\N	decreto2650	t	t
2375	Cuotas por devolver	2	4	\N	decreto2650	t	t
2380	Acreedores varios	2	4	\N	decreto2650	t	t
24	Impuestos, gravámenes y tasas	2	2	\N	decreto2650	t	t
2404	De renta y complementarios	2	4	\N	decreto2650	t	t
2408	Impuesto sobre las ventas por pagar	2	4	\N	decreto2650	t	t
2412	De industria y comercio	2	4	\N	decreto2650	t	t
2416	A la propiedad raíz	2	4	\N	decreto2650	t	t
2420	Derechos sobre instrumentos públicos	2	4	\N	decreto2650	t	t
2424	De valorización	2	4	\N	decreto2650	t	t
2428	De turismo	2	4	\N	decreto2650	t	t
2432	Tasa por utilización de puertos	2	4	\N	decreto2650	t	t
2436	De vehículos	2	4	\N	decreto2650	t	t
2440	De espectáculos públicos	2	4	\N	decreto2650	t	t
2444	De hidrocarburos y minas	2	4	\N	decreto2650	t	t
2448	Regalías e impuestos a la pequeña y mediana minería	2	4	\N	decreto2650	t	t
2452	A las exportaciones cafeteras	2	4	\N	decreto2650	t	t
2456	A las importaciones	2	4	\N	decreto2650	t	t
2460	Cuotas de fomento	2	4	\N	decreto2650	t	t
2464	De licores, cervezas y cigarrillos	2	4	\N	decreto2650	t	t
2468	Al sacrificio de ganado	2	4	\N	decreto2650	t	t
2472	Al azar y juegos	2	4	\N	decreto2650	t	t
2476	Gravámenes y regalías por utilización del suelo	2	4	\N	decreto2650	t	t
2495	Otros	2	4	\N	decreto2650	t	t
25	Obligaciones laborales	2	2	\N	decreto2650	t	t
2505	Salarios por pagar	2	4	\N	decreto2650	t	t
2510	Cesantías consolidadas	2	4	\N	decreto2650	t	t
2515	Intereses sobre cesantías	2	4	\N	decreto2650	t	t
2520	Prima de servicios	2	4	\N	decreto2650	t	t
2525	Vacaciones consolidadas	2	4	\N	decreto2650	t	t
2530	Prestaciones extralegales	2	4	\N	decreto2650	t	t
2532	Pensiones por pagar	2	4	\N	decreto2650	t	t
2535	Cuotas partes pensiones de jubilación	2	4	\N	decreto2650	t	t
2540	Indemnizaciones laborales	2	4	\N	decreto2650	t	t
26	Pasivos estimados y provisiones	2	2	\N	decreto2650	t	t
2605	Para costos y gastos	2	4	\N	decreto2650	t	t
2610	Para obligaciones laborales	2	4	\N	decreto2650	t	t
2615	Para obligaciones fiscales	2	4	\N	decreto2650	t	t
2620	Pensiones de jubilación	2	4	\N	decreto2650	t	t
2625	Para obras de urbanismo	2	4	\N	decreto2650	t	t
2630	Para mantenimiento y reparaciones	2	4	\N	decreto2650	t	t
2635	Para contingencias	2	4	\N	decreto2650	t	t
2640	Para obligaciones de garantías	2	4	\N	decreto2650	t	t
2695	Provisiones diversas	2	4	\N	decreto2650	t	t
27	Diferidos	2	2	\N	decreto2650	t	t
2705	Ingresos recibidos por anticipado	2	4	\N	decreto2650	t	t
2710	Abonos diferidos	2	4	\N	decreto2650	t	t
2715	Utilidad diferida en ventas a plazos	2	4	\N	decreto2650	t	t
2720	Crédito por corrección monetaria diferida	2	4	\N	decreto2650	t	t
2725	Impuestos diferidos	2	4	\N	decreto2650	t	t
28	Otros pasivos	2	2	\N	decreto2650	t	t
2805	Anticipos y avances recibidos	2	4	\N	decreto2650	t	t
2810	Depósitos recibidos	2	4	\N	decreto2650	t	t
2815	Ingresos recibidos para terceros	2	4	\N	decreto2650	t	t
2820	Cuentas de operación conjunta	2	4	\N	decreto2650	t	t
2825	Retenciones a terceros sobre contratos	2	4	\N	decreto2650	t	t
2830	Embargos judiciales	2	4	\N	decreto2650	t	t
2835	Acreedores del sistema	2	4	\N	decreto2650	t	t
2840	Cuentas en participación	2	4	\N	decreto2650	t	t
2895	Diversos	2	4	\N	decreto2650	t	t
29	Bonos y papeles comerciales	2	2	\N	decreto2650	t	t
2905	Bonos en circulación	2	4	\N	decreto2650	t	t
2910	Bonos obligatoriamente convertibles en acciones	2	4	\N	decreto2650	t	t
2915	Papeles comerciales	2	4	\N	decreto2650	t	t
2920	Bonos pensionales	2	4	\N	decreto2650	t	t
2925	Títulos pensionales	2	4	\N	decreto2650	t	t
31	Capital social	3	2	\N	decreto2650	t	t
3105	Capital suscrito y pagado	3	4	\N	decreto2650	t	t
3115	Aportes sociales	3	4	\N	decreto2650	t	t
3120	Capital asignado	3	4	\N	decreto2650	t	t
3125	Inversión suplementaria al capital asignado	3	4	\N	decreto2650	t	t
3130	Capital de personas naturales	3	4	\N	decreto2650	t	t
3135	Aportes del Estado	3	4	\N	decreto2650	t	t
3140	Fondo social	3	4	\N	decreto2650	t	t
32	Superávit de capital	3	2	\N	decreto2650	t	t
3205	Prima en colocación de acciones, cuotas o partes de interés social	3	4	\N	decreto2650	t	t
3210	Donaciones	3	4	\N	decreto2650	t	t
3215	Crédito mercantil	3	4	\N	decreto2650	t	t
3220	Know how	3	4	\N	decreto2650	t	t
3225	Superávit método de participación	3	4	\N	decreto2650	t	t
33	Reservas	3	2	\N	decreto2650	t	t
3305	Reservas obligatorias	3	4	\N	decreto2650	t	t
3310	Reservas estatutarias	3	4	\N	decreto2650	t	t
3315	Reservas ocasionales	3	4	\N	decreto2650	t	t
34	Revalorización del patrimonio	3	2	\N	decreto2650	t	t
3405	Ajustes por inflación	3	4	\N	decreto2650	t	t
3410	Saneamiento fiscal	3	4	\N	decreto2650	t	t
3415	Ajustes por inflación Decreto 3019 de 1989	3	4	\N	decreto2650	t	t
35	Dividendos o participaciones decretados en acciones, cuotas o partes de interés social	3	2	\N	decreto2650	t	t
3505	Dividendos decretados en acciones	3	4	\N	decreto2650	t	t
3510	Participaciones decretadas en cuotas o partes de interés social	3	4	\N	decreto2650	t	t
36	Resultados del ejercicio	3	2	\N	decreto2650	t	t
3605	Utilidad del ejercicio	3	4	\N	decreto2650	t	t
3610	Pérdida del ejercicio	3	4	D	decreto2650	t	t
37	Resultados de ejercicios anteriores	3	2	\N	decreto2650	t	t
3705	Utilidades acumuladas	3	4	\N	decreto2650	t	t
3710	Pérdidas acumuladas	3	4	D	decreto2650	t	t
38	Superávit por valorizaciones	3	2	\N	decreto2650	t	t
3805	De inversiones	3	4	\N	decreto2650	t	t
3810	De propiedades, planta y equipo	3	4	\N	decreto2650	t	t
3895	De otros activos	3	4	\N	decreto2650	t	t
41	Operacionales	4	2	\N	decreto2650	t	t
4105	Agricultura, ganadería, caza y silvicultura	4	4	\N	decreto2650	t	t
4110	Pesca	4	4	\N	decreto2650	t	t
4115	Explotación de minas y canteras	4	4	\N	decreto2650	t	t
4120	Industrias manufactureras	4	4	\N	decreto2650	t	t
4125	Suministro de electricidad, gas y agua	4	4	\N	decreto2650	t	t
4130	Construcción	4	4	\N	decreto2650	t	t
4135	Comercio al por mayor y al por menor	4	4	\N	decreto2650	t	t
4140	Hoteles y restaurantes	4	4	\N	decreto2650	t	t
4145	Transporte, almacenamiento y comunicaciones	4	4	\N	decreto2650	t	t
4150	Actividad financiera	4	4	\N	decreto2650	t	t
4155	Actividades inmobiliarias, empresariales y de alquiler	4	4	\N	decreto2650	t	t
4160	Enseñanza	4	4	\N	decreto2650	t	t
4165	Servicios sociales y de salud	4	4	\N	decreto2650	t	t
4170	Otras actividades de servicios comunitarios, sociales y personales	4	4	\N	decreto2650	t	t
4175	Devoluciones en ventas (DB)	4	4	D	decreto2650	t	t
42	No operacionales	4	2	\N	decreto2650	t	t
4205	Otras ventas	4	4	\N	decreto2650	t	t
4210	Financieros	4	4	\N	decreto2650	t	t
4215	Dividendos y participaciones	4	4	\N	decreto2650	t	t
4218	Ingresos método de participación	4	4	\N	decreto2650	t	t
4220	Arrendamientos	4	4	\N	decreto2650	t	t
4225	Comisiones	4	4	\N	decreto2650	t	t
4230	Honorarios	4	4	\N	decreto2650	t	t
4235	Servicios	4	4	\N	decreto2650	t	t
4240	Utilidad en venta de inversiones	4	4	\N	decreto2650	t	t
4245	Utilidad en venta de propiedades, planta y equipo	4	4	\N	decreto2650	t	t
4248	Utilidad en venta de otros bienes	4	4	\N	decreto2650	t	t
4250	Recuperaciones	4	4	\N	decreto2650	t	t
4255	Indemnizaciones	4	4	\N	decreto2650	t	t
4260	Participaciones en concesiones	4	4	\N	decreto2650	t	t
4265	Ingresos de ejercicios anteriores	4	4	\N	decreto2650	t	t
4275	Devoluciones en otras ventas (DB)	4	4	D	decreto2650	t	t
4295	Diversos	4	4	\N	decreto2650	t	t
47	Ajustes por inflación	4	2	\N	decreto2650	t	t
4705	Corrección monetaria	4	4	\N	decreto2650	t	t
51	Operacionales de administración	5	2	\N	decreto2650	t	t
5105	Gastos de personal	5	4	\N	decreto2650	t	t
5110	Honorarios	5	4	\N	decreto2650	t	t
5115	Impuestos	5	4	\N	decreto2650	t	t
5120	Arrendamientos	5	4	\N	decreto2650	t	t
5125	Contribuciones y afiliaciones	5	4	\N	decreto2650	t	t
5130	Seguros	5	4	\N	decreto2650	t	t
5135	Servicios	5	4	\N	decreto2650	t	t
5140	Gastos legales	5	4	\N	decreto2650	t	t
5145	Mantenimiento y reparaciones	5	4	\N	decreto2650	t	t
5150	Adecuación e instalación	5	4	\N	decreto2650	t	t
5155	Gastos de viaje	5	4	\N	decreto2650	t	t
5160	Depreciaciones	5	4	\N	decreto2650	t	t
5165	Amortizaciones	5	4	\N	decreto2650	t	t
5195	Diversos	5	4	\N	decreto2650	t	t
5199	Provisiones	5	4	\N	decreto2650	t	t
52	Operacionales de ventas	5	2	\N	decreto2650	t	t
5205	Gastos de personal	5	4	\N	decreto2650	t	t
5210	Honorarios	5	4	\N	decreto2650	t	t
5215	Impuestos	5	4	\N	decreto2650	t	t
5220	Arrendamientos	5	4	\N	decreto2650	t	t
5225	Contribuciones y afiliaciones	5	4	\N	decreto2650	t	t
5230	Seguros	5	4	\N	decreto2650	t	t
5235	Servicios	5	4	\N	decreto2650	t	t
5240	Gastos legales	5	4	\N	decreto2650	t	t
5245	Mantenimiento y reparaciones	5	4	\N	decreto2650	t	t
5250	Adecuación e instalación	5	4	\N	decreto2650	t	t
5255	Gastos de viaje	5	4	\N	decreto2650	t	t
5260	Depreciaciones	5	4	\N	decreto2650	t	t
5265	Amortizaciones	5	4	\N	decreto2650	t	t
5270	Financieros-reajuste del sistema	5	4	\N	decreto2650	t	t
5275	Pérdidas método de participación	5	4	\N	decreto2650	t	t
5295	Diversos	5	4	\N	decreto2650	t	t
5299	Provisiones	5	4	\N	decreto2650	t	t
53	No operacionales	5	2	\N	decreto2650	t	t
5305	Financieros	5	4	\N	decreto2650	t	t
5310	Pérdida en venta y retiro de bienes	5	4	\N	decreto2650	t	t
5313	Pérdidas método de participación	5	4	\N	decreto2650	t	t
5315	Gastos extraordinarios	5	4	\N	decreto2650	t	t
5395	Gastos diversos	5	4	\N	decreto2650	t	t
54	Impuesto de renta y complementarios	5	2	\N	decreto2650	t	t
5405	Impuesto de renta y complementarios	5	4	\N	decreto2650	t	t
59	Ganancias y pérdidas	5	2	\N	decreto2650	t	t
5905	Ganancias y pérdidas	5	4	\N	decreto2650	t	t
61	Costo de ventas y de prestación de servicios	6	2	\N	decreto2650	t	t
6105	Agricultura, ganadería, caza y silvicultura	6	4	\N	decreto2650	t	t
6110	Pesca	6	4	\N	decreto2650	t	t
6115	Explotación de minas y canteras	6	4	\N	decreto2650	t	t
6120	Industrias manufactureras	6	4	\N	decreto2650	t	t
6125	Suministro de electricidad, gas y agua	6	4	\N	decreto2650	t	t
6130	Construcción	6	4	\N	decreto2650	t	t
6135	Comercio al por mayor y al por menor	6	4	\N	decreto2650	t	t
6140	Hoteles y restaurantes	6	4	\N	decreto2650	t	t
6145	Transporte, almacenamiento y comunicaciones	6	4	\N	decreto2650	t	t
6150	Actividad financiera	6	4	\N	decreto2650	t	t
6155	Actividades inmobiliarias, empresariales y de alquiler	6	4	\N	decreto2650	t	t
6160	Enseñanza	6	4	\N	decreto2650	t	t
6165	Servicios sociales y de salud	6	4	\N	decreto2650	t	t
6170	Otras actividades de servicios comunitarios, sociales y personales	6	4	\N	decreto2650	t	t
62	Compras	6	2	\N	decreto2650	t	t
6205	De mercancías	6	4	\N	decreto2650	t	t
6210	De materias primas	6	4	\N	decreto2650	t	t
6215	De materiales indirectos	6	4	\N	decreto2650	t	t
6220	Compra de energía	6	4	\N	decreto2650	t	t
6225	Devoluciones en compras (CR)	6	4	C	decreto2650	t	t
71	Materia prima	7	2	\N	decreto2650	t	t
72	Mano de obra directa	7	2	\N	decreto2650	t	t
73	Costos indirectos	7	2	\N	decreto2650	t	t
74	Contratos de servicios	7	2	\N	decreto2650	t	t
\.


--
-- Data for Name: puc_clase; Type: TABLE DATA; Schema: core; Owner: -
--

COPY core.puc_clase (clase, nombre, naturaleza, signo, tipo_estado, comparativo) FROM stdin;
1	Activo	D	1	BALANCE	CIERRE_ANTERIOR
2	Pasivo	C	-1	BALANCE	CIERRE_ANTERIOR
3	Patrimonio	C	-1	BALANCE	CIERRE_ANTERIOR
4	Ingresos	C	-1	RESULTADO	MISMO_PERIODO
5	Gastos	D	1	RESULTADO	MISMO_PERIODO
6	Costos de venta	D	1	RESULTADO	MISMO_PERIODO
7	Costos de producción o de operación	D	1	RESULTADO	MISMO_PERIODO
\.


--
-- Data for Name: puc_nivel; Type: TABLE DATA; Schema: core; Owner: -
--

COPY core.puc_nivel (nivel, digitos, orden) FROM stdin;
Clase	1	1
Grupo	2	2
Cuenta	4	3
Subcuenta	6	4
Auxiliar	8	5
Subauxiliar	10	6
\.


--
-- Name: alerta_id_seq; Type: SEQUENCE SET; Schema: core; Owner: -
--

SELECT pg_catalog.setval('core.alerta_id_seq', 2, true);


--
-- Name: balance_id_seq; Type: SEQUENCE SET; Schema: core; Owner: -
--

SELECT pg_catalog.setval('core.balance_id_seq', 13308, true);


--
-- Name: cotejo_detalle_id_seq; Type: SEQUENCE SET; Schema: core; Owner: -
--

SELECT pg_catalog.setval('core.cotejo_detalle_id_seq', 1661, true);


--
-- Name: cotejo_id_seq; Type: SEQUENCE SET; Schema: core; Owner: -
--

SELECT pg_catalog.setval('core.cotejo_id_seq', 23, true);


--
-- Name: hallazgo_id_seq; Type: SEQUENCE SET; Schema: core; Owner: -
--

SELECT pg_catalog.setval('core.hallazgo_id_seq', 13, true);


--
-- Name: materialidad_historia_id_seq; Type: SEQUENCE SET; Schema: core; Owner: -
--

SELECT pg_catalog.setval('core.materialidad_historia_id_seq', 14, true);


--
-- Name: materialidad_id_seq; Type: SEQUENCE SET; Schema: core; Owner: -
--

SELECT pg_catalog.setval('core.materialidad_id_seq', 6, true);


--
-- Name: nota_alcance_id_seq; Type: SEQUENCE SET; Schema: core; Owner: -
--

SELECT pg_catalog.setval('core.nota_alcance_id_seq', 1, false);


--
-- Name: perfil_mapeo_id_seq; Type: SEQUENCE SET; Schema: core; Owner: -
--

SELECT pg_catalog.setval('core.perfil_mapeo_id_seq', 6, true);


--
-- Name: alerta alerta_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.alerta
    ADD CONSTRAINT alerta_pkey PRIMARY KEY (id);


--
-- Name: balance balance_carga_id_codigo_puc_key; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.balance
    ADD CONSTRAINT balance_carga_id_codigo_puc_key UNIQUE (carga_id, codigo_puc);


--
-- Name: balance balance_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.balance
    ADD CONSTRAINT balance_pkey PRIMARY KEY (id);


--
-- Name: campo_canonico campo_canonico_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.campo_canonico
    ADD CONSTRAINT campo_canonico_pkey PRIMARY KEY (naturaleza, campo);


--
-- Name: carga carga_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.carga
    ADD CONSTRAINT carga_pkey PRIMARY KEY (id);


--
-- Name: cliente cliente_nit_key; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.cliente
    ADD CONSTRAINT cliente_nit_key UNIQUE (nit);


--
-- Name: cliente cliente_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.cliente
    ADD CONSTRAINT cliente_pkey PRIMARY KEY (id);


--
-- Name: cliente cliente_seudonimo_key; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.cliente
    ADD CONSTRAINT cliente_seudonimo_key UNIQUE (seudonimo);


--
-- Name: cotejo_detalle cotejo_detalle_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.cotejo_detalle
    ADD CONSTRAINT cotejo_detalle_pkey PRIMARY KEY (id);


--
-- Name: cotejo cotejo_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.cotejo
    ADD CONSTRAINT cotejo_pkey PRIMARY KEY (id);


--
-- Name: encargo encargo_cliente_id_fecha_corte_key; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.encargo
    ADD CONSTRAINT encargo_cliente_id_fecha_corte_key UNIQUE (cliente_id, fecha_corte);


--
-- Name: encargo_insumo encargo_insumo_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.encargo_insumo
    ADD CONSTRAINT encargo_insumo_pkey PRIMARY KEY (encargo_id, tipo);


--
-- Name: encargo encargo_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.encargo
    ADD CONSTRAINT encargo_pkey PRIMARY KEY (id);


--
-- Name: fase fase_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.fase
    ADD CONSTRAINT fase_pkey PRIMARY KEY (fase);


--
-- Name: hallazgo hallazgo_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.hallazgo
    ADD CONSTRAINT hallazgo_pkey PRIMARY KEY (id);


--
-- Name: insumo insumo_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.insumo
    ADD CONSTRAINT insumo_pkey PRIMARY KEY (tipo);


--
-- Name: materialidad materialidad_encargo_id_fase_key; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.materialidad
    ADD CONSTRAINT materialidad_encargo_id_fase_key UNIQUE (encargo_id, fase);


--
-- Name: materialidad_historia materialidad_historia_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.materialidad_historia
    ADD CONSTRAINT materialidad_historia_pkey PRIMARY KEY (id);


--
-- Name: materialidad materialidad_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.materialidad
    ADD CONSTRAINT materialidad_pkey PRIMARY KEY (id);


--
-- Name: movimiento movimiento_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.movimiento
    ADD CONSTRAINT movimiento_pkey PRIMARY KEY (id, fecha);


--
-- Name: movimiento_2024 movimiento_2024_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.movimiento_2024
    ADD CONSTRAINT movimiento_2024_pkey PRIMARY KEY (id, fecha);


--
-- Name: movimiento_2025 movimiento_2025_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.movimiento_2025
    ADD CONSTRAINT movimiento_2025_pkey PRIMARY KEY (id, fecha);


--
-- Name: movimiento_2026 movimiento_2026_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.movimiento_2026
    ADD CONSTRAINT movimiento_2026_pkey PRIMARY KEY (id, fecha);


--
-- Name: movimiento_2027 movimiento_2027_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.movimiento_2027
    ADD CONSTRAINT movimiento_2027_pkey PRIMARY KEY (id, fecha);


--
-- Name: movimiento_default movimiento_default_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.movimiento_default
    ADD CONSTRAINT movimiento_default_pkey PRIMARY KEY (id, fecha);


--
-- Name: nivel_cargable nivel_cargable_digitos_key; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.nivel_cargable
    ADD CONSTRAINT nivel_cargable_digitos_key UNIQUE (digitos);


--
-- Name: nivel_cargable nivel_cargable_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.nivel_cargable
    ADD CONSTRAINT nivel_cargable_pkey PRIMARY KEY (nivel);


--
-- Name: nota_alcance nota_alcance_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.nota_alcance
    ADD CONSTRAINT nota_alcance_pkey PRIMARY KEY (id);


--
-- Name: perfil_mapeo perfil_mapeo_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.perfil_mapeo
    ADD CONSTRAINT perfil_mapeo_pkey PRIMARY KEY (id);


--
-- Name: puc_clase puc_clase_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.puc_clase
    ADD CONSTRAINT puc_clase_pkey PRIMARY KEY (clase);


--
-- Name: puc_nivel puc_nivel_digitos_key; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.puc_nivel
    ADD CONSTRAINT puc_nivel_digitos_key UNIQUE (digitos);


--
-- Name: puc_nivel puc_nivel_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.puc_nivel
    ADD CONSTRAINT puc_nivel_pkey PRIMARY KEY (nivel);


--
-- Name: puc puc_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.puc
    ADD CONSTRAINT puc_pkey PRIMARY KEY (codigo);


--
-- Name: ix_alerta_pend; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_alerta_pend ON core.alerta USING btree (estado, creada_en);


--
-- Name: ix_balance_cuenta; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_balance_cuenta ON core.balance USING btree (carga_id, cuenta);


--
-- Name: ix_balance_nivel; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_balance_nivel ON core.balance USING btree (carga_id, nivel);


--
-- Name: ix_carga_cliente; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_carga_cliente ON core.carga USING btree (cliente_id, tipo, periodo_ini, periodo_fin);


--
-- Name: ix_carga_hash; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_carga_hash ON core.carga USING btree (cliente_id, hash_sha256);


--
-- Name: ix_cotejo_det; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_cotejo_det ON core.cotejo_detalle USING btree (cotejo_id, cambio);


--
-- Name: ix_cotejo_fuera; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_cotejo_fuera ON core.cotejo_detalle USING btree (cotejo_id) WHERE fuera_periodo;


--
-- Name: ix_encargo_insumo_carga; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_encargo_insumo_carga ON core.encargo_insumo USING btree (carga_id);


--
-- Name: ix_hallazgo; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_hallazgo ON core.hallazgo USING btree (encargo_id, severidad);


--
-- Name: ix_mat_historia; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_mat_historia ON core.materialidad_historia USING btree (encargo_id, cambiado_en DESC);


--
-- Name: ix_materialidad; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_materialidad ON core.materialidad USING btree (encargo_id, fase);


--
-- Name: ix_mov_doc; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_mov_doc ON ONLY core.movimiento USING btree (carga_id, num_doc);


--
-- Name: ix_mov_drill; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_mov_drill ON ONLY core.movimiento USING btree (carga_id, cuenta, subcuenta, fecha);


--
-- Name: ix_mov_encargo; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_mov_encargo ON ONLY core.movimiento USING btree (encargo_id, cuenta, fecha);


--
-- Name: ix_mov_patron; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_mov_patron ON ONLY core.movimiento USING btree (carga_id, cuenta, desc_norm);


--
-- Name: ix_mov_tercero; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_mov_tercero ON ONLY core.movimiento USING btree (carga_id, tercero_nit);


--
-- Name: ix_nota_alcance; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_nota_alcance ON core.nota_alcance USING btree (encargo_id, fase, creado_en DESC);


--
-- Name: ix_puc_clase; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX ix_puc_clase ON core.puc USING btree (clase, digitos);


--
-- Name: movimiento_2024_carga_id_cuenta_desc_norm_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX movimiento_2024_carga_id_cuenta_desc_norm_idx ON core.movimiento_2024 USING btree (carga_id, cuenta, desc_norm);


--
-- Name: movimiento_2024_carga_id_cuenta_subcuenta_fecha_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX movimiento_2024_carga_id_cuenta_subcuenta_fecha_idx ON core.movimiento_2024 USING btree (carga_id, cuenta, subcuenta, fecha);


--
-- Name: movimiento_2024_carga_id_num_doc_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX movimiento_2024_carga_id_num_doc_idx ON core.movimiento_2024 USING btree (carga_id, num_doc);


--
-- Name: movimiento_2024_carga_id_tercero_nit_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX movimiento_2024_carga_id_tercero_nit_idx ON core.movimiento_2024 USING btree (carga_id, tercero_nit);


--
-- Name: movimiento_2024_encargo_id_cuenta_fecha_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX movimiento_2024_encargo_id_cuenta_fecha_idx ON core.movimiento_2024 USING btree (encargo_id, cuenta, fecha);


--
-- Name: movimiento_2025_carga_id_cuenta_desc_norm_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX movimiento_2025_carga_id_cuenta_desc_norm_idx ON core.movimiento_2025 USING btree (carga_id, cuenta, desc_norm);


--
-- Name: movimiento_2025_carga_id_cuenta_subcuenta_fecha_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX movimiento_2025_carga_id_cuenta_subcuenta_fecha_idx ON core.movimiento_2025 USING btree (carga_id, cuenta, subcuenta, fecha);


--
-- Name: movimiento_2025_carga_id_num_doc_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX movimiento_2025_carga_id_num_doc_idx ON core.movimiento_2025 USING btree (carga_id, num_doc);


--
-- Name: movimiento_2025_carga_id_tercero_nit_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX movimiento_2025_carga_id_tercero_nit_idx ON core.movimiento_2025 USING btree (carga_id, tercero_nit);


--
-- Name: movimiento_2025_encargo_id_cuenta_fecha_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX movimiento_2025_encargo_id_cuenta_fecha_idx ON core.movimiento_2025 USING btree (encargo_id, cuenta, fecha);


--
-- Name: movimiento_2026_carga_id_cuenta_desc_norm_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX movimiento_2026_carga_id_cuenta_desc_norm_idx ON core.movimiento_2026 USING btree (carga_id, cuenta, desc_norm);


--
-- Name: movimiento_2026_carga_id_cuenta_subcuenta_fecha_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX movimiento_2026_carga_id_cuenta_subcuenta_fecha_idx ON core.movimiento_2026 USING btree (carga_id, cuenta, subcuenta, fecha);


--
-- Name: movimiento_2026_carga_id_num_doc_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX movimiento_2026_carga_id_num_doc_idx ON core.movimiento_2026 USING btree (carga_id, num_doc);


--
-- Name: movimiento_2026_carga_id_tercero_nit_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX movimiento_2026_carga_id_tercero_nit_idx ON core.movimiento_2026 USING btree (carga_id, tercero_nit);


--
-- Name: movimiento_2026_encargo_id_cuenta_fecha_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX movimiento_2026_encargo_id_cuenta_fecha_idx ON core.movimiento_2026 USING btree (encargo_id, cuenta, fecha);


--
-- Name: movimiento_2027_carga_id_cuenta_desc_norm_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX movimiento_2027_carga_id_cuenta_desc_norm_idx ON core.movimiento_2027 USING btree (carga_id, cuenta, desc_norm);


--
-- Name: movimiento_2027_carga_id_cuenta_subcuenta_fecha_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX movimiento_2027_carga_id_cuenta_subcuenta_fecha_idx ON core.movimiento_2027 USING btree (carga_id, cuenta, subcuenta, fecha);


--
-- Name: movimiento_2027_carga_id_num_doc_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX movimiento_2027_carga_id_num_doc_idx ON core.movimiento_2027 USING btree (carga_id, num_doc);


--
-- Name: movimiento_2027_carga_id_tercero_nit_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX movimiento_2027_carga_id_tercero_nit_idx ON core.movimiento_2027 USING btree (carga_id, tercero_nit);


--
-- Name: movimiento_2027_encargo_id_cuenta_fecha_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX movimiento_2027_encargo_id_cuenta_fecha_idx ON core.movimiento_2027 USING btree (encargo_id, cuenta, fecha);


--
-- Name: movimiento_default_carga_id_cuenta_desc_norm_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX movimiento_default_carga_id_cuenta_desc_norm_idx ON core.movimiento_default USING btree (carga_id, cuenta, desc_norm);


--
-- Name: movimiento_default_carga_id_cuenta_subcuenta_fecha_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX movimiento_default_carga_id_cuenta_subcuenta_fecha_idx ON core.movimiento_default USING btree (carga_id, cuenta, subcuenta, fecha);


--
-- Name: movimiento_default_carga_id_num_doc_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX movimiento_default_carga_id_num_doc_idx ON core.movimiento_default USING btree (carga_id, num_doc);


--
-- Name: movimiento_default_carga_id_tercero_nit_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX movimiento_default_carga_id_tercero_nit_idx ON core.movimiento_default USING btree (carga_id, tercero_nit);


--
-- Name: movimiento_default_encargo_id_cuenta_fecha_idx; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX movimiento_default_encargo_id_cuenta_fecha_idx ON core.movimiento_default USING btree (encargo_id, cuenta, fecha);


--
-- Name: uq_perfil_vigente; Type: INDEX; Schema: core; Owner: -
--

CREATE UNIQUE INDEX uq_perfil_vigente ON core.perfil_mapeo USING btree (cliente_id, tipo) WHERE vigente;


--
-- Name: uq_sinonimo; Type: INDEX; Schema: core; Owner: -
--

CREATE UNIQUE INDEX uq_sinonimo ON core.campo_sinonimo USING btree (naturaleza, norm);


--
-- Name: ix_bal_stg; Type: INDEX; Schema: raw; Owner: -
--

CREATE INDEX ix_bal_stg ON raw.balance_staging USING btree (carga_id);


--
-- Name: ix_bal_stg_llave; Type: INDEX; Schema: raw; Owner: -
--

CREATE INDEX ix_bal_stg_llave ON raw.balance_staging USING btree (carga_id, llave);


--
-- Name: ix_mov_stg; Type: INDEX; Schema: raw; Owner: -
--

CREATE INDEX ix_mov_stg ON raw.movimiento_staging USING btree (carga_id);


--
-- Name: ix_mov_stg_llave; Type: INDEX; Schema: raw; Owner: -
--

CREATE INDEX ix_mov_stg_llave ON raw.movimiento_staging USING btree (carga_id, llave);


--
-- Name: movimiento_2024_carga_id_cuenta_desc_norm_idx; Type: INDEX ATTACH; Schema: core; Owner: -
--

ALTER INDEX core.ix_mov_patron ATTACH PARTITION core.movimiento_2024_carga_id_cuenta_desc_norm_idx;


--
-- Name: movimiento_2024_carga_id_cuenta_subcuenta_fecha_idx; Type: INDEX ATTACH; Schema: core; Owner: -
--

ALTER INDEX core.ix_mov_drill ATTACH PARTITION core.movimiento_2024_carga_id_cuenta_subcuenta_fecha_idx;


--
-- Name: movimiento_2024_carga_id_num_doc_idx; Type: INDEX ATTACH; Schema: core; Owner: -
--

ALTER INDEX core.ix_mov_doc ATTACH PARTITION core.movimiento_2024_carga_id_num_doc_idx;


--
-- Name: movimiento_2024_carga_id_tercero_nit_idx; Type: INDEX ATTACH; Schema: core; Owner: -
--

ALTER INDEX core.ix_mov_tercero ATTACH PARTITION core.movimiento_2024_carga_id_tercero_nit_idx;


--
-- Name: movimiento_2024_encargo_id_cuenta_fecha_idx; Type: INDEX ATTACH; Schema: core; Owner: -
--

ALTER INDEX core.ix_mov_encargo ATTACH PARTITION core.movimiento_2024_encargo_id_cuenta_fecha_idx;


--
-- Name: movimiento_2024_pkey; Type: INDEX ATTACH; Schema: core; Owner: -
--

ALTER INDEX core.movimiento_pkey ATTACH PARTITION core.movimiento_2024_pkey;


--
-- Name: movimiento_2025_carga_id_cuenta_desc_norm_idx; Type: INDEX ATTACH; Schema: core; Owner: -
--

ALTER INDEX core.ix_mov_patron ATTACH PARTITION core.movimiento_2025_carga_id_cuenta_desc_norm_idx;


--
-- Name: movimiento_2025_carga_id_cuenta_subcuenta_fecha_idx; Type: INDEX ATTACH; Schema: core; Owner: -
--

ALTER INDEX core.ix_mov_drill ATTACH PARTITION core.movimiento_2025_carga_id_cuenta_subcuenta_fecha_idx;


--
-- Name: movimiento_2025_carga_id_num_doc_idx; Type: INDEX ATTACH; Schema: core; Owner: -
--

ALTER INDEX core.ix_mov_doc ATTACH PARTITION core.movimiento_2025_carga_id_num_doc_idx;


--
-- Name: movimiento_2025_carga_id_tercero_nit_idx; Type: INDEX ATTACH; Schema: core; Owner: -
--

ALTER INDEX core.ix_mov_tercero ATTACH PARTITION core.movimiento_2025_carga_id_tercero_nit_idx;


--
-- Name: movimiento_2025_encargo_id_cuenta_fecha_idx; Type: INDEX ATTACH; Schema: core; Owner: -
--

ALTER INDEX core.ix_mov_encargo ATTACH PARTITION core.movimiento_2025_encargo_id_cuenta_fecha_idx;


--
-- Name: movimiento_2025_pkey; Type: INDEX ATTACH; Schema: core; Owner: -
--

ALTER INDEX core.movimiento_pkey ATTACH PARTITION core.movimiento_2025_pkey;


--
-- Name: movimiento_2026_carga_id_cuenta_desc_norm_idx; Type: INDEX ATTACH; Schema: core; Owner: -
--

ALTER INDEX core.ix_mov_patron ATTACH PARTITION core.movimiento_2026_carga_id_cuenta_desc_norm_idx;


--
-- Name: movimiento_2026_carga_id_cuenta_subcuenta_fecha_idx; Type: INDEX ATTACH; Schema: core; Owner: -
--

ALTER INDEX core.ix_mov_drill ATTACH PARTITION core.movimiento_2026_carga_id_cuenta_subcuenta_fecha_idx;


--
-- Name: movimiento_2026_carga_id_num_doc_idx; Type: INDEX ATTACH; Schema: core; Owner: -
--

ALTER INDEX core.ix_mov_doc ATTACH PARTITION core.movimiento_2026_carga_id_num_doc_idx;


--
-- Name: movimiento_2026_carga_id_tercero_nit_idx; Type: INDEX ATTACH; Schema: core; Owner: -
--

ALTER INDEX core.ix_mov_tercero ATTACH PARTITION core.movimiento_2026_carga_id_tercero_nit_idx;


--
-- Name: movimiento_2026_encargo_id_cuenta_fecha_idx; Type: INDEX ATTACH; Schema: core; Owner: -
--

ALTER INDEX core.ix_mov_encargo ATTACH PARTITION core.movimiento_2026_encargo_id_cuenta_fecha_idx;


--
-- Name: movimiento_2026_pkey; Type: INDEX ATTACH; Schema: core; Owner: -
--

ALTER INDEX core.movimiento_pkey ATTACH PARTITION core.movimiento_2026_pkey;


--
-- Name: movimiento_2027_carga_id_cuenta_desc_norm_idx; Type: INDEX ATTACH; Schema: core; Owner: -
--

ALTER INDEX core.ix_mov_patron ATTACH PARTITION core.movimiento_2027_carga_id_cuenta_desc_norm_idx;


--
-- Name: movimiento_2027_carga_id_cuenta_subcuenta_fecha_idx; Type: INDEX ATTACH; Schema: core; Owner: -
--

ALTER INDEX core.ix_mov_drill ATTACH PARTITION core.movimiento_2027_carga_id_cuenta_subcuenta_fecha_idx;


--
-- Name: movimiento_2027_carga_id_num_doc_idx; Type: INDEX ATTACH; Schema: core; Owner: -
--

ALTER INDEX core.ix_mov_doc ATTACH PARTITION core.movimiento_2027_carga_id_num_doc_idx;


--
-- Name: movimiento_2027_carga_id_tercero_nit_idx; Type: INDEX ATTACH; Schema: core; Owner: -
--

ALTER INDEX core.ix_mov_tercero ATTACH PARTITION core.movimiento_2027_carga_id_tercero_nit_idx;


--
-- Name: movimiento_2027_encargo_id_cuenta_fecha_idx; Type: INDEX ATTACH; Schema: core; Owner: -
--

ALTER INDEX core.ix_mov_encargo ATTACH PARTITION core.movimiento_2027_encargo_id_cuenta_fecha_idx;


--
-- Name: movimiento_2027_pkey; Type: INDEX ATTACH; Schema: core; Owner: -
--

ALTER INDEX core.movimiento_pkey ATTACH PARTITION core.movimiento_2027_pkey;


--
-- Name: movimiento_default_carga_id_cuenta_desc_norm_idx; Type: INDEX ATTACH; Schema: core; Owner: -
--

ALTER INDEX core.ix_mov_patron ATTACH PARTITION core.movimiento_default_carga_id_cuenta_desc_norm_idx;


--
-- Name: movimiento_default_carga_id_cuenta_subcuenta_fecha_idx; Type: INDEX ATTACH; Schema: core; Owner: -
--

ALTER INDEX core.ix_mov_drill ATTACH PARTITION core.movimiento_default_carga_id_cuenta_subcuenta_fecha_idx;


--
-- Name: movimiento_default_carga_id_num_doc_idx; Type: INDEX ATTACH; Schema: core; Owner: -
--

ALTER INDEX core.ix_mov_doc ATTACH PARTITION core.movimiento_default_carga_id_num_doc_idx;


--
-- Name: movimiento_default_carga_id_tercero_nit_idx; Type: INDEX ATTACH; Schema: core; Owner: -
--

ALTER INDEX core.ix_mov_tercero ATTACH PARTITION core.movimiento_default_carga_id_tercero_nit_idx;


--
-- Name: movimiento_default_encargo_id_cuenta_fecha_idx; Type: INDEX ATTACH; Schema: core; Owner: -
--

ALTER INDEX core.ix_mov_encargo ATTACH PARTITION core.movimiento_default_encargo_id_cuenta_fecha_idx;


--
-- Name: movimiento_default_pkey; Type: INDEX ATTACH; Schema: core; Owner: -
--

ALTER INDEX core.movimiento_pkey ATTACH PARTITION core.movimiento_default_pkey;


--
-- Name: alerta alerta_cliente_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.alerta
    ADD CONSTRAINT alerta_cliente_id_fkey FOREIGN KEY (cliente_id) REFERENCES core.cliente(id) ON DELETE CASCADE;


--
-- Name: alerta alerta_cotejo_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.alerta
    ADD CONSTRAINT alerta_cotejo_id_fkey FOREIGN KEY (cotejo_id) REFERENCES core.cotejo(id) ON DELETE SET NULL;


--
-- Name: alerta alerta_encargo_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.alerta
    ADD CONSTRAINT alerta_encargo_id_fkey FOREIGN KEY (encargo_id) REFERENCES core.encargo(id) ON DELETE SET NULL;


--
-- Name: balance balance_carga_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.balance
    ADD CONSTRAINT balance_carga_id_fkey FOREIGN KEY (carga_id) REFERENCES core.carga(id) ON DELETE CASCADE;


--
-- Name: balance balance_cliente_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.balance
    ADD CONSTRAINT balance_cliente_id_fkey FOREIGN KEY (cliente_id) REFERENCES core.cliente(id) ON DELETE CASCADE;


--
-- Name: balance balance_nivel_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.balance
    ADD CONSTRAINT balance_nivel_fkey FOREIGN KEY (nivel) REFERENCES core.nivel_cargable(nivel);


--
-- Name: campo_sinonimo campo_sinonimo_naturaleza_campo_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.campo_sinonimo
    ADD CONSTRAINT campo_sinonimo_naturaleza_campo_fkey FOREIGN KEY (naturaleza, campo) REFERENCES core.campo_canonico(naturaleza, campo);


--
-- Name: carga carga_cliente_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.carga
    ADD CONSTRAINT carga_cliente_id_fkey FOREIGN KEY (cliente_id) REFERENCES core.cliente(id) ON DELETE CASCADE;


--
-- Name: carga carga_encargo_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.carga
    ADD CONSTRAINT carga_encargo_id_fkey FOREIGN KEY (encargo_id) REFERENCES core.encargo(id) ON DELETE SET NULL;


--
-- Name: carga carga_perfil_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.carga
    ADD CONSTRAINT carga_perfil_id_fkey FOREIGN KEY (perfil_id) REFERENCES core.perfil_mapeo(id);


--
-- Name: carga carga_tipo_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.carga
    ADD CONSTRAINT carga_tipo_fkey FOREIGN KEY (tipo) REFERENCES core.insumo(tipo);


--
-- Name: cotejo cotejo_carga_nueva_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.cotejo
    ADD CONSTRAINT cotejo_carga_nueva_fkey FOREIGN KEY (carga_nueva) REFERENCES core.carga(id) ON DELETE CASCADE;


--
-- Name: cotejo cotejo_carga_previa_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.cotejo
    ADD CONSTRAINT cotejo_carga_previa_fkey FOREIGN KEY (carga_previa) REFERENCES core.carga(id) ON DELETE SET NULL;


--
-- Name: cotejo_detalle cotejo_detalle_cotejo_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.cotejo_detalle
    ADD CONSTRAINT cotejo_detalle_cotejo_id_fkey FOREIGN KEY (cotejo_id) REFERENCES core.cotejo(id) ON DELETE CASCADE;


--
-- Name: cotejo cotejo_encargo_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.cotejo
    ADD CONSTRAINT cotejo_encargo_id_fkey FOREIGN KEY (encargo_id) REFERENCES core.encargo(id) ON DELETE SET NULL;


--
-- Name: encargo encargo_cliente_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.encargo
    ADD CONSTRAINT encargo_cliente_id_fkey FOREIGN KEY (cliente_id) REFERENCES core.cliente(id) ON DELETE CASCADE;


--
-- Name: encargo encargo_fase_activa_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.encargo
    ADD CONSTRAINT encargo_fase_activa_fkey FOREIGN KEY (fase_activa) REFERENCES core.fase(fase);


--
-- Name: encargo_insumo encargo_insumo_carga_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.encargo_insumo
    ADD CONSTRAINT encargo_insumo_carga_id_fkey FOREIGN KEY (carga_id) REFERENCES core.carga(id) ON DELETE CASCADE;


--
-- Name: encargo_insumo encargo_insumo_encargo_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.encargo_insumo
    ADD CONSTRAINT encargo_insumo_encargo_id_fkey FOREIGN KEY (encargo_id) REFERENCES core.encargo(id) ON DELETE CASCADE;


--
-- Name: encargo_insumo encargo_insumo_tipo_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.encargo_insumo
    ADD CONSTRAINT encargo_insumo_tipo_fkey FOREIGN KEY (tipo) REFERENCES core.insumo(tipo);


--
-- Name: hallazgo hallazgo_carga_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.hallazgo
    ADD CONSTRAINT hallazgo_carga_id_fkey FOREIGN KEY (carga_id) REFERENCES core.carga(id) ON DELETE CASCADE;


--
-- Name: hallazgo hallazgo_encargo_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.hallazgo
    ADD CONSTRAINT hallazgo_encargo_id_fkey FOREIGN KEY (encargo_id) REFERENCES core.encargo(id) ON DELETE CASCADE;


--
-- Name: materialidad materialidad_encargo_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.materialidad
    ADD CONSTRAINT materialidad_encargo_id_fkey FOREIGN KEY (encargo_id) REFERENCES core.encargo(id) ON DELETE CASCADE;


--
-- Name: materialidad materialidad_fase_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.materialidad
    ADD CONSTRAINT materialidad_fase_fkey FOREIGN KEY (fase) REFERENCES core.fase(fase);


--
-- Name: materialidad_historia materialidad_historia_encargo_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.materialidad_historia
    ADD CONSTRAINT materialidad_historia_encargo_id_fkey FOREIGN KEY (encargo_id) REFERENCES core.encargo(id) ON DELETE CASCADE;


--
-- Name: nivel_cargable nivel_cargable_nivel_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.nivel_cargable
    ADD CONSTRAINT nivel_cargable_nivel_fkey FOREIGN KEY (nivel) REFERENCES core.puc_nivel(nivel);


--
-- Name: nota_alcance nota_alcance_encargo_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.nota_alcance
    ADD CONSTRAINT nota_alcance_encargo_id_fkey FOREIGN KEY (encargo_id) REFERENCES core.encargo(id) ON DELETE CASCADE;


--
-- Name: nota_alcance nota_alcance_fase_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.nota_alcance
    ADD CONSTRAINT nota_alcance_fase_fkey FOREIGN KEY (fase) REFERENCES core.fase(fase);


--
-- Name: perfil_mapeo perfil_mapeo_cliente_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.perfil_mapeo
    ADD CONSTRAINT perfil_mapeo_cliente_id_fkey FOREIGN KEY (cliente_id) REFERENCES core.cliente(id) ON DELETE CASCADE;


--
-- Name: perfil_mapeo perfil_mapeo_tipo_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.perfil_mapeo
    ADD CONSTRAINT perfil_mapeo_tipo_fkey FOREIGN KEY (tipo) REFERENCES core.insumo(tipo);


--
-- Name: puc puc_clase_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.puc
    ADD CONSTRAINT puc_clase_fkey FOREIGN KEY (clase) REFERENCES core.puc_clase(clase);


--
-- Name: puc puc_digitos_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.puc
    ADD CONSTRAINT puc_digitos_fkey FOREIGN KEY (digitos) REFERENCES core.puc_nivel(digitos);


--
-- Name: balance_staging balance_staging_carga_id_fkey; Type: FK CONSTRAINT; Schema: raw; Owner: -
--

ALTER TABLE ONLY raw.balance_staging
    ADD CONSTRAINT balance_staging_carga_id_fkey FOREIGN KEY (carga_id) REFERENCES core.carga(id) ON DELETE CASCADE;


--
-- Name: movimiento_staging movimiento_staging_carga_id_fkey; Type: FK CONSTRAINT; Schema: raw; Owner: -
--

ALTER TABLE ONLY raw.movimiento_staging
    ADD CONSTRAINT movimiento_staging_carga_id_fkey FOREIGN KEY (carga_id) REFERENCES core.carga(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict BQcDdPbTcPi2y5mqCBXwiTkPg9A2dBAqlDqh0WjyQekrgkYfpFVGEhZhlq9ZsUN

