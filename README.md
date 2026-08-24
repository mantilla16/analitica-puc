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

`08_materialidad.sql` (raíz) ya está incorporado en `db/schema.sql` --
queda como registro histórico, no se vuelve a correr.

**`10_observacion_ia.sql` todavía NO está en el dump** y hay que aplicarlo
después, tanto en una base nueva como en una existente:

```bash
psql -h localhost -U postgres -d auditoria_puc -v ON_ERROR_STOP=1 -f 10_observacion_ia.sql
```

Cuando se regenere `db/schema.sql` con un `pg_dump` nuevo, esa migración
queda absorbida y este paso deja de ser necesario.

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

Dos proveedores, elegidos por `IA_PROVEEDOR`:

| Variable | Default | Qué es |
|---|---|---|
| `IA_PROVEEDOR` | `ollama` | `ollama` \| `azure_foundry` |
| `IA_TIMEOUT` | `60` | Segundos de espera por observación |
| `IA_LOTE` | `5` | Cuántas observaciones se piden por petición |
| `IA_AUTO` | `1` | Si al abrir Variaciones se generan solas las que faltan (`0` = solo a pedido) |
| `OLLAMA_URL` | `http://localhost:11434` | Dónde corre Ollama |
| `OLLAMA_MODELO` | `qwen3:8b` | Modelo local |
| `AZURE_AI_ENDPOINT` | — | `https://<recurso>.services.ai.azure.com/openai/v1` (sin `/chat/completions`) |
| `AZURE_AI_DEPLOYMENT` | — | Nombre del despliegue en Foundry |
| `AZURE_AI_API_KEY` | — | Clave del recurso de Foundry |

**`IA_TIMEOUT` e `IA_LOTE` dependen del hardware, no del código.** El
frontend consulta `GET /ia/config` y usa el `lote` que diga el servidor:
contra un endpoint en la nube, 5 en paralelo van bien; contra un Ollama
en CPU, esas 5 se pelean los mismos núcleos y conviene bajar el lote y
subir el timeout.

Si el proveedor no responde, la pestaña Variaciones sigue funcionando —
cada observación muestra un aviso y un botón "Reintentar", en vez de
romper el resto de la página.

### Los dos servidores en uso

| | **oficina** (local, sin GPU) | **azure** (VM en la nube) |
|---|---|---|
| IA | Ollama en Docker, CPU | Azure AI Foundry, serverless |
| `IA_PROVEEDOR` | `ollama` | `azure_foundry` |
| `OLLAMA_MODELO` | `qwen3:4b` (los 8b no caben con 7 GiB de RAM) | — |
| `IA_LOTE` | `1` | `5` |
| `IA_TIMEOUT` | `600` | `60` |
| `IA_AUTO` | `0` (a pedido) | `1` (automático) |
| Acceso público | Tailscale Funnel (`*.ts.net`) | DNS de Azure (`*.cloudapp.azure.com`) |

Ambos corren el mismo código y el mismo esquema; lo único que cambia son
esas variables de entorno en el `systemd`. **oficina existe como respaldo
del avance de la capa de IA**: los créditos de Azure se agotan y el
análisis guardado no puede depender de una sola máquina.

## Despliegue en un servidor Linux (producción)

Pensado para un servidor Ubuntu/Debian sin GPU: Postgres, backend y
Ollama (CPU) en la misma máquina, nginx al frente sirviendo el frontend
y haciendo de proxy hacia el backend.

```bash
# Paquetes del sistema
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git nginx nodejs npm postgresql

# Base de datos
sudo -u postgres createdb auditoria_puc
sudo -u postgres psql -d auditoria_puc -v ON_ERROR_STOP=1 -f db/schema.sql

# Backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Frontend -- genera frontend/dist
cd frontend && npm install && npm run build && cd ..
sudo mkdir -p /var/www/analitica-puc
sudo cp -r frontend/dist/* /var/www/analitica-puc/

# nginx
sudo cp deploy/analitica-puc.nginx /etc/nginx/sites-available/analitica-puc
sudo ln -s /etc/nginx/sites-available/analitica-puc /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

# Ollama (si corre en este mismo servidor)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3:8b
```

El backend se deja corriendo con `systemd` (no directamente con
`uvicorn --reload`, eso es solo para desarrollo):

```ini
# /etc/systemd/system/analitica-puc.service
[Unit]
Description=Analitica PUC - FastAPI
After=network.target postgresql.service

[Service]
User=TU_USUARIO
WorkingDirectory=/home/TU_USUARIO/analitica-puc
Environment="AUDITORIA_DSN=postgresql://postgres:TU_PASSWORD@localhost:5432/auditoria_puc"
ExecStart=/home/TU_USUARIO/analitica-puc/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now analitica-puc
journalctl -u analitica-puc -f   # logs en vivo
```

El navegador solo habla con nginx (puerto 80) -- ni el frontend ni nadie
de afuera necesita saber que el backend está en el puerto 8000. Por eso
mismo, la lista `allow_origins` de CORS en `main.py` (pensada para
`localhost:5173`/`3000` en desarrollo) deja de importar en este montaje:
todo llega al navegador bajo el mismo origen.

**Pendiente, no incluido aquí:** HTTPS. Sin un dominio apuntando a este
servidor no tiene sentido armarlo todavía -- cuando lo haya, es un
`certbot --nginx` y listo.

## Qué NO va en este repo

- `archivos/` -- los Excel que suben los clientes quedan ahí en disco, pero
  son datos confidenciales de auditoría y están en `.gitignore`.
- `.venv/`, `frontend/node_modules/` -- se regeneran con los comandos de
  arriba.
- Contraseñas reales de ningún tipo. `AUDITORIA_DSN` siempre se fija por
  variable de entorno, nunca hardcodeada.
