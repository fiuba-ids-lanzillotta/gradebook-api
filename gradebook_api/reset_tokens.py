"""
Almacén de tokens de recuperación de contraseña en Upstash Redis (REST).

El token viaja al usuario por email; en Redis se guarda sólo su `sha256` (nunca
el token en claro) mapeado a `{tipo, id}`, con TTL. El consumo es de **un solo
uso** (get-and-delete). A diferencia de la cache, esta funcionalidad **requiere**
Redis: sin credenciales de Upstash, no hay dónde guardar el token.
"""
import hashlib
import json
import logging

from .config import (
    UPSTASH_REDIS_REST_URL,
    UPSTASH_REDIS_REST_TOKEN,
)

logger = logging.getLogger(__name__)

_PREFIJO = 'gradebook-api:pwreset:'
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


def _clave(token: str) -> str:
    return _PREFIJO + hashlib.sha256(token.encode('utf-8')).hexdigest()


def guardar_token(token: str, tipo: str, persona_id: int, ttl: int) -> bool:
    """
    Guarda el token de recuperación (por su hash) con TTL. Retorna True si se
    guardó; False si Redis no está configurado o falló.
    """
    cliente = _obtener_cliente()

    if cliente is None:
        logger.error('password-reset: Redis no configurado; no se puede emitir el token')

        return False

    try:
        cliente.set(_clave(token), json.dumps({'tipo': tipo, 'id': persona_id}), ex=ttl)

        return True
    except Exception as error:
        logger.error(f'password-reset guardar_token falló: {error}')

        return False


def consumir_token(token: str) -> dict:
    """
    Retorna `{tipo, id}` y borra el token (un solo uso), o `{}` si no existe,
    expiró o Redis no está disponible.
    """
    cliente = _obtener_cliente()

    if cliente is None:
        return {}

    clave = _clave(token)

    try:
        crudo = cliente.get(clave)

        if not crudo:
            return {}

        cliente.delete(clave)

        return json.loads(crudo)
    except Exception as error:
        logger.error(f'password-reset consumir_token falló: {error}')

        return {}
