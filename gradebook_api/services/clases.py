"""Listado de clases por materia/cursada con cache."""
from datetime import date

from ..constants import (
    ERROR_CODE_MATERIA_NOT_FOUND,
    ERROR_CODE_CURSADA_NOT_FOUND,
    ERROR_CODE_CURSADA_VIGENTE_NOT_FOUND,
)
from ..config import CACHE_TTL_CLASES_SEGUNDOS
from ..utils import construir_error_api, validar_entero, validar_minimo, validar_string_no_vacio
from .. import db, cache


def listar_clases(materia: str, cursada_id=None) -> list[dict]:
    """
    Retorna las clases de una materia y cursada (más recientes primero).

    Si `cursada_id` no se envía, se usa la cursada vigente de la materia.
    Cada item: {id, fecha, titulo}.
    """
    materia_codigo = validar_string_no_vacio(materia, 'materia')
    materia_encontrada = db.obtener_materia_por_codigo(materia_codigo)

    if not materia_encontrada:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_MATERIA_NOT_FOUND,
            message='Materia no encontrada',
            description=f"No existe una materia con código '{materia_codigo}'."
        ), 404)

    cursada = _resolver_cursada(materia_encontrada['id'], cursada_id)

    clave_cache = f'clases:cursada:{cursada["id"]}'
    clases = cache.obtener(clave_cache)

    if clases is None:
        clases = [_clase_dto(fila) for fila in db.buscar_clases_de_cursada(cursada['id'])]
        cache.guardar(clave_cache, clases, CACHE_TTL_CLASES_SEGUNDOS)

    return clases


def _resolver_cursada(materia_id: int, cursada_id):
    """Resuelve la cursada: por id si viene, o la vigente de la materia."""
    if cursada_id is None or str(cursada_id).strip() == '':
        hoy = date.today().isoformat()
        cursada = db.obtener_cursada_vigente_por_materia(materia_id, hoy)

        if not cursada:
            raise ValueError(construir_error_api(
                code=ERROR_CODE_CURSADA_VIGENTE_NOT_FOUND,
                message='No hay cursada vigente',
                description=f"No existe una cursada vigente para la materia con id '{materia_id}'."
            ), 404)

        return cursada

    cursada_id_validado = validar_minimo(validar_entero(cursada_id, 'cursada'), 1, 'cursada')
    cursada = db.obtener_cursada_por_id(cursada_id_validado)

    if not cursada or cursada['materia_id'] != materia_id:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_CURSADA_NOT_FOUND,
            message='Cursada no encontrada',
            description=f"No existe una cursada con id '{cursada_id_validado}' para la materia indicada."
        ), 404)

    return cursada


def _clase_dto(fila: dict) -> dict:
    return {
        'id':     fila['id'],
        'fecha':  fila['fecha'],
        'titulo': fila.get('titulo'),
    }
