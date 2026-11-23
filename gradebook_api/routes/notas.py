"""Calificaciones del alumno."""
from flask import Blueprint, jsonify, request

from ..constants import PERMISO_NOTAS_LEER
from ..utils import responder_error_api, id_alumno_actual, requiere_auth, requiere_permiso
from ..services.notas import calificaciones_de, mis_calificaciones, mis_notas, vista_de_cursada

notas_bp = Blueprint('notas', __name__)


@notas_bp.route('/cursadas/<cursada_id>/estudiantes/<estudiante_id>/calificaciones', methods=['GET'])
@requiere_permiso(PERMISO_NOTAS_LEER)
def get_calificaciones(cursada_id, estudiante_id):
    """Notas del alumno en las categorías habilitadas de la cursada."""
    try:
        resultado = calificaciones_de(cursada_id, estudiante_id)
    except ValueError as error:
        return responder_error_api(error)

    return jsonify(resultado)


@notas_bp.route('/cursadas/<cursada_id>/vista', methods=['GET'])
@requiere_permiso(PERMISO_NOTAS_LEER)
def get_vista(cursada_id):
    """Planilla de la cursada: inscriptos, estado y nota de cada instancia habilitada."""
    try:
        resultado = vista_de_cursada(cursada_id, q=request.args.get('q'))
    except ValueError as error:
        return responder_error_api(error)

    return jsonify(resultado)


@notas_bp.route('/me/calificaciones', methods=['GET'])
@requiere_auth()
def get_mis_calificaciones():
    """El perfil de notas del alumno, igual al del docente y sin edición."""
    try:
        resultado = mis_calificaciones(id_alumno_actual())
    except ValueError as error:
        return responder_error_api(error)

    return jsonify(resultado)


@notas_bp.route('/me/notas', methods=['GET'])
@requiere_auth()
def get_mis_notas():
    """Las calificaciones del alumno: individuales y las de los equipos que integra."""
    try:
        resultado = mis_notas(id_alumno_actual())
    except ValueError as error:
        return responder_error_api(error)

    return jsonify(resultado)
