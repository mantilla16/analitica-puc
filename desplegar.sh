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

modo=$(printf '%s' "$estado" | sed -n 's/.*"modo_correo":"\([^"]*\)".*/\1/p')
listo=$(printf '%s' "$estado" | sed -n 's/.*"correo_listo":\([a-z]*\).*/\1/p')

verde ""
verde "Desplegado: $(git log --oneline -1)"
verde "Correo: modo $modo, $([ "$listo" = true ] && echo "en orden" || echo "CON PROBLEMAS")"
[ "$listo" = true ] || rojo "Nadie podrá entrar hasta que el correo funcione."
