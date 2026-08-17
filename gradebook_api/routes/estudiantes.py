from flask import Blueprint, jsonify, request

from ..constants import (
    PERMISO_ESTUDIANTES_LEER,
    PERMISO_ESTUDIANTES_GESTIONAR,
    PERMISO_PERMISOS_ASIGNAR,
)
from ..utils import requiere_permiso, validar_entero, validar_minimo
from ..services.estudiantes import (
    listar_estudiantes,
    buscar_estudiante_por_id,
    crear_estudiante,
    actualizar_estudiante,
    eliminar_estudiante_por_id,
)
from ..services.permisos import asignar_overrides_estudiante

estudiantes_bp = Blueprint('estudiantes', __name__)


@estudiantes_bp.route('/estudiantes', methods=['GET'])
@requiere_permiso(PERMISO_ESTUDIANTES_LEER)
def get_estudiantes():
    """Lista todos los estudiantes. Requiere estudiantes.leer."""
    return jsonify(listar_estudiantes())


@estudiantes_bp.route('/estudiantes/<estudiante_id>', methods=['GET'])
@requiere_permiso(PERMISO_ESTUDIANTES_LEER)
def get_estudiante(estudiante_id):
    try:
        id_validado = validar_minimo(validar_entero(estudiante_id, 'id'), 1, 'id')
        estudiante = buscar_estudiante_por_id(id_validado)
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return jsonify(estudiante)


@estudiantes_bp.route('/estudiantes', methods=['POST'])
@requiere_permiso(PERMISO_ESTUDIANTES_GESTIONAR)
def post_estudiante():
    body = request.get_json(silent=True)

    try:
        estudiante = crear_estudiante(body)
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return jsonify(estudiante), 201


@estudiantes_bp.route('/estudiantes/<estudiante_id>', methods=['PUT'])
@requiere_permiso(PERMISO_ESTUDIANTES_GESTIONAR)
def put_estudiante(estudiante_id):
    body = request.get_json(silent=True)

    try:
        id_validado = validar_minimo(validar_entero(estudiante_id, 'id'), 1, 'id')
        estudiante = actualizar_estudiante(id_validado, body)
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return jsonify(estudiante)


@estudiantes_bp.route('/estudiantes/<estudiante_id>', methods=['DELETE'])
@requiere_permiso(PERMISO_ESTUDIANTES_GESTIONAR)
def delete_estudiante(estudiante_id):
    try:
        id_validado = validar_minimo(validar_entero(estudiante_id, 'id'), 1, 'id')
        eliminar_estudiante_por_id(id_validado)
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return '', 204


@estudiantes_bp.route('/estudiantes/<estudiante_id>/permisos', methods=['PUT'])
@requiere_permiso(PERMISO_PERMISOS_ASIGNAR)
def put_estudiante_permisos(estudiante_id):
    """Reemplaza los overrides de permisos del estudiante."""
    body = request.get_json(silent=True)

    try:
        id_validado = validar_minimo(validar_entero(estudiante_id, 'id'), 1, 'id')
        resultado = asignar_overrides_estudiante(id_validado, body)
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return jsonify(resultado)
