from flask import Blueprint, jsonify, request

from ..constants import (
    PERMISO_DOCENTES_LEER,
    PERMISO_DOCENTES_GESTIONAR,
    PERMISO_PERMISOS_ASIGNAR,
)
from ..utils import requiere_permiso, validar_entero, validar_minimo
from ..services.docentes import (
    listar_docentes,
    buscar_docente_por_id,
    crear_docente,
    actualizar_docente,
    eliminar_docente_por_id,
)
from ..services.permisos import asignar_overrides_docente

docentes_bp = Blueprint('docentes', __name__)


@docentes_bp.route('/docentes', methods=['GET'])
@requiere_permiso(PERMISO_DOCENTES_LEER)
def get_docentes():
    """Lista todos los docentes. Requiere docentes.leer."""
    return jsonify(listar_docentes())


@docentes_bp.route('/docentes/<docente_id>', methods=['GET'])
@requiere_permiso(PERMISO_DOCENTES_LEER)
def get_docente(docente_id):
    try:
        id_validado = validar_minimo(validar_entero(docente_id, 'id'), 1, 'id')
        docente = buscar_docente_por_id(id_validado)
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return jsonify(docente)


@docentes_bp.route('/docentes', methods=['POST'])
@requiere_permiso(PERMISO_DOCENTES_GESTIONAR)
def post_docente():
    body = request.get_json(silent=True)

    try:
        docente = crear_docente(body)
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return jsonify(docente), 201


@docentes_bp.route('/docentes/<docente_id>', methods=['PUT'])
@requiere_permiso(PERMISO_DOCENTES_GESTIONAR)
def put_docente(docente_id):
    body = request.get_json(silent=True)

    try:
        id_validado = validar_minimo(validar_entero(docente_id, 'id'), 1, 'id')
        docente = actualizar_docente(id_validado, body)
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return jsonify(docente)


@docentes_bp.route('/docentes/<docente_id>', methods=['DELETE'])
@requiere_permiso(PERMISO_DOCENTES_GESTIONAR)
def delete_docente(docente_id):
    try:
        id_validado = validar_minimo(validar_entero(docente_id, 'id'), 1, 'id')
        eliminar_docente_por_id(id_validado)
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return '', 204


@docentes_bp.route('/docentes/<docente_id>/permisos', methods=['PUT'])
@requiere_permiso(PERMISO_PERMISOS_ASIGNAR)
def put_docente_permisos(docente_id):
    """Reemplaza los overrides de permisos del docente."""
    body = request.get_json(silent=True)

    try:
        id_validado = validar_minimo(validar_entero(docente_id, 'id'), 1, 'id')
        resultado = asignar_overrides_docente(id_validado, body)
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return jsonify(resultado)
