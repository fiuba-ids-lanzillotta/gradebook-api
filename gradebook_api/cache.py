"""
Cache-aside con Upstash Redis (REST), con invalidación explícita.

Se activa solo si hay credenciales de Upstash; si no, queda deshabilitado. Es
fail-open: ante error de Redis, un `obtener` devuelve None (miss → se recalcula)
y `guardar`/`invalidar` son best-effort (no interrumpen el request).

Se cachea solo data serializable y liviana (JSON).
"""
import json
import logging

from .config import (
    UPSTASH_REDIS_REST_URL,
    UPSTASH_REDIS_REST_TOKEN,
)

logger = logging.getLogger(__name__)

_PREFIJO = 'gradebook-api:cache:'
_cliente = None
_inicializado = False


def _obtener_cliente():
    """Crea (una sola vez) el cliente de Upstash, o None si no está configurado."""
    global _cliente, _inicializado

    if _inicializado:
        return _cliente

    _inicializado = True

    if UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN:
        from upstash_redis import Redis
        _cliente = Redis(url=UPSTASH_REDIS_REST_URL, token=UPSTASH_REDIS_REST_TOKEN, rest_retries=0)

    return _cliente


def obtener(clave: str):
    """Retorna el valor cacheado (deserializado) o None (miss / deshabilitado / error)."""
    cliente = _obtener_cliente()

    if cliente is None:
        return None

    try:
        crudo = cliente.get(_PREFIJO + clave)

        return json.loads(crudo) if crudo else None
    except Exception as error:
        logger.error(f'Cache obtener falló (fail-open): {error}')

        return None


def guardar(clave: str, valor, ttl: int) -> None:
    """Guarda un valor serializable en la cache con el TTL dado (best-effort)."""
    cliente = _obtener_cliente()

    if cliente is None:
        return

    try:
        cliente.set(_PREFIJO + clave, json.dumps(valor), ex=ttl)
    except Exception as error:
        logger.error(f'Cache guardar falló: {error}')


def invalidar(*claves: str) -> None:
    """Borra una o más claves de la cache (best-effort). Se usa tras cada escritura."""
    cliente = _obtener_cliente()

    if cliente is None or not claves:
        return

    try:
        cliente.delete(*[_PREFIJO + clave for clave in claves])
    except Exception as error:
        logger.error(f'Cache invalidar falló: {error}')


def adquirir_lock(clave: str, ttl: int) -> bool:
    """
    Intenta tomar un lock (SET NX EX). Retorna True si lo tomó. Fail-open: si no
    hay Redis o falla, retorna True (no bloquea el flujo, sólo se pierde la
    exclusión mutua).
    """
    cliente = _obtener_cliente()

    if cliente is None:
        return True

    try:
        return bool(cliente.set(_PREFIJO + 'lock:' + clave, '1', nx=True, ex=ttl))
    except Exception as error:
        logger.error(f'Cache adquirir_lock falló (fail-open): {error}')

        return True


def liberar_lock(clave: str) -> None:
    """Libera un lock tomado con `adquirir_lock` (best-effort)."""
    cliente = _obtener_cliente()

    if cliente is None:
        return

    try:
        cliente.delete(_PREFIJO + 'lock:' + clave)
    except Exception as error:
        logger.error(f'Cache liberar_lock falló: {error}')
