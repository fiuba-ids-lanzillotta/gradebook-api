"""Calificaciones del alumno."""
from flask import Blueprint, jsonify

from ..utils import responder_error_api, id_alumno_actual, requiere_auth
from ..services.notas import mis_notas

notas_bp = Blueprint('notas', __name__)


@notas_bp.route('/me/notas', methods=['GET'])
@requiere_auth()
def get_mis_notas():
    """Las calificaciones del alumno: individuales y las de los equipos que integra."""
    try:
        resultado = mis_notas(id_alumno_actual())
    except ValueError as error:
        return responder_error_api(error)

    return jsonify(resultado)
