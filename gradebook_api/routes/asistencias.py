from flask import Blueprint, jsonify, request

from ..constants import PERMISO_ASISTENCIAS_LEER, PERMISO_ASISTENCIAS_GESTIONAR
from ..utils import requiere_permiso, validar_entero, validar_minimo, validar_params_paginacion
from ..pagination import construir_respuesta_paginada
from ..services.asistencias import (
    crear_clase,
    listar_clases_de_cursada,
    enviar_qrs,
    resumen_envio,
    marcar_asistencia,
    listar_asistencias_de_clase,
    cerrar_clase,
)
from ..services.clases import listar_clases

asistencias_bp = Blueprint('asistencias', __name__)


def _id_valido(valor, nombre):
    return validar_minimo(validar_entero(valor, nombre), 1, nombre)


def _error(error):
    status = error.args[1] if len(error.args) > 1 else 400

    return jsonify(error.args[0]), status


# ---------------------------------------------------------------
# Clases (toma de asistencia por fecha)
# ---------------------------------------------------------------

@asistencias_bp.route('/cursadas/<cursada_id>/clases', methods=['POST'])
@requiere_permiso(PERMISO_ASISTENCIAS_GESTIONAR)
def post_clase(cursada_id):
    """Dispara la toma de asistencia de una fecha: crea la clase y genera los QRs. asistencias.gestionar."""
    try:
        resultado = crear_clase(_id_valido(cursada_id, 'cursada_id'), request.get_json(silent=True))
    except ValueError as error:
        return _error(error)

    return jsonify(resultado), 201


@asistencias_bp.route('/cursadas/<cursada_id>/clases', methods=['GET'])
@requiere_permiso(PERMISO_ASISTENCIAS_LEER)
def get_clases(cursada_id):
    """Lista las clases con toma de asistencia de una cursada (paginado). asistencias.leer."""
    args = request.args

    try:
        paginacion = validar_params_paginacion(args.to_dict())
        clases     = listar_clases_de_cursada(_id_valido(cursada_id, 'cursada_id'))
    except ValueError as error:
        return _error(error)

    if not clases:
        return '', 204

    offset, limit = paginacion['offset'], paginacion['limit']

    return jsonify(construir_respuesta_paginada(
        datos={'clases': clases[offset: offset + limit]},
        total=len(clases), offset=offset, limit=limit,
        base_url=request.base_url, params=args.to_dict(),
    ))


@asistencias_bp.route('/clases', methods=['GET'])
@requiere_permiso(PERMISO_ASISTENCIAS_LEER)
def get_clases_por_materia():
    """Lista las clases de una materia/cursada (paginado). Query params: materia (obligatorio), cursada (opcional)."""
    args = request.args

    try:
        paginacion = validar_params_paginacion(args.to_dict())
        clases     = listar_clases(
            materia=args.get('materia'),
            cursada_id=args.get('cursada'),
        )
    except ValueError as error:
        return _error(error)

    if not clases:
        return '', 204

    offset, limit = paginacion['offset'], paginacion['limit']

    return jsonify(construir_respuesta_paginada(
        datos={'clases': clases[offset: offset + limit]},
        total=len(clases), offset=offset, limit=limit,
        base_url=request.base_url, params=args.to_dict(),
    ))


# ---------------------------------------------------------------
# Envío de QRs (por lotes) + progreso
# ---------------------------------------------------------------

@asistencias_bp.route('/clases/<clase_id>/enviar-qrs', methods=['POST'])
@requiere_permiso(PERMISO_ASISTENCIAS_GESTIONAR)
def post_enviar_qrs(clase_id):
    """Envía el próximo lote de QRs pendientes. Query `limite` opcional. asistencias.gestionar."""
    try:
        clase = _id_valido(clase_id, 'clase_id')
        limite = request.args.get('limite')
        limite = _id_valido(limite, 'limite') if limite is not None else None
        resultado = enviar_qrs(clase, limite)
    except ValueError as error:
        return _error(error)

    return jsonify(resultado)


@asistencias_bp.route('/clases/<clase_id>/envio', methods=['GET'])
@requiere_permiso(PERMISO_ASISTENCIAS_LEER)
def get_envio(clase_id):
    """Estado del envío de QRs de una clase (para el polling de progreso). asistencias.leer."""
    try:
        resultado = resumen_envio(_id_valido(clase_id, 'clase_id'))
    except ValueError as error:
        return _error(error)

    return jsonify(resultado)


# ---------------------------------------------------------------
# Marcar / listar / cerrar
# ---------------------------------------------------------------

@asistencias_bp.route('/clases/<clase_id>/marcar', methods=['POST'])
@requiere_permiso(PERMISO_ASISTENCIAS_GESTIONAR)
def post_marcar(clase_id):
    """Marca 'presente' por código (QR/tipeado) o padrón. asistencias.gestionar."""
    docente_id = request.usuario_actual.get('sub')

    try:
        resultado = marcar_asistencia(_id_valido(clase_id, 'clase_id'), request.get_json(silent=True), docente_id)
    except ValueError as error:
        return _error(error)

    return jsonify(resultado)


@asistencias_bp.route('/clases/<clase_id>/asistencias', methods=['GET'])
@requiere_permiso(PERMISO_ASISTENCIAS_LEER)
def get_asistencias(clase_id):
    """Lista las asistencias de una clase (paginado). Filtros `estado` y `q`. asistencias.leer."""
    args = request.args

    try:
        paginacion  = validar_params_paginacion(args.to_dict())
        asistencias = listar_asistencias_de_clase(
            _id_valido(clase_id, 'clase_id'), estado=args.get('estado'), q=args.get('q')
        )
    except ValueError as error:
        return _error(error)

    if not asistencias:
        return '', 204

    offset, limit = paginacion['offset'], paginacion['limit']

    return jsonify(construir_respuesta_paginada(
        datos={'asistencias': asistencias[offset: offset + limit]},
        total=len(asistencias), offset=offset, limit=limit,
        base_url=request.base_url, params=args.to_dict(),
    ))


@asistencias_bp.route('/clases/<clase_id>/cerrar', methods=['POST'])
@requiere_permiso(PERMISO_ASISTENCIAS_GESTIONAR)
def post_cerrar(clase_id):
    """Cierra la clase: los pendientes pasan a ausentes. asistencias.gestionar."""
    try:
        resultado = cerrar_clase(_id_valido(clase_id, 'clase_id'))
    except ValueError as error:
        return _error(error)

    return jsonify(resultado)
