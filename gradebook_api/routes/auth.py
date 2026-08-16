from flask import Blueprint, jsonify, request

from ..utils import requiere_auth
from ..services.auth import autenticar_admin, identidad_actual

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
def post_login():
    body = request.get_json(silent=True)

    try:
        resultado = autenticar_admin(body)
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return jsonify(resultado)


@auth_bp.route('/me', methods=['GET'])
@requiere_auth()
def get_me():
    """Retorna la identidad del admin autenticado a partir del token."""
    return jsonify(identidad_actual(request.usuario_actual))
