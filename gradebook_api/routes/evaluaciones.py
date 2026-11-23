"""Evaluaciones de una cursada."""
from flask import Blueprint, jsonify, request

from ..constants import PERMISO_EVALUACIONES_GESTIONAR, PERMISO_EVALUACIONES_LEER, PERMISO_GRUPOS_HABILITAR
from ..utils import responder_error_api, requiere_permiso
from ..services.evaluaciones import cambiar_visibilidad, crear, habilitar_crear_grupos, listar_de_cursada

evaluaciones_bp = Blueprint('evaluaciones', __name__)


@evaluaciones_bp.route('/cursadas/<cursada_id>/evaluaciones', methods=['GET'])
@requiere_permiso(PERMISO_EVALUACIONES_LEER)
def get_evaluaciones(cursada_id):
    """Lista las categorías de la cursada, con la cantidad de instancias de cada una."""
    try:
        resultado = listar_de_cursada(cursada_id)
    except ValueError as error:
        return responder_error_api(error)

    return jsonify(resultado)


@evaluaciones_bp.route('/cursadas/<cursada_id>/evaluaciones', methods=['POST'])
@requiere_permiso(PERMISO_EVALUACIONES_GESTIONAR)
def post_evaluacion(cursada_id):
    """Crea una categoría. Body: {nombre, tipo, criterio, peso, modalidad, instancias}. Arranca deshabilitada."""
    try:
        resultado = crear(cursada_id, request.get_json(silent=True) or {})
    except ValueError as error:
        return responder_error_api(error)

    return jsonify(resultado), 201


@evaluaciones_bp.route('/evaluaciones/<evaluacion_id>/visibilidad', methods=['PUT'])
@requiere_permiso(PERMISO_EVALUACIONES_GESTIONAR)
def put_visibilidad(evaluacion_id):
    """Habilita o deshabilita la categoría. Body: {visibilidad: habilitado|deshabilitado}."""
    try:
        resultado = cambiar_visibilidad(
            evaluacion_id, (request.get_json(silent=True) or {}).get('visibilidad'),
        )
    except ValueError as error:
        return responder_error_api(error)

    return jsonify(resultado)


@evaluaciones_bp.route('/evaluaciones/<evaluacion_id>/crear-grupos', methods=['PUT'])
@requiere_permiso(PERMISO_GRUPOS_HABILITAR)
def put_crear_grupos(evaluacion_id):
    """Abre/cierra la creación de equipos por alumnos. Body: {habilitado}. Solo super_admin."""
    try:
        resultado = habilitar_crear_grupos(evaluacion_id, (request.get_json(silent=True) or {}).get('habilitado'))
    except ValueError as error:
        return responder_error_api(error)

    return jsonify(resultado)
