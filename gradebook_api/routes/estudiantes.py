from flask import Blueprint, jsonify, request

from ..constants import (
    PERMISO_ESTUDIANTES_LEER,
    PERMISO_ESTUDIANTES_GESTIONAR,
    PERMISO_PERMISOS_ASIGNAR,
    ERROR_CODE_ARCHIVO_FALTANTE,
)
from ..utils import requiere_permiso, construir_error_api, validar_entero, validar_minimo
from ..services.estudiantes import (
    listar_estudiantes_de_cursada,
    buscar_estudiante_por_id,
    crear_estudiante,
    actualizar_estudiante,
    cambiar_estado_inscripcion,
    importar_estudiantes_csv,
)
from ..services.permisos import asignar_overrides_estudiante

estudiantes_bp = Blueprint('estudiantes', __name__)

# Nombre del campo del formulario multipart donde viaja el archivo CSV.
CAMPO_ARCHIVO_CSV = 'archivo'


def _decodificar(datos: bytes) -> str:
    """Decodifica el CSV: intenta UTF-8 (con BOM) y cae a cp1252 (export SIU)."""
    try:
        return datos.decode('utf-8-sig')
    except UnicodeDecodeError:
        return datos.decode('cp1252', errors='replace')


@estudiantes_bp.route('/estudiantes', methods=['GET'])
@requiere_permiso(PERMISO_ESTUDIANTES_LEER)
def get_estudiantes():
    """
    Lista los estudiantes inscriptos en una cursada. Requiere estudiantes.leer.

    Query params: `anio` y `cuatrimestre` (obligatorios) y filtros opcionales
    `nombre`, `apellido`, `padron`, `email` (coincidencia parcial).
    """
    args = request.args

    try:
        estudiantes = listar_estudiantes_de_cursada(
            args.get('anio'),
            args.get('cuatrimestre'),
            nombre=args.get('nombre'),
            apellido=args.get('apellido'),
            padron=args.get('padron'),
            email=args.get('email'),
        )
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return jsonify(estudiantes)


@estudiantes_bp.route('/estudiantes/<estudiante_id>', methods=['GET'])
@requiere_permiso(PERMISO_ESTUDIANTES_LEER)
def get_estudiante(estudiante_id):
    try:
        id_validado = validar_minimo(validar_entero(estudiante_id, 'id'), 1, 'id')
        estudiante = buscar_estudiante_por_id(id_validado)
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return jsonify(estudiante)


@estudiantes_bp.route('/estudiantes', methods=['POST'])
@requiere_permiso(PERMISO_ESTUDIANTES_GESTIONAR)
def post_estudiante():
    body = request.get_json(silent=True)

    try:
        estudiante = crear_estudiante(body)
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return jsonify(estudiante), 201


@estudiantes_bp.route('/estudiantes/<estudiante_id>', methods=['PUT'])
@requiere_permiso(PERMISO_ESTUDIANTES_GESTIONAR)
def put_estudiante(estudiante_id):
    body = request.get_json(silent=True)

    try:
        id_validado = validar_minimo(validar_entero(estudiante_id, 'id'), 1, 'id')
        estudiante = actualizar_estudiante(id_validado, body)
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return jsonify(estudiante)


@estudiantes_bp.route('/estudiantes/csv', methods=['POST'])
@requiere_permiso(PERMISO_ESTUDIANTES_GESTIONAR)
def post_estudiantes_csv():
    """Alta masiva de estudiantes desde un CSV (export SIU). Password inicial = padrón."""
    archivo = request.files.get(CAMPO_ARCHIVO_CSV)

    if archivo is None:
        return jsonify(construir_error_api(
            code=ERROR_CODE_ARCHIVO_FALTANTE,
            message='Archivo CSV faltante',
            description=f"Debe enviarse el CSV como archivo en el campo '{CAMPO_ARCHIVO_CSV}' (multipart/form-data)"
        )), 400

    try:
        resultado = importar_estudiantes_csv(_decodificar(archivo.read()))
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return jsonify(resultado), 201


@estudiantes_bp.route('/estudiantes/<estudiante_id>/baja', methods=['POST'])
@requiere_permiso(PERMISO_ESTUDIANTES_GESTIONAR)
def post_baja_estudiante(estudiante_id):
    """
    Baja lógica: cambia el estado de la inscripción del estudiante en la cursada
    vigente (baja / abandono / reactivación). Body: {estado, motivo}. El `motivo`
    es obligatorio sólo cuando `estado` es 'baja'.
    """
    body = request.get_json(silent=True)

    try:
        id_validado = validar_minimo(validar_entero(estudiante_id, 'id'), 1, 'id')
        resultado = cambiar_estado_inscripcion(id_validado, body)
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return jsonify(resultado)


@estudiantes_bp.route('/estudiantes/<estudiante_id>/permisos', methods=['PUT'])
@requiere_permiso(PERMISO_PERMISOS_ASIGNAR)
def put_estudiante_permisos(estudiante_id):
    """Reemplaza los overrides de permisos del estudiante."""
    body = request.get_json(silent=True)

    try:
        id_validado = validar_minimo(validar_entero(estudiante_id, 'id'), 1, 'id')
        resultado = asignar_overrides_estudiante(id_validado, body)
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return jsonify(resultado)
