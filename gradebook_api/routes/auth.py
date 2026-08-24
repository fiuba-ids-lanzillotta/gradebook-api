from flask import Blueprint, jsonify, request

from ..utils import requiere_auth
from ..services.auth import autenticar, identidad_actual
from ..services.password_reset import solicitar_recuperacion, confirmar_recuperacion

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
def post_login():
    body = request.get_json(silent=True)

    try:
        resultado = autenticar(body)
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return jsonify(resultado)


@auth_bp.route('/me', methods=['GET'])
@requiere_auth()
def get_me():
    """Retorna la identidad (con permisos efectivos) de la persona autenticada."""
    return jsonify(identidad_actual(request.usuario_actual))


@auth_bp.route('/password-reset/solicitar', methods=['POST'])
def post_password_reset_solicitar():
    """Solicita el envío del link de recuperación. Respuesta uniforme (no enumera)."""
    body = request.get_json(silent=True)

    try:
        resultado = solicitar_recuperacion(body)
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return jsonify(resultado)


@auth_bp.route('/password-reset/confirmar', methods=['POST'])
def post_password_reset_confirmar():
    """Confirma el reset: valida el token de un solo uso y actualiza el password."""
    body = request.get_json(silent=True)

    try:
        resultado = confirmar_recuperacion(body)
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return jsonify(resultado)
