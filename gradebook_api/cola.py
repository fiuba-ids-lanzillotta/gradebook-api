"""
Publicación de mensajes en Upstash QStash hacia gradebook-mailer (worker de
emails serverless). El contrato de los endpoints está en `docs/swagger.yaml` del
repo del worker; el contexto y las decisiones en `docs/worker-asincrono-qrs.md`.

Env-gated: sin `QSTASH_TOKEN`/`MAIL_WORKER_URL` no se publica nada; `publicar`
loguea el mensaje que iría al worker (modo dev/tests) y `enviar_qrs` simula el
envío marcando las asistencias. Fail-open: ante un error de publish se loguea y
se retorna False — los QRs quedan pendientes (el front los reintenta) y los
transaccionales se pierden igual que un error de SMTP.

No usa el SDK de `qstash`: publicar es un POST HTTPS común (`requests`). El SDK
solo lo necesita el worker para verificar firmas.
"""
import json
import logging

import requests

from .config import QSTASH_URL, QSTASH_TOKEN, MAIL_WORKER_URL

logger = logging.getLogger(__name__)

_TIMEOUT_SEGUNDOS = 10


def cola_configurada() -> bool:
    """Indica si el envío asíncrono de emails está habilitado (QStash + worker)."""
    return bool(QSTASH_TOKEN and MAIL_WORKER_URL)


def publicar(path: str, body: dict) -> bool:
    """
    Publica un mensaje para `MAIL_WORKER_URL + path`. Retorna True si QStash lo
    aceptó; False si la cola no está configurada o el publish falló.
    """
    if not cola_configurada():
        logger.warning(f'[cola] Sin configurar (dev); email para {path}: {body}')
        
        return False

    try:
        respuesta = requests.post(
            f'{QSTASH_URL}/v2/publish/{MAIL_WORKER_URL}{path}',
            json=body,
            headers=_headers(),
            timeout=_TIMEOUT_SEGUNDOS,
        )
    except Exception as error:
        logger.error(f'[cola] No se pudo publicar {path}: {error}')
        
        return False

    return _verificar_respuesta(respuesta, path)


def publicar_lote(path: str, cuerpos: list[dict], delay_segundos: int = 0) -> bool:
    """
    Publica varios mensajes al mismo path del worker en una sola llamada
    (`/v2/batch`). Retorna True si QStash aceptó el lote completo.

    Con `delay_segundos` > 0 cada mensaje sale con `Upstash-Delay` creciente
    (0s, Ns, 2Ns, ...): QStash entrega de a un lote por vez en lugar de todo
    el batch en paralelo.
    """
    if not cuerpos:
        return False

    if not cola_configurada():
        logger.warning(f'[cola] Sin configurar (dev); {len(cuerpos)} mensajes para {path}')
        
        return False

    mensajes = [
        {
            'destination': f'{MAIL_WORKER_URL}{path}',
            'body':        json.dumps(cuerpo),
            'headers':     _headers_mensaje(indice * delay_segundos),
        }
        for indice, cuerpo in enumerate(cuerpos)
    ]

    try:
        respuesta = requests.post(
            f'{QSTASH_URL}/v2/batch',
            json=mensajes,
            headers=_headers(),
            timeout=_TIMEOUT_SEGUNDOS,
        )
    except Exception as error:
        logger.error(f'[cola] No se pudo publicar el lote a {path}: {error}')
        
        return False

    return _verificar_respuesta(respuesta, path)


def _headers() -> dict:
    return {'Authorization': f'Bearer {QSTASH_TOKEN}'}


def _headers_mensaje(delay_segundos: int) -> dict:
    """Headers por mensaje del batch: JSON siempre, Upstash-Delay solo si > 0."""
    headers = {'Content-Type': 'application/json'}

    if delay_segundos > 0:
        headers['Upstash-Delay'] = f'{delay_segundos}s'

    return headers


def _verificar_respuesta(respuesta, path: str) -> bool:
    if respuesta.ok:
        return True

    logger.error(f'[cola] QStash rechazó {path}: HTTP {respuesta.status_code} {respuesta.text[:200]}')
    
    return False
