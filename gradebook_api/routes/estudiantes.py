from flask import Blueprint, jsonify, request, Response

from ..constants import (
    PERMISO_ESTUDIANTES_LEER,
    PERMISO_ESTUDIANTES_CREAR,
    PERMISO_ESTUDIANTES_MODIFICAR,
    PERMISO_ESTUDIANTES_ELIMINAR,
    PERMISO_ESTUDIANTES_REACTIVAR,
    PERMISO_PERMISOS_ASIGNAR,
    ERROR_CODE_ARCHIVO_FALTANTE,
)

from ..utils import (
    requiere_permiso,
    construir_error_api,
    validar_entero,
    validar_minimo,
    validar_params_paginacion,
    sin_cache,
)
from ..services.estudiantes import (
    listar_estudiantes_de_cursada,
    buscar_estudiante_por_id,
    crear_estudiante,
    actualizar_estudiante,
    cambiar_estado_inscripcion,
    reactivar_inscripcion,
    importar_estudiantes_csv,
    exportar_estudiantes_csv,
)
from ..pagination import construir_respuesta_paginada
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

    Query params: `anio` y `cuatrimestre` (obligatorios); búsqueda `q` (término
    único, OR sobre el estudiante) o filtros por campo `nombre`/`apellido`/`padron`/
    `email` (coincidencia parcial); paginación `_offset` / `_limit`. La respuesta
    incluye `_links` (HATEOAS).
    """
    args = request.args

    try:
        paginacion  = validar_params_paginacion(args.to_dict())
        estudiantes = listar_estudiantes_de_cursada(
            args.get('anio'),
            args.get('cuatrimestre'),
            nombre=args.get('nombre'),
            apellido=args.get('apellido'),
            padron=args.get('padron'),
            email=args.get('email'),
            q=args.get('q'),
        )
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    if not estudiantes:
        return '', 204

    offset, limit = paginacion['offset'], paginacion['limit']
    pagina = estudiantes[offset: offset + limit]

    respuesta = construir_respuesta_paginada(
        datos={'estudiantes': pagina},
        total=len(estudiantes),
        offset=offset,
        limit=limit,
        base_url=request.base_url,
        params=args.to_dict(),
    )

    return jsonify(respuesta)


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
@requiere_permiso(PERMISO_ESTUDIANTES_CREAR)
def post_estudiante():
    body = request.get_json(silent=True)

    try:
        estudiante = crear_estudiante(body)
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return jsonify(estudiante), 201

@estudiantes_bp.route('/estudiantes/csv', methods=['GET'])
@requiere_permiso(PERMISO_ESTUDIANTES_LEER)
def get_estudiantes_csv():
    """Exporta el padrón de la cursada (anio + cuatrimestre) como CSV SIU."""
    args = request.args

    try:
        contenido = exportar_estudiantes_csv(args.get('anio'), args.get('cuatrimestre'))
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400
        return jsonify(error.args[0]), status

    anio = args.get('anio', '')
    cuatri = args.get('cuatrimestre', '')
    nombre = f'alumnos-{anio}-C{cuatri}.csv'

    return sin_cache(Response(
        contenido,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{nombre}"'},
    ))

@estudiantes_bp.route('/estudiantes/csv', methods=['POST'])
@requiere_permiso(PERMISO_ESTUDIANTES_CREAR)
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

@estudiantes_bp.route('/estudiantes/<estudiante_id>', methods=['PUT'])
@requiere_permiso(PERMISO_ESTUDIANTES_MODIFICAR)
def put_estudiante(estudiante_id):
    body = request.get_json(silent=True)

    try:
        id_validado = validar_minimo(validar_entero(estudiante_id, 'id'), 1, 'id')
        estudiante = actualizar_estudiante(id_validado, body)
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return jsonify(estudiante)

@estudiantes_bp.route('/estudiantes/<estudiante_id>/baja', methods=['POST'])
@requiere_permiso(PERMISO_ESTUDIANTES_ELIMINAR)
def post_baja_estudiante(estudiante_id):
    """
    Baja lógica: cambia el estado de la inscripción del estudiante en la cursada
    vigente a 'baja' o 'abandono'. Body: {estado, motivo}. El `motivo` es
    obligatorio sólo cuando `estado` es 'baja'.
    """
    body = request.get_json(silent=True)

    try:
        id_validado = validar_minimo(validar_entero(estudiante_id, 'id'), 1, 'id')
        resultado = cambiar_estado_inscripcion(id_validado, body)
    except ValueError as error:
        status = error.args[1] if len(error.args) > 1 else 400

        return jsonify(error.args[0]), status

    return jsonify(resultado)


@estudiantes_bp.route('/estudiantes/<estudiante_id>/reactivacion', methods=['POST'])
@requiere_permiso(PERMISO_ESTUDIANTES_REACTIVAR)
def post_reactivar_estudiante(estudiante_id):
    """
    Reactiva la inscripción del estudiante en la cursada vigente. Requiere que
    la inscripción esté en estado 'baja' (permiso estudiantes.reactivar).
    """
    try:
        id_validado = validar_minimo(validar_entero(estudiante_id, 'id'), 1, 'id')
        resultado = reactivar_inscripcion(id_validado)
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
