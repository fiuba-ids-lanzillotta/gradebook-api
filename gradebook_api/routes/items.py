from flask import Blueprint, jsonify, request

from ..constants import ROL_ADMIN
from ..utils import requiere_auth, validar_entero, validar_minimo, sin_cache
from ..services.items import (
    listar_items,
    buscar_item_por_id,
    crear_item,
    actualizar_item,
    eliminar_item_por_id,
)

items_bp = Blueprint('items', __name__)


@items_bp.route('/items', methods=['GET'])
def get_items():
    """Lista todos los items (público)."""
    return sin_cache(jsonify(listar_items()))


@items_bp.route('/items/<item_id>', methods=['GET'])
def get_item(item_id):
    try:
        id_validado = validar_minimo(validar_entero(item_id, 'id'), 1, 'id')
        item = buscar_item_por_id(id_validado)
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return sin_cache(jsonify(item))


@items_bp.route('/items', methods=['POST'])
@requiere_auth(rol=ROL_ADMIN)
def post_item():
    body = request.get_json(silent=True)

    try:
        item = crear_item(body)
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return jsonify(item), 201


@items_bp.route('/items/<item_id>', methods=['PUT'])
@requiere_auth(rol=ROL_ADMIN)
def put_item(item_id):
    body = request.get_json(silent=True)

    try:
        id_validado = validar_minimo(validar_entero(item_id, 'id'), 1, 'id')
        item = actualizar_item(id_validado, body)
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return jsonify(item)


@items_bp.route('/items/<item_id>', methods=['DELETE'])
@requiere_auth(rol=ROL_ADMIN)
def delete_item(item_id):
    try:
        id_validado = validar_minimo(validar_entero(item_id, 'id'), 1, 'id')
        eliminar_item_por_id(id_validado)
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return '', 204
