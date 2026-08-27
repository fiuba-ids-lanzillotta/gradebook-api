from flask import Blueprint, jsonify, request

from ..constants import PERMISO_ROLES_GESTIONAR, PERMISO_ROLES_LEER
from ..utils import requiere_permiso
from ..services.permisos import listar_roles, listar_permisos, asignar_permisos_a_rol

roles_bp = Blueprint('roles', __name__)


@roles_bp.route('/roles', methods=['GET'])
@requiere_permiso(PERMISO_ROLES_GESTIONAR)
def get_roles():
    """Lista los roles con sus permisos. Requiere roles.gestionar."""
    return jsonify(listar_roles())


@roles_bp.route('/permisos', methods=['GET'])
@requiere_permiso(PERMISO_ROLES_LEER)
def get_permisos():
    """Lista el catálogo de permisos. Requiere roles.leer."""
    return jsonify(listar_permisos())


@roles_bp.route('/roles/<codigo>/permisos', methods=['PUT'])
@requiere_permiso(PERMISO_ROLES_GESTIONAR)
def put_permisos_de_rol(codigo):
    """Reemplaza el conjunto de permisos de un rol (nivel general)."""
    body = request.get_json(silent=True)

    try:
        resultado = asignar_permisos_a_rol(codigo, body)
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return jsonify(resultado)
