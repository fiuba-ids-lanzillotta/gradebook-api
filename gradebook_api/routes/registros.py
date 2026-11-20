"""Registro de auditoría (solo lectura)."""
from flask import Blueprint, jsonify, request

from ..constants import PERMISO_REGISTROS_LEER
from ..utils import requiere_permiso, validar_params_paginacion
from ..pagination import construir_respuesta_paginada
from ..services.registros import listar

registros_bp = Blueprint('registros', __name__)


@registros_bp.route('/registros', methods=['GET'])
@requiere_permiso(PERMISO_REGISTROS_LEER)
def get_registros():
    """
    Lista los registros de auditoría. Requiere registros.leer.

    Query params: `email` (parcial), `accion`, `tipo` (docente|estudiante),
    `cursada`, `_orden` (asc|desc, default desc), `_offset`/`_limit`.
    """
    args = request.args

    try:
        paginacion = validar_params_paginacion(args.to_dict())
        registros, total = listar(
            email=args.get('email'),
            accion=args.get('accion'),
            tipo=args.get('tipo'),
            cursada_id=args.get('cursada'),
            orden=args.get('_orden'),
            offset=paginacion['offset'],
            limit=paginacion['limit'],
        )
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    if not registros:
        return '', 204

    respuesta = construir_respuesta_paginada(
        datos={'registros': registros},
        total=total,
        offset=paginacion['offset'],
        limit=paginacion['limit'],
        base_url=request.base_url,
        params=args.to_dict(),
    )

    return jsonify(respuesta)
