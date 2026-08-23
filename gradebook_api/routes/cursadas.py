from flask import Blueprint, jsonify, request

from ..constants import PERMISO_CURSADAS_LEER
from ..utils import requiere_permiso, validar_params_paginacion
from ..pagination import construir_respuesta_paginada
from ..services.cursadas import listar_cursadas

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
