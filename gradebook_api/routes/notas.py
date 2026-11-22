"""Calificaciones del alumno."""
from flask import Blueprint, jsonify

from ..utils import id_alumno_actual, requiere_auth
from ..services.notas import mis_notas

notas_bp = Blueprint('notas', __name__)


@notas_bp.route('/me/notas', methods=['GET'])
@requiere_auth()
def get_mis_notas():
    """Las calificaciones del alumno: individuales y las de los equipos que integra."""
    try:
        resultado = mis_notas(id_alumno_actual())
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return jsonify(resultado)
