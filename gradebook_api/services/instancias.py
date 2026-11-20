"""Instancias de una evaluación (fechas/convocatorias donde se rinde o entrega)."""
from ..constants import (
    ACCION_INSTANCIA_CERRAR,
    ACCION_INSTANCIA_CREAR,
    ACCION_INSTANCIA_EDITAR,
    ERROR_CODE_EVALUACION_NOT_FOUND,
    ERROR_CODE_INSTANCIA_NOT_FOUND,
    ESTADO_INSTANCIA_CERRADA,
)
from ..utils import construir_error_api, validar_entero, validar_minimo
from ..validators.instancias import validar_body_actualizar_instancia, validar_body_instancia
from .. import db, registro


def listar(evaluacion_id: int) -> dict:
    """Instancias de la evaluación, ordenadas por número."""
    evaluacion = _evaluacion_o_404(evaluacion_id)

    return {
        'instancias': [_dto(fila, evaluacion) for fila in db.buscar_instancias(evaluacion['id'])],
    }


def crear(evaluacion_id: int, body: dict) -> dict:
    """Crea una instancia abierta con el número siguiente dentro de la evaluación."""
    evaluacion = _evaluacion_o_404(evaluacion_id)
    datos = validar_body_instancia(body)
    numero = db.proximo_numero_instancia(evaluacion['id'])
    fila = db.insertar_instancia(evaluacion['id'], numero, datos['nombre'], datos['fecha'])
    registro.registrar(
        ACCION_INSTANCIA_CREAR,
        f'Creó la instancia "{datos["nombre"]}" de la evaluación "{evaluacion.get("nombre")}"',
        detalle={
            'instancia_id': fila.get('id'),
            'evaluacion_id': evaluacion['id'],
            'numero': numero,
            'fecha': datos['fecha'],
        },
        cursada_id=evaluacion.get('cursada_id'),
    )

    return _dto(fila, evaluacion)


def actualizar(instancia_id: int, body: dict) -> dict:
    """Edita nombre, fecha o estado de una instancia existente."""
    instancia = _instancia_o_404(instancia_id)
    datos = validar_body_actualizar_instancia(body)
    fila = db.actualizar_instancia(instancia['id'], datos)
    evaluacion = db.obtener_evaluacion(instancia['evaluacion_id']) or {}
    recien_cerrada = (datos.get('estado') == ESTADO_INSTANCIA_CERRADA
                      and instancia.get('estado') != ESTADO_INSTANCIA_CERRADA)
    registro.registrar(
        ACCION_INSTANCIA_CERRAR if recien_cerrada else ACCION_INSTANCIA_EDITAR,
        _descripcion_edicion(instancia, evaluacion, recien_cerrada),
        detalle={'instancia_id': instancia['id'], 'cambios': datos},
        cursada_id=evaluacion.get('cursada_id'),
    )

    return _dto(fila or instancia, evaluacion)


def _descripcion_edicion(instancia: dict, evaluacion: dict, recien_cerrada: bool) -> str:
    nombre = instancia.get('nombre') or instancia.get('id')
    evaluacion_nombre = evaluacion.get('nombre') or instancia.get('evaluacion_id')
    verbo = 'Cerró' if recien_cerrada else 'Editó'

    return f'{verbo} la instancia "{nombre}" de la evaluación "{evaluacion_nombre}"'


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


def _instancia_o_404(instancia_id: int) -> dict:
    instancia_id = validar_minimo(validar_entero(instancia_id, 'id'), 1, 'id')
    instancia = db.obtener_instancia(instancia_id)

    if not instancia:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_INSTANCIA_NOT_FOUND,
            message='Instancia no encontrada',
            description=f"No existe una instancia con id '{instancia_id}'.",
        ), 404)

    return instancia


def _dto(fila: dict, evaluacion: dict) -> dict:
    return {
        'id': fila.get('id'),
        'evaluacion_id': fila.get('evaluacion_id'),
        'evaluacion_nombre': evaluacion.get('nombre') or '',
        'numero': fila.get('numero'),
        'nombre': fila.get('nombre'),
        'fecha': fila.get('fecha'),
        'estado': fila.get('estado'),
        'created_at': fila.get('created_at'),
        'updated_at': fila.get('updated_at'),
    }
