from flask import Blueprint, jsonify, request

from ..constants import (
    PERMISO_CURSADAS_LEER,
    PERMISO_CURSADAS_CREAR,
    PERMISO_CURSADAS_MODIFICAR,
)
from ..utils import requiere_permiso, validar_params_paginacion, validar_entero, validar_minimo
from ..pagination import construir_respuesta_paginada
from ..services.cursadas import listar_cursadas, crear_cursada, actualizar_cursada

cursadas_bp = Blueprint('cursadas', __name__)


@cursadas_bp.route('/cursadas', methods=['GET'])
@requiere_permiso(PERMISO_CURSADAS_LEER)
def get_cursadas():
    """
    Lista los cursos/cursadas. Requiere cursadas.leer.

    Query params: filtros opcionales `codigo` (materia, parcial), `anio`,
    `cuatrimestre`; paginación `_offset` / `_limit`. La respuesta incluye `_links`.
    """
    args = request.args

    try:
        paginacion = validar_params_paginacion(args.to_dict())
        cursadas   = listar_cursadas(
            codigo=args.get('codigo'),
            anio=args.get('anio'),
            cuatrimestre=args.get('cuatrimestre'),
        )
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    if not cursadas:
        return '', 204

    offset, limit = paginacion['offset'], paginacion['limit']
    pagina = cursadas[offset: offset + limit]

    respuesta = construir_respuesta_paginada(
        datos={'cursadas': pagina},
        total=len(cursadas),
        offset=offset,
        limit=limit,
        base_url=request.base_url,
        params=args.to_dict(),
    )

    return jsonify(respuesta)


@cursadas_bp.route('/cursadas', methods=['POST'])
@requiere_permiso(PERMISO_CURSADAS_CREAR)
def post_cursada():
    """
    Alta de cursada. Requiere permiso cursadas.crear (solo super_admin).

    Body: {codigo, nombre, anio, cuatrimestre, fecha_inicio, fecha_fin}.
    Si la materia no existe, se crea.
    """
    body = request.get_json(silent=True)

    try:
        resultado = crear_cursada(body)
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return jsonify(resultado), 201


@cursadas_bp.route('/cursadas/<cursada_id>', methods=['PUT'])
@requiere_permiso(PERMISO_CURSADAS_MODIFICAR)
def put_cursada(cursada_id):
    """
    Modificación de cursada. Requiere permiso cursadas.modificar (solo super_admin).

    Body: {codigo, nombre, anio, cuatrimestre, fecha_inicio, fecha_fin}.
    El codigo debe coincidir con la materia actual (no se puede cambiar de materia).
    """
    body = request.get_json(silent=True)

    try:
        id_validado = validar_minimo(validar_entero(cursada_id, 'id'), 1, 'id')
        resultado = actualizar_cursada(id_validado, body)
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return jsonify(resultado)
