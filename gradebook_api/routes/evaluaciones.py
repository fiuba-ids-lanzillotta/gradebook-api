"""Evaluaciones de una cursada."""
from flask import Blueprint, jsonify, request

from ..constants import PERMISO_GRUPOS_HABILITAR
from ..utils import requiere_permiso
from ..services.evaluaciones import habilitar_crear_grupos

evaluaciones_bp = Blueprint('evaluaciones', __name__)


@evaluaciones_bp.route('/evaluaciones/<evaluacion_id>/crear-grupos', methods=['PUT'])
@requiere_permiso(PERMISO_GRUPOS_HABILITAR)
def put_crear_grupos(evaluacion_id):
    """Abre/cierra la creación de equipos por alumnos. Body: {habilitado}. Solo super_admin."""
    try:
        resultado = habilitar_crear_grupos(evaluacion_id, (request.get_json(silent=True) or {}).get('habilitado'))
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return jsonify(resultado)
