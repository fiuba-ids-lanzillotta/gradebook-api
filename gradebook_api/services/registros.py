"""Listado del registro de auditoría (backoffice docente)."""
from ..constants import (
    TIPO_DOCENTE,
    TIPO_ESTUDIANTE,
    ERROR_CODE_INVALID_BODY,
)
from ..utils import construir_error_api, validar_entero, validar_minimo
from .. import db

ORDEN_ASC = 'asc'
ORDEN_DESC = 'desc'

_TIPOS_ACTOR = (TIPO_DOCENTE, TIPO_ESTUDIANTE)


def listar(email=None, accion=None, tipo=None, cursada_id=None, orden=None,
           offset: int = 0, limit: int = 50) -> tuple[list[dict], int]:
    """
    Filtra los registros por email (parcial), acción, tipo de actor
    (`docente`/`estudiante`) y cursada; ordena por fecha (`orden` asc|desc,
    default desc). Retorna (página, total).
    """
    if tipo and tipo not in _TIPOS_ACTOR:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_INVALID_BODY,
            message='Tipo de actor inválido',
            description=f"El parámetro 'tipo' admite {_TIPOS_ACTOR}. Se recibió: '{tipo}'.",
        ), 400)

    if orden and orden not in (ORDEN_ASC, ORDEN_DESC):
        raise ValueError(construir_error_api(
            code=ERROR_CODE_INVALID_BODY,
            message='Orden inválido',
            description=f"El parámetro '_orden' admite '{ORDEN_ASC}' o '{ORDEN_DESC}'. Se recibió: '{orden}'.",
        ), 400)

    cursada = validar_minimo(validar_entero(cursada_id, 'cursada'), 1, 'cursada') if cursada_id else None

    return db.buscar_registros(
        email=(email or '').strip() or None,
        accion=(accion or '').strip() or None,
        actor_tipo=tipo,
        cursada_id=cursada,
        ascendente=orden == ORDEN_ASC,
        offset=offset,
        limit=limit,
    )
