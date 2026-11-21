"""Evaluaciones de una cursada (hoy: habilitar/cerrar la creación de equipos)."""
from ..constants import (
    ACCION_EVALUACION_GRUPOS,
    ERROR_CODE_EVALUACION_NO_GRUPAL,
    ERROR_CODE_EVALUACION_NOT_FOUND,
    ERROR_CODE_GRUPOS_OCUPADA,
)
from ..utils import construir_error_api, validar_booleano, validar_entero, validar_minimo
from .. import db, registro

MODALIDAD_GRUPAL = 'grupal'


def habilitar_crear_grupos(evaluacion_id: int, habilitado) -> dict:
    """
    Abre o cierra la creación de equipos por los alumnos en una evaluación grupal.
    Solo una evaluación por cursada puede tenerla habilitada (índice parcial en la
    base + chequeo acá para devolver el error con nombre).
    """
    evaluacion = _evaluacion_o_404(evaluacion_id)
    habilitado = validar_booleano(habilitado, 'habilitado')

    if evaluacion.get('modalidad') != MODALIDAD_GRUPAL:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_EVALUACION_NO_GRUPAL,
            message='La evaluación no es grupal',
            description='Solo las evaluaciones de modalidad grupal pueden habilitar la creación de equipos.',
        ), 400)

    if habilitado:
        activa = db.buscar_evaluacion_con_creacion_grupos(evaluacion['cursada_id'])

        if activa and activa['id'] != evaluacion['id']:
            raise ValueError(construir_error_api(
                code=ERROR_CODE_GRUPOS_OCUPADA,
                message='Ya hay una evaluación con creación de equipos abierta',
                description=f'La creación de equipos está habilitada en "{activa.get("nombre")}". Cerrala ahí primero.',
            ), 409)

    fila = db.actualizar_evaluacion(evaluacion['id'], {'permite_crear_grupos': habilitado})
    registro.registrar(
        ACCION_EVALUACION_GRUPOS,
        f'{"Habilitó" if habilitado else "Deshabilitó"} la creación de equipos en la evaluación "{evaluacion.get("nombre")}"',
        detalle={'evaluacion_id': evaluacion['id'], 'habilitado': habilitado},
        cursada_id=evaluacion.get('cursada_id'),
    )

    return _dto(fila or evaluacion)


def _evaluacion_o_404(evaluacion_id: int) -> dict:
    evaluacion_id = validar_minimo(validar_entero(evaluacion_id, 'id'), 1, 'id')
    evaluacion = db.obtener_evaluacion(evaluacion_id)

    if not evaluacion:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_EVALUACION_NOT_FOUND,
            message='Evaluación no encontrada',
            description=f"No existe una evaluación con id '{evaluacion_id}'.",
        ), 404)

    return evaluacion


def _dto(fila: dict) -> dict:
    return {
        'id': fila.get('id'),
        'cursada_id': fila.get('cursada_id'),
        'nombre': fila.get('nombre'),
        'modalidad': fila.get('modalidad'),
        'permite_crear_grupos': fila.get('permite_crear_grupos'),
    }
