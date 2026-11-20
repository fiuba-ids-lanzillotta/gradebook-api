"""
Escritura de registros de auditoría.

`registrar` se llama al final de cada mutación exitosa del backoffice (y de las
acciones propias del estudiante, cuando existan). Resuelve el actor desde el
payload del JWT (`request.usuario_actual`, que dejan `@requiere_permiso` /
`@requiere_auth`) y persiste una fila en `registros` con la acción codificada y
la descripción ya renderizada — la foto queda inmutable aunque el actor se
borre o renombre después.

Fail-open como `cola.publicar`: ante cualquier error de escritura (o si no hay
actor en el contexto, ej. tests) se loguea y se sigue — la auditoría nunca
rompe la operación de negocio.
"""
import logging

from flask import has_request_context, request

from .constants import TIPO_DOCENTE, TIPO_ESTUDIANTE
from . import db

logger = logging.getLogger(__name__)

MAXIMO_DESCRIPCION = 300


def registrar(accion: str, descripcion: str, detalle: dict = None, cursada_id: int = None) -> bool:
    """
    Persiste un registro de auditoría para el actor del request actual.
    Retorna True si se guardó; False si no hay actor o la escritura falló.
    """
    actor = _actor_actual()

    if not actor:
        logger.warning(f'[registro] Sin actor en el contexto; no se registra "{accion}"')

        return False

    fila = {
        'actor_tipo':  actor['tipo'],
        'actor_id':    actor['id'],
        'actor_email': actor['email'],
        'accion':      accion,
        'descripcion': descripcion[:MAXIMO_DESCRIPCION],
        'cursada_id':  cursada_id,
        'detalle':     detalle or {},
    }

    try:
        db.insertar_registro(fila)
    except Exception as error:
        logger.error(f'[registro] No se pudo guardar "{accion}": {error}')

        return False

    return True


def _actor_actual() -> dict:
    """Resuelve el actor del request (payload JWT), o {} fuera de contexto."""
    if not has_request_context():
        return {}

    payload = getattr(request, 'usuario_actual', None) or {}
    tipo = payload.get('tipo')
    email = payload.get('email')

    if tipo not in (TIPO_DOCENTE, TIPO_ESTUDIANTE) or not email:
        return {}

    return {
        'tipo':  tipo,
        'id':    int(payload.get('sub') or 0),
        'email': email,
    }
