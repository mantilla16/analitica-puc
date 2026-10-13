#!/usr/bin/env bash
#
# Despliegue de Analítica PUC en el servidor.
#
#     ./desplegar.sh
#
# Existe porque los tres tropiezos de la semana del 21-sep-2026 fueron de
# despliegue y ninguno de código: nginx apuntando a otro puerto, el build
# que se hacía pero no se publicaba, y un arreglo editado en el servidor que
# el pull iba a sobrescribir. Un procedimiento que vive en la cabeza de
# alguien se olvida; uno que está aquí, no.
#
# Lo importante no es que ejecute los pasos, sino que COMPRUEBE el final: si
# la aplicación no responde, se entera el que despliega y no el auditor tres
# días después.
set -euo pipefail

cd "$(dirname "$0")"

SERVICIO=analitica-puc
HOST=${ANALITICA_HOST:-rbbaq.taildce0dd.ts.net}
ESPERA=30

rojo()  { printf '\033[31m%s\033[0m\n' "$*"; }
verde() { printf '\033[32m%s\033[0m\n' "$*"; }
paso()  { printf '\n\033[1m==> %s\033[0m\n' "$*"; }

# --------------------------------------------------------------- 1. código
paso "Cambios sin guardar"
# `core.fileMode=false` ignora el bit de ejecución: un `chmod +x` no es un
# cambio de código y bloquear el despliegue por eso es ruido que enseña a
# saltarse la comprobación -- justo lo contrario de para lo que está.
GIT="git -c core.fileMode=false"
if ! $GIT diff --quiet || ! $GIT diff --cached --quiet; then
    rojo "Hay cambios locales sin commitear:"
    $GIT status --short
    rojo ""
    rojo "Editar en el servidor deja arreglos que nadie más puede ver y que"
    rojo "el próximo pull borra. Cómetelos y súbelos, o descártalos a"
    rojo "conciencia, antes de desplegar."
    exit 1
fi

paso "Trayendo el código"
git pull --ff-only

# ------------------------------------------------------------- 2. pruebas
paso "Pruebas que no necesitan la base"
if [ -x .venv/bin/python ]; then
    .venv/bin/python validar_excel.py
else
    rojo "No encuentro .venv/bin/python; me salto las pruebas."
fi

# ------------------------------------------------- 3. dependencias Python
# Si `requirements.txt` cambio (una libreria nueva, una version fija), sin
# esto el servicio arranca importando lo viejo y muere con ImportError. Ya
# nos paso una vez con pyjwt; que no vuelva a pasar.
paso "Dependencias Python"
if [ -x .venv/bin/pip ]; then
    .venv/bin/pip install --quiet --disable-pip-version-check -r requirements.txt
else
    rojo "No encuentro .venv/bin/pip; me salto la instalacion de Python."
fi

# ----------------------------------------------------- 3.5 migraciones SQL
# Aplica cualquier NN_*.sql del repo que no se haya aplicado todavia. Antes
# habia que acordarse de correrla a mano, y una migracion sin aplicar deja
# el codigo nuevo pegado contra una tabla vieja: el usuario carga su balance
# y la app sigue respondiendo con la logica anterior. Pasa poco pero cuando
# pasa es dificil de diagnosticar porque todo "parece" al dia.
#
# La tabla core.migracion registra lo ya aplicado por nombre de archivo.
# Los sql son idempotentes (IF NOT EXISTS, ON CONFLICT) por si acaso, pero
# el objetivo aqui es NO volver a correrlos.
paso "Migraciones SQL pendientes"
# El archivo .env es root:600 y el runner no puede sudo bash -c (no esta en
# sudoers con eso). systemctl show si lee la propiedad Environment del
# servicio y es equivalente: refleja lo que el proceso tiene cargado.
DSN=$(systemctl show "$SERVICIO" --property=Environment --value 2>/dev/null \
      | tr ' ' '\n' | sed -n 's/^AUDITORIA_DSN=//p' | head -1)
if [ -z "$DSN" ]; then
    rojo "No pude leer AUDITORIA_DSN del servicio; me salto migraciones."
    rojo "  prueba: systemctl show $SERVICIO --property=Environment"
else
    psql_aqui() { PGCLIENTENCODING=UTF8 psql "$DSN" -v ON_ERROR_STOP=1 "$@"; }
    # El cerrojo de "primera corrida": si la tabla no existia, se SIEMBRAN
    # como ya aplicadas todas las migraciones hasta el numero 15 (que ya
    # estaban en el servidor antes de que esto existiera). Sin esto, el
    # primer deploy intentaria correr 01 al 15 contra una base que ya las
    # tiene y fallaria -- no todas son idempotentes.
    existia=$(psql_aqui -tAc "SELECT 1 FROM information_schema.tables
                              WHERE table_schema='core' AND table_name='migracion'")
    psql_aqui -tAc "CREATE TABLE IF NOT EXISTS core.migracion (
                      archivo text PRIMARY KEY,
                      aplicada_en timestamptz NOT NULL DEFAULT now())" >/dev/null
    if [ "$existia" != "1" ]; then
        for f in $(ls [0-9][0-9]_*.sql 2>/dev/null | sort); do
            nn="${f%%_*}"
            if [ "$nn" -le 15 ] 2>/dev/null; then
                psql_aqui -c "INSERT INTO core.migracion(archivo) VALUES('$f')
                              ON CONFLICT DO NOTHING" >/dev/null
            fi
        done
        verde "  (primera vez: 01-15 sembradas como aplicadas)"
    fi
    for f in $(ls [0-9][0-9]_*.sql 2>/dev/null | sort); do
        ya=$(psql_aqui -tAc "SELECT 1 FROM core.migracion WHERE archivo='$f'")
        if [ "$ya" = "1" ]; then
            continue
        fi
        printf '  %s ... ' "$f"
        if psql_aqui -f "$f" >/dev/null 2>&1; then
            psql_aqui -c "INSERT INTO core.migracion(archivo) VALUES('$f')" >/dev/null
            verde "aplicada"
        else
            rojo "FALLO"
            rojo "  revisa: PGCLIENTENCODING=UTF8 psql \"\$AUDITORIA_DSN\" -v ON_ERROR_STOP=1 -f $f"
            exit 1
        fi
    done
fi

# ------------------------------------------------------------ 4. frontend
paso "Construyendo el frontend"
( cd frontend && npm ci --silent && npm run build )

# nginx sirve desde frontend/dist directamente. Si algún día vuelve a
# servir desde /var/www, este es el sitio donde hay que copiar -- y el
# motivo por el que un despliegue puede quedar a medias sin avisar.
RAIZ=$(sudo nginx -T 2>/dev/null | awk '/^\s*root /{print $2}' | tr -d ';' | head -1)
if [ -n "$RAIZ" ] && [ "$RAIZ" != "$PWD/frontend/dist" ]; then
    rojo "OJO: nginx sirve desde $RAIZ, no desde $PWD/frontend/dist"
    rojo "El build se hizo pero nadie lo va a publicar. Revísalo."
fi

# ------------------------------------------------------------ 4. servicio
paso "Reiniciando el servicio"
sudo systemctl restart "$SERVICIO"

# --------------------------------------------------------- 5. comprobación
paso "Esperando a que responda"
# `systemctl restart` vuelve en cuanto lanza el proceso, no cuando la
# aplicación está lista. Preguntar antes da un 502 que parece un fallo y
# solo es prisa.
for i in $(seq "$ESPERA"); do
    codigo=$(curl -s -o /dev/null -w '%{http_code}' \
             -H "Host: $HOST" http://127.0.0.1/api/auth/estado || true)
    [ "$codigo" = "200" ] && break
    sleep 1
done

if [ "$codigo" != "200" ]; then
    rojo "NO LEVANTÓ: /api/auth/estado devolvió $codigo tras ${ESPERA}s"
    rojo ""
    rojo "  404 -> nginx manda /api/ a otra aplicación"
    rojo "  502 -> el servicio no arrancó: sudo journalctl -u $SERVICIO -n 40"
    exit 1
fi

# Que responda no basta: tiene que responder ESTA aplicación. Un 200 de la
# aplicación equivocada se ve idéntico.
estado=$(curl -s -H "Host: $HOST" http://127.0.0.1/api/auth/estado)
case "$estado" in
    *dominio*) : ;;
    *) rojo "Responde algo en /api/, pero no es Analítica PUC:"
       rojo "  $estado"
       exit 1 ;;
esac

ms_cliente=$(printf '%s' "$estado" | sed -n 's/.*"msClientId":"\([^"]*\)".*/\1/p')
ms_tenant=$(printf '%s' "$estado" | sed -n 's/.*"msTenantId":"\([^"]*\)".*/\1/p')

verde ""
verde "Desplegado: $(git log --oneline -1)"
if [ -n "$ms_cliente" ] && [ -n "$ms_tenant" ]; then
    verde "Ingreso con Microsoft: configurado"
else
    rojo "Ingreso con Microsoft: FALTAN credenciales"
    rojo "  revisa AUDITORIA_MS_CLIENTE y AUDITORIA_MS_TENANT en /etc/analitica-puc.env"
fi
