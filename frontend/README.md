# Frontend — Analítica PUC

React + Vite + Tailwind 4.

## Arranque

```
cd frontend
npm install
npm run dev
```

Abre http://localhost:5173

El backend debe estar corriendo en el puerto 8000. Vite hace proxy de
`/api` hacia `http://localhost:8000`, así que no hay problema de CORS.

Para apuntar a otra dirección, crea un `.env`:

```
VITE_API=http://otro-servidor:8000
```

## Flujo

1. **Encargos** — lista y creación. Solo se pide la fecha de corte:
   los dos periodos comparativos se derivan de ella.
2. **Encargo** — checklist de los cinco archivos. Cada uno se sube desde
   su fila. Los periodos se calculan solos según el tipo de insumo.
3. **Mapeo** — aparece solo la primera vez que se carga ese tipo de
   archivo para ese cliente. Lo que el sistema reconoce viene
   preseleccionado y marcado como "auto".
4. **Resultado** — cuadre por nivel, y si el archivo trae cambios
   respecto a una carga anterior, la tabla de evidencia.

## Diseño

La paleta viene del punteo del auditor: lápiz verde para lo verificado,
rojo para la excepción, ámbar para lo que hay que revisar. Todas las
cifras y códigos van en IBM Plex Mono con cifras tabulares para que las
columnas de saldos se alineen como en un balance.

El elemento central es la tira de cuadre: cada nivel completo debe sumar
cero por sí solo, y cuando lo hace aparece el punteo.
