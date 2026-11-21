"""Equipos de una evaluación grupal."""
from flask import Blueprint, jsonify, request

from ..constants import (
    PERMISO_ESTUDIANTES_LEER,
    PERMISO_ESTUDIANTES_MODIFICAR,
    TIPO_ESTUDIANTE,
    ERROR_CODE_SIN_PERMISO,
)
from ..utils import construir_error_api, requiere_auth, requiere_permiso, validar_entero, validar_minimo
from ..services.grupos import (
    agregar_integrante,
    agregar_por_padron,
    asignar_tutores,
    crear_mi_equipo,
    detalle,
    echar_integrante,
    listar_de_cursada,
    mi_equipo,
    renombrar,
    renombrar_mi_equipo,
    salir_de_mi_equipo,
    transferir_integrante,
)

grupos_bp = Blueprint('grupos', __name__)


def _error(error: ValueError):
    status = error.args[1] if len(error.args) > 1 else 400

    return jsonify(error.args[0]), status


def _id_alumno() -> int:
    payload = getattr(request, 'usuario_actual', None) or {}

    if payload.get('tipo') != TIPO_ESTUDIANTE:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_SIN_PERMISO,
            message='Solo alumnos',
            description='Esta acción es del alumno.',
        ), 403)

    return int(payload['sub'])


@grupos_bp.route('/me/equipo', methods=['GET'])
@requiere_auth()
def get_mi_equipo():
    """El equipo del alumno en la evaluación que tiene habilitada la creación."""
    try:
        resultado = mi_equipo(_id_alumno(), con_candidatos=True)
    except ValueError as error:
        return _error(error)

    return jsonify(resultado)


@grupos_bp.route('/me/equipo', methods=['POST'])
@requiere_auth()
def post_mi_equipo():
    """Crea el equipo en esa evaluación. Body: {nombre, padrones?: []}."""
    body = request.get_json(silent=True) or {}

    try:
        resultado = crear_mi_equipo(_id_alumno(), body.get('nombre'), body.get('padrones') or [])
    except ValueError as error:
        return _error(error)

    return jsonify(resultado), 201


@grupos_bp.route('/me/equipo', methods=['PUT'])
@requiere_auth()
def put_mi_equipo():
    """El owner renombra su equipo. Body: {nombre}."""
    body = request.get_json(silent=True) or {}

    try:
        resultado = renombrar_mi_equipo(_id_alumno(), body.get('nombre'))
    except ValueError as error:
        return _error(error)

    return jsonify(resultado)


@grupos_bp.route('/me/equipo/salir', methods=['POST'])
@requiere_auth()
def post_salir_de_mi_equipo():
    """El alumno deja su equipo. Si es el owner y hay otros, la corona pasa a uno al azar."""
    try:
        resultado = salir_de_mi_equipo(_id_alumno())
    except ValueError as error:
        return _error(error)

    return jsonify(resultado)


@grupos_bp.route('/me/equipo/integrantes', methods=['POST'])
@requiere_auth()
def post_mi_integrante():
    """El owner suma un alumno por padrón. Body: {padron}."""
    body = request.get_json(silent=True) or {}

    try:
        resultado = agregar_por_padron(_id_alumno(), body.get('padron'))
    except ValueError as error:
        return _error(error)

    return jsonify(resultado), 201


@grupos_bp.route('/cursadas/<cursada_id>/grupos', methods=['GET'])
@requiere_permiso(PERMISO_ESTUDIANTES_LEER)
def get_grupos(cursada_id):
    """Lista los equipos de las evaluaciones grupales de la cursada."""
    try:
        resultado = listar_de_cursada(cursada_id)
    except ValueError as error:
        return _error(error)

    return jsonify(resultado)


@grupos_bp.route('/grupos/tutores', methods=['PUT'])
@requiere_permiso(PERMISO_ESTUDIANTES_MODIFICAR)
def put_tutores():
    """Asigna tutores. Body: {asignaciones: [{grupo_id, tutor_id|null}]}."""
    body = request.get_json(silent=True) or {}

    try:
        resultado = asignar_tutores(body.get('asignaciones'))
    except ValueError as error:
        return _error(error)

    return jsonify(resultado)


@grupos_bp.route('/grupos/<grupo_id>', methods=['GET'])
@requiere_permiso(PERMISO_ESTUDIANTES_LEER)
def get_grupo(grupo_id):
    try:
        resultado = detalle(grupo_id)
    except ValueError as error:
        return _error(error)

    return jsonify(resultado)


@grupos_bp.route('/grupos/<grupo_id>', methods=['PUT'])
@requiere_permiso(PERMISO_ESTUDIANTES_MODIFICAR)
def put_grupo(grupo_id):
    """Renombra el equipo. Body: {nombre}."""
    body = request.get_json(silent=True) or {}

    try:
        resultado = renombrar(grupo_id, body.get('nombre'))
    except ValueError as error:
        return _error(error)

    return jsonify(resultado)


@grupos_bp.route('/grupos/<grupo_id>/integrantes', methods=['POST'])
@requiere_permiso(PERMISO_ESTUDIANTES_MODIFICAR)
def post_integrante(grupo_id):
    """Suma un alumno que esté cursando y no integre otro equipo de la evaluación."""
    body = request.get_json(silent=True) or {}

    try:
        resultado = agregar_integrante(grupo_id, body.get('estudiante_id'))
    except ValueError as error:
        return _error(error)

    return jsonify(resultado), 201


@grupos_bp.route('/grupos/<grupo_id>/integrantes/<estudiante_id>', methods=['DELETE'])
@requiere_permiso(PERMISO_ESTUDIANTES_MODIFICAR)
def delete_integrante(grupo_id, estudiante_id):
    try:
        resultado = echar_integrante(grupo_id, estudiante_id)
    except ValueError as error:
        return _error(error)

    return jsonify(resultado)


@grupos_bp.route('/grupos/<grupo_id>/integrantes/<estudiante_id>/transferir', methods=['POST'])
@requiere_permiso(PERMISO_ESTUDIANTES_MODIFICAR)
def post_transferir(grupo_id, estudiante_id):
    """Mueve al alumno a otro equipo de la misma evaluación. Body: {grupo_destino_id}."""
    body = request.get_json(silent=True) or {}

    try:
        destino = validar_minimo(validar_entero(body.get('grupo_destino_id'), 'grupo_destino_id'), 1, 'grupo_destino_id')
        resultado = transferir_integrante(grupo_id, estudiante_id, destino)
    except ValueError as error:
        return _error(error)

    return jsonify(resultado)
