"""Instancias de una evaluación (fechas/convocatorias donde se rinde o entrega)."""
from flask import Blueprint, jsonify, request

from ..constants import PERMISO_EVALUACIONES_GESTIONAR, PERMISO_EVALUACIONES_LEER
from ..utils import requiere_permiso
from ..services.instancias import actualizar, crear, listar

instancias_bp = Blueprint('instancias', __name__)


def _error(error: ValueError):
    status = error.args[1] if len(error.args) > 1 else 400

    return jsonify(error.args[0]), status


@instancias_bp.route('/evaluaciones/<evaluacion_id>/instancias', methods=['GET'])
@requiere_permiso(PERMISO_EVALUACIONES_LEER)
def get_instancias(evaluacion_id):
    """Lista las instancias de la evaluación, ordenadas por número."""
    try:
        resultado = listar(evaluacion_id)
    except ValueError as error:
        return _error(error)

    return jsonify(resultado)


@instancias_bp.route('/evaluaciones/<evaluacion_id>/instancias', methods=['POST'])
@requiere_permiso(PERMISO_EVALUACIONES_GESTIONAR)
def post_instancia(evaluacion_id):
    """Crea una instancia abierta. Body: {nombre, fecha?}. El número se asigna solo."""
    try:
        resultado = crear(evaluacion_id, request.get_json(silent=True) or {})
    except ValueError as error:
        return _error(error)

    return jsonify(resultado), 201


@instancias_bp.route('/instancias/<instancia_id>', methods=['PUT'])
@requiere_permiso(PERMISO_EVALUACIONES_GESTIONAR)
def put_instancia(instancia_id):
    """Edita nombre, fecha o estado de la instancia. `fecha: null` la limpia."""
    try:
        resultado = actualizar(instancia_id, request.get_json(silent=True) or {})
    except ValueError as error:
        return _error(error)

    return jsonify(resultado)
