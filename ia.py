"""
Capa de IA para redactar observaciones sobre variaciones ya calculadas.

Regla dura: el modelo no calcula. Recibe los agregados que ya salieron de
analisis.py (variación, motivo, patrones de movimiento) y solo redacta.
Toda cifra que aparezca en el texto debe existir literal en la entrada —
se verifica después de generar, no se confía en el modelo.

Dos proveedores posibles, elegidos por IA_PROVEEDOR:
  - "ollama" (default) -- modelo abierto corriendo local, para desarrollo.
  - "azure_foundry" -- despliegue serverless en Azure AI Foundry, para un
    servidor sin suficiente CPU/GPU propia.
No toca la base ni sabe qué es un encargo: recibe un dict, devuelve un dict.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
from decimal import Decimal
from typing import Any

IA_PROVEEDOR = os.getenv("IA_PROVEEDOR", "ollama")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODELO = os.getenv("OLLAMA_MODELO", "qwen3:8b")

AZURE_AI_ENDPOINT = os.getenv("AZURE_AI_ENDPOINT")
AZURE_AI_DEPLOYMENT = os.getenv("AZURE_AI_DEPLOYMENT")
AZURE_AI_API_KEY = os.getenv("AZURE_AI_API_KEY")

PROMPT_SISTEMA = (
    "Eres un asistente de auditoría. Se te dan cifras YA CALCULADAS sobre "
    "una cuenta contable, en un JSON. Tu única tarea es redactar una "
    "observación de 3 a 6 frases explicando por qué esa cuenta varió, "
    "apoyándote en 'patrones_de_movimiento' (qué descripciones de "
    "movimiento explican el cambio) y en 'composicion_auxiliar' (en qué "
    "auxiliares concretos -- subcuentas de 8 dígitos -- está concentrada "
    "la variación).\n\n"
    "Reglas estrictas:\n"
    "- No calcules nada. No inventes ninguna cifra que no esté en el JSON.\n"
    "- Toda cifra que menciones debe copiarse literal del JSON de entrada.\n"
    "- La PRIMERA vez que nombres la cuenta, cita su código junto al "
    "  nombre -- ej. 'la cuenta 2105 (Bancos nacionales)' y no solo "
    "  'Bancos nacionales' -- porque el PUC colombiano repite nombres "
    "  parecidos entre cuentas de activo y de pasivo que no tienen "
    "  relación (ej. 1110 Bancos, en el activo, contra 2105 Bancos "
    "  Nacionales, en el pasivo). Lo mismo al citar cualquier auxiliar: "
    "  siempre con su código.\n"
    "- No te quedes con un solo auxiliar si 'composicion_auxiliar' trae "
    "  más de uno con variación relevante: repasa la lista completa y "
    "  menciona los principales contribuyentes -- no solo el más grande. "
    "  Cada auxiliar ya trae su 'pct_de_la_variacion_total' calculado -- "
    "  cópialo tal cual, no lo calcules tú.\n"
    "- Si ni los patrones de movimiento ni la composición por auxiliar "
    "  explican bien la variación, dilo explícitamente en vez de inventar "
    "  una causa.\n"
    "- Responde en español, en prosa corrida, sin viñetas ni markdown."
)


def _prompt(entrada: dict) -> str:
    return (
        f"{PROMPT_SISTEMA}\n\n"
        f"JSON de entrada:\n{json.dumps(entrada, ensure_ascii=False, default=str)}\n\n"
        f"Observación:"
    )


def redactar_observacion(entrada: dict, timeout: int = 60) -> dict:
    """Llama al modelo (Ollama o Azure AI Foundry, según IA_PROVEEDOR) y
    verifica las cifras del texto contra la entrada.

    Nunca lanza por errores del modelo/red: si no responde, devuelve un
    texto de aviso en vez de tumbar el flujo de variaciones.
    """
    try:
        prompt = _prompt(entrada)
        if IA_PROVEEDOR == "azure_foundry":
            texto = _generar_foundry(prompt, timeout)
        else:
            texto = _generar_ollama(prompt, timeout)
    except Exception as exc:
        return {"texto": f"No se pudo generar la observación: {exc}",
                "verificado": False, "cifras_no_verificadas": [], "error": True}

    faltantes = _cifras_no_verificadas(texto, entrada)
    return {"texto": texto.strip(), "verificado": not faltantes,
            "cifras_no_verificadas": faltantes, "error": False}


def _quitar_pensamiento(texto: str) -> str:
    """Por si el modelo (Qwen, Phi-4-reasoning) filtra su razonamiento
    interno al texto en vez de mantenerlo aparte -- no debe llegar ni a
    la observación final ni a la verificación de cifras."""
    return re.sub(r"<think>.*?</think>", "", texto, flags=re.S).strip()


def _generar_foundry(prompt: str, timeout: int) -> str:
    from openai import OpenAI   # importado aquí: no todos los entornos lo instalan

    if not (AZURE_AI_ENDPOINT and AZURE_AI_DEPLOYMENT and AZURE_AI_API_KEY):
        raise RuntimeError(
            "Faltan AZURE_AI_ENDPOINT / AZURE_AI_DEPLOYMENT / AZURE_AI_API_KEY"
        )

    client = OpenAI(base_url=AZURE_AI_ENDPOINT, api_key=AZURE_AI_API_KEY,
                    timeout=timeout)
    r = client.chat.completions.create(
        model=AZURE_AI_DEPLOYMENT,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return _quitar_pensamiento(r.choices[0].message.content)


def _generar_ollama(prompt: str, timeout: int) -> str:
    payload = json.dumps({
        "model": MODELO, "prompt": prompt + " /no_think", "stream": False,
        "think": False,   # ignorado sin daño por modelos que no soportan pensar
        "options": {"temperature": 0.2},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/generate", data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        texto = json.loads(r.read())["response"]
    return _quitar_pensamiento(texto)


# --------------------------------------------------------------- verificación

_NUMERO = re.compile(r"-?\d[\d.,]*\d|\d")


def _valores_planos(v: Any) -> list[str]:
    """Todos los valores numéricos/texto de la entrada, aplanados."""
    if isinstance(v, dict):
        return [x for val in v.values() for x in _valores_planos(val)]
    if isinstance(v, (list, tuple)):
        return [x for item in v for x in _valores_planos(item)]
    if isinstance(v, (int, float, Decimal)):
        return [str(v)]
    if isinstance(v, str):
        return [v]
    return []


def _normalizar(num: str) -> Decimal | None:
    """'1.314.075.851,50' o '1314075851.50' -> Decimal('1314075851.50').

    Compara por VALOR, no por texto: '502000000.0' (viene de un float de
    Python) y '502.000.000,00' (formato colombiano en la respuesta del
    modelo) deben verificarse como la misma cifra, y comparar strings
    quedaría corto por los ceros de más o de menos.
    """
    limpio = num.strip().rstrip(".,")
    if not limpio:
        return None
    if "," in limpio and limpio.count(",") == 1 and re.search(r",\d{1,2}$", limpio):
        limpio = limpio.replace(".", "").replace(",", ".")
    else:
        limpio = limpio.replace(",", "")
    try:
        return Decimal(limpio)
    except Exception:
        return None


def _cifras_no_verificadas(texto: str, entrada: dict) -> list[str]:
    """Números del texto generado (2+ dígitos, para no marcar '1 cuenta',
    'el 2do', etc.) cuyo VALOR no aparece en ningún valor de la entrada
    (en positivo o negativo, porque el modelo puede describir una caída
    con la cifra en positivo). Es una verificación heurística, no una
    prueba matemática."""
    disponibles = set()
    for v in _valores_planos(entrada):
        for m in _NUMERO.findall(str(v)):
            n = _normalizar(m)
            if n is not None:
                disponibles.add(n)
                disponibles.add(abs(n))

    sospechosas = []
    for m in _NUMERO.findall(texto):
        digitos = re.sub(r"[.,]", "", m)
        if len(digitos) < 2:
            continue
        n = _normalizar(m)
        if n is not None and n not in disponibles and abs(n) not in disponibles:
            sospechosas.append(m)
    return sospechosas
