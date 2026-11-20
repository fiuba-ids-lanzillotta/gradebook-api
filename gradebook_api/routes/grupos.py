"""Equipos de una evaluación grupal."""
from flask import Blueprint, jsonify, request

from ..constants import PERMISO_ESTUDIANTES_LEER, PERMISO_ESTUDIANTES_MODIFICAR
from ..utils import requiere_permiso, validar_entero, validar_minimo
from ..services.grupos import (
    agregar_integrante,
    asignar_tutores,
    detalle,
    echar_integrante,
    listar_de_cursada,
    renombrar,
    transferir_integrante,
)

grupos_bp = Blueprint('grupos', __name__)


def _error(error: ValueError):
    status = error.args[1] if len(error.args) > 1 else 400

    return jsonify(error.args[0]), status


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
