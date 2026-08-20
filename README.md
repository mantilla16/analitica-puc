# Analítica de balances y movimientos PUC

Herramienta interna de Russell Bedford para analizar balances y movimientos
contables de clientes de auditoría en Colombia. Sustituye un trabajo manual
en Excel por un pipeline que carga, valida, compara y deja evidencia.

```
Excel  →  raw.*_staging  →  cotejo  →  core.balance  →  análisis (+ IA)
         (todo texto)      (recargas)   (validado)      (variaciones)
```

## Stack

- **Backend**: Python + FastAPI + psycopg 3, en la raíz del repo.
- **Base de datos**: PostgreSQL 18. Solo tablas, llaves foráneas e índices —
  cero funciones, vistas o triggers. Toda la lógica de negocio vive en
  Python (ver [`db/ESQUEMA.md`](db/ESQUEMA.md)).
- **Frontend**: React + Vite + Tailwind 4, en [`frontend/`](frontend/).
- **IA**: [Ollama](https://ollama.com) corriendo un modelo abierto en local
  (`qwen3:8b` por defecto), para redactar observaciones sobre las
  variaciones ya calculadas. El modelo no calcula nada — solo redacta
  sobre cifras que Python ya calculó, y cada cifra que menciona se verifica
  contra la entrada antes de mostrarse.

## Estructura del repo

```
main.py           Rutas HTTP (FastAPI) -- solo orquesta, no calcula
servicios.py       Orquestación: encargo, mapeo, procesar, cotejar, promover
analisis.py        Explorador del balance, variaciones, observaciones de IA
reglas.py          Fechas, materialidad, signo por herencia, cotejo, cuadres
excel.py           Inspección y parseo de archivos .xlsx
db.py              SQL plano contra las tablas (sin lógica de negocio)
ia.py              Prompt + llamada a Ollama + verificación de cifras
frontend/          React + Vite + Tailwind
db/                schema.sql (estructura completa) y ESQUEMA.md (qué es cada tabla)
*.sql (raíz)        Migraciones incrementales aplicadas sobre schema.sql
```

`reglas.py`, `excel.py` e `ia.py` no tocan la base de datos: se pueden
probar sin levantar Postgres.

## Puesta en marcha

### 1. Base de datos

Crea la base y corre el esquema completo -- ya incluye todo, no hace
falta nada más encima:

```bash
createdb -h localhost -U postgres auditoria_puc
psql -h localhost -U postgres -d auditoria_puc -v ON_ERROR_STOP=1 -f db/schema.sql
```

Los archivos `NN_descripcion.sql` sueltos en la raíz (como
`08_materialidad.sql`) son el historial de migraciones que ya está
incorporado en `db/schema.sql` -- quedan como registro, no se vuelven a
correr sobre una base nueva. Si en el futuro aparece una migración con un
número más alto que no esté todavía en `db/schema.sql`, esa sí hay que
aplicarla aparte y luego regenerar el dump.

### 2. Backend

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

set AUDITORIA_DSN=postgresql://postgres:TU_PASSWORD@localhost:5432/auditoria_puc
.venv\Scripts\uvicorn.exe main:app --reload --port 8000
```

`AUDITORIA_DSN` es la única variable obligatoria. Sin ella, `db.py` usa por
defecto `postgresql://postgres:postgres@localhost:5432/auditoria_puc` —
sirve para desarrollo local si esa es tu contraseña, pero en cualquier otro
entorno hay que fijarla explícitamente.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Vite hace proxy de `/api` hacia `http://localhost:8000`.

### 4. IA (opcional, pero la pestaña Variaciones la usa automáticamente)

```bash
ollama pull qwen3:8b
ollama serve
```

Variables opcionales (por defecto apuntan a una instancia local de Ollama):

| Variable | Default | Qué es |
|---|---|---|
| `OLLAMA_URL` | `http://localhost:11434` | Dónde corre el servidor de Ollama |
| `OLLAMA_MODELO` | `qwen3:8b` | Modelo a usar para redactar observaciones |

Si Ollama no está corriendo, la pestaña Variaciones sigue funcionando
normal — cada observación simplemente muestra un aviso de que no se pudo
generar, en vez de romper el resto de la página.

## Qué NO va en este repo

- `archivos/` -- los Excel que suben los clientes quedan ahí en disco, pero
  son datos confidenciales de auditoría y están en `.gitignore`.
- `.venv/`, `frontend/node_modules/` -- se regeneran con los comandos de
  arriba.
- Contraseñas reales de ningún tipo. `AUDITORIA_DSN` siempre se fija por
  variable de entorno, nunca hardcodeada.
