"""
Rate limiting con Upstash Redis (REST), por IP.

Se activa solo si hay credenciales de Upstash (`UPSTASH_REDIS_REST_URL` /
`UPSTASH_REDIS_REST_TOKEN`); si no, queda deshabilitado. Es **fail-open**: si el
rate limiting no está configurado o Redis falla, se permite el request para no
tirar abajo el servicio (degradación, no error).
"""
import logging

from .config import (
    UPSTASH_REDIS_REST_URL,
    UPSTASH_REDIS_REST_TOKEN,
    RATE_LIMIT_MAXIMO,
    RATE_LIMIT_VENTANA_SEGUNDOS,
)

logger = logging.getLogger(__name__)

_limiter = None


def _obtener_limiter():
    """Crea (una sola vez) el rate limiter de Upstash, o None si no está configurado."""
    global _limiter

    if _limiter is not None:
        return _limiter

    if not (UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN):
        return None

    # Import perezoso: solo se necesita cuando el rate limiting está activo.
    from upstash_ratelimit import Ratelimit, FixedWindow
    from upstash_redis import Redis

    # rest_retries=0 para fallar rápido (evita esperar reintentos ante Redis caído).
    redis = Redis(url=UPSTASH_REDIS_REST_URL, token=UPSTASH_REDIS_REST_TOKEN, rest_retries=0)

    _limiter = Ratelimit(
        redis=redis,
        limiter=FixedWindow(max_requests=RATE_LIMIT_MAXIMO, window=RATE_LIMIT_VENTANA_SEGUNDOS),
        prefix='gradebook-api',
    )

    return _limiter


def esta_permitido(identificador: str) -> bool:
    """
    Indica si el request está dentro del límite para `identificador` (p. ej. la IP).

    Fail-open: retorna True si el rate limiting está deshabilitado o si Redis
    falla, para no interrumpir el servicio por un problema del limiter.
    """
    limiter = _obtener_limiter()

    if limiter is None:
        return True

    try:
        return limiter.limit(identificador).allowed
    except Exception as error:
        logger.error(f'Rate limit no disponible (fail-open): {error}')

        return True
