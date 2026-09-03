import csv
import io
from datetime import date

from ..constants import (
    CUATRIMESTRES,
    ESTADO_INSCRIPCION_DEFAULT,
    ESTADO_INSCRIPCION_CURSANDO,
    ESTADO_INSCRIPCION_BAJA,
    ERROR_CODE_ESTUDIANTE_NOT_FOUND,
    ERROR_CODE_EMAIL_DUPLICADO,
    ERROR_CODE_PADRON_DUPLICADO,
    ERROR_CODE_CSV_INVALIDO,
    ERROR_CODE_INVALID_CUATRIMESTRE,
    ERROR_CODE_CURSADA_VIGENTE_NOT_FOUND,
    ERROR_CODE_INSCRIPCION_NOT_FOUND,
    ERROR_CODE_REACTIVACION_INVALIDA,
)
from ..config import CACHE_TTL_ESTUDIANTES_SEGUNDOS
from ..utils import construir_error_api, hashear_password, validar_entero
from ..validators.estudiantes import validar_body_estudiante, validar_body_estado_inscripcion
from .. import db, cache

# Cache del listado por cursada. Como las claves varían por filtros/búsqueda, se
# usa un contador de versión: cada escritura lo incrementa e invalida todo el
# namespace de una (las claves viejas quedan huérfanas y expiran por TTL).
_CACHE_VERSION_KEY  = 'estudiantes:version'
_CACHE_VERSION_TTL  = 86400


def construir_estudiante_dto(estudiante: dict) -> dict:
    """DTO público de un estudiante (nunca expone el password_hash)."""
    return {
        'id':         estudiante['id'],
        'padron':     estudiante['padron'],
        'nombre':     estudiante['nombre'],
        'apellido':   estudiante['apellido'],
        'email':      estudiante['email'],
        'activo':     estudiante.get('activo', True),
        'created_at': estudiante.get('created_at'),
        'updated_at': estudiante.get('updated_at'),
    }


def listar_estudiantes_de_cursada(anio, cuatrimestre, nombre=None, apellido=None,
                                  padron=None, email=None, q=None) -> list[dict]:
    """
    Lista los estudiantes inscriptos en la cursada (anio + cuatrimestre).

    Búsqueda: `q` (término único, OR sobre el estudiante: numérico → padrón/email,
    alfabético → nombre/apellido/email) o filtros por campo nombre/apellido/padrón/email
    (coincidencia parcial, AND). Cada estudiante incluye sus datos + de la inscripción
    (recursa, estado) y el histórico de bajas (`motivos_baja`).
    """
    anio_validado   = validar_entero(anio, 'anio')
    cuatri_validado = _validar_cuatrimestre(cuatrimestre)

    clave = _clave_cache_listado(anio_validado, cuatri_validado, nombre, apellido, padron, email, q)
    cacheado = cache.obtener(clave)
    if cacheado is not None:
        return cacheado

    filas = db.buscar_inscripciones_de_cursada(
        anio_validado, cuatri_validado, nombre, apellido, padron, email, q
    )

    ids     = [fila['estudiantes']['id'] for fila in filas if fila.get('estudiantes')]
    historico = _historico_de_bajas(ids)

    dtos = [_construir_estudiante_inscripcion_dto(fila, historico)
            for fila in filas if fila.get('estudiantes')]
    dtos = sorted(dtos, key=lambda estudiante: (estudiante['apellido'] or '', estudiante['nombre'] or ''))

    cache.guardar(clave, dtos, CACHE_TTL_ESTUDIANTES_SEGUNDOS)

    return dtos


def _version_cache_estudiantes() -> int:
    version = cache.obtener(_CACHE_VERSION_KEY)

    return version if isinstance(version, int) else 1


def _invalidar_cache_estudiantes() -> None:
    """Invalida todo el listado cacheado incrementando la versión del namespace."""
    cache.guardar(_CACHE_VERSION_KEY, _version_cache_estudiantes() + 1, _CACHE_VERSION_TTL)


def _clave_cache_listado(anio, cuatrimestre, nombre, apellido, padron, email, q) -> str:
    partes = [anio, cuatrimestre, q or '', nombre or '', apellido or '', padron or '', email or '']

    return f'estudiantes:v{_version_cache_estudiantes()}:' + ':'.join(str(parte) for parte in partes)


def _validar_cuatrimestre(cuatrimestre) -> int:
    valor = validar_entero(cuatrimestre, 'cuatrimestre')

    if valor not in CUATRIMESTRES:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_INVALID_CUATRIMESTRE,
            message='Cuatrimestre inválido',
            description=f"El cuatrimestre debe ser uno de: {', '.join(str(c) for c in CUATRIMESTRES)}"
        ))

    return valor


def _historico_de_bajas(estudiante_ids: list[int]) -> dict:
    """Agrupa el histórico de bajas por estudiante: {id: [{anio, cuatrimestre, motivo}]}."""
    historico = {}

    for baja in db.buscar_bajas_de_estudiantes(estudiante_ids):
        cursada = baja.get('cursadas')
        if cursada:
            historico.setdefault(baja['estudiante_id'], []).append({
                'anio':         cursada['anio'],
                'cuatrimestre': cursada['cuatrimestre'],
                'motivo':       baja.get('motivo_baja'),
            })

    return historico


def _construir_estudiante_inscripcion_dto(fila: dict, historico: dict) -> dict:
    """DTO de estudiante + su inscripción en la cursada + histórico de bajas."""
    estudiante = fila['estudiantes']

    return {
        'id':           estudiante['id'],
        'padron':       estudiante['padron'],
        'nombre':       estudiante['nombre'],
        'apellido':     estudiante['apellido'],
        'email':        estudiante['email'],
        'recursa':      fila['recursa'],
        'estado':       fila['estado'],
        'motivos_baja': historico.get(estudiante['id'], []),
    }


def buscar_estudiante_por_id(estudiante_id: int) -> dict:
    """Busca un estudiante por id. Lanza ValueError 404 si no existe."""
    return construir_estudiante_dto(_obtener_estudiante_o_404(estudiante_id))


def crear_estudiante(body: dict) -> dict:
    """
    Valida el body, verifica padrón/email únicos, crea el estudiante y lo inscribe
    en la cursada vigente (estado 'cursando'; recursa según inscripciones previas).
    Lanza 409 si no hay cursada vigente.
    """
    datos = validar_body_estudiante(body, requiere_password=True)
    _validar_padron_unico(datos['padron'])
    _validar_email_unico(datos['email'])

    cursada = _cursada_vigente_o_error()

    nuevo_id = db.insertar_estudiante(
        datos['padron'], datos['nombre'], datos['apellido'], datos['email'],
        hashear_password(datos['password'])
    )

    # Estudiante nuevo: sin inscripciones previas → recursa = False.
    db.insertar_inscripcion(cursada['id'], nuevo_id, False, ESTADO_INSCRIPCION_DEFAULT)
    _invalidar_cache_estudiantes()

    return buscar_estudiante_por_id(nuevo_id)


def _cursada_vigente_o_error() -> dict:
    """Retorna la cursada vigente (según la fecha de hoy) o lanza ValueError 409."""
    cursada = db.obtener_cursada_vigente(date.today().isoformat())

    if not cursada:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_CURSADA_VIGENTE_NOT_FOUND,
            message='No hay cursada vigente',
            description='No existe una cursada cuyo período (fecha_inicio..fecha_fin) incluya la fecha actual.'
        ), 409)

    return cursada


def actualizar_estudiante(estudiante_id: int, body: dict) -> dict:
    """Valida el body y actualiza un estudiante. Si viene password, lo actualiza."""
    _obtener_estudiante_o_404(estudiante_id)
    datos = validar_body_estudiante(body, requiere_password=False)
    _validar_padron_unico(datos['padron'], excluir_id=estudiante_id)
    _validar_email_unico(datos['email'], excluir_id=estudiante_id)

    db.actualizar_estudiante(
        estudiante_id, datos['padron'], datos['nombre'], datos['apellido'], datos['email']
    )

    if datos['password']:
        db.actualizar_password_estudiante(estudiante_id, hashear_password(datos['password']))

    _invalidar_cache_estudiantes()

    return buscar_estudiante_por_id(estudiante_id)


def cambiar_estado_inscripcion(estudiante_id: int, body: dict) -> dict:
    """
    Cambia el estado de la inscripción del estudiante en la cursada vigente
    a 'baja' o 'abandono'. `motivo` sólo se guarda para 'baja'.

    Lanza 400 (body inválido), 409 (sin cursada vigente) o 404 (el estudiante no
    está inscripto en la cursada vigente).
    """
    datos   = validar_body_estado_inscripcion(body)
    cursada = _cursada_vigente_o_error()

    inscripcion = db.obtener_inscripcion(cursada['id'], estudiante_id)
    if not inscripcion:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_INSCRIPCION_NOT_FOUND,
            message='Inscripción no encontrada',
            description=f"El estudiante '{estudiante_id}' no está inscripto en la cursada vigente"
        ), 404)

    # El motivo sólo aplica a la baja; en cualquier otro estado se limpia.
    motivo = datos['motivo'] if datos['estado'] == ESTADO_INSCRIPCION_BAJA else None
    db.actualizar_estado_inscripcion(inscripcion['id'], datos['estado'], motivo)
    _invalidar_cache_estudiantes()

    return {
        'estudiante_id': estudiante_id,
        'cursada_id':    cursada['id'],
        'estado':        datos['estado'],
        'motivo_baja':   motivo,
    }


def reactivar_inscripcion(estudiante_id: int) -> dict:
    """
    Reactiva la inscripción de un estudiante en la cursada vigente.

    Solo está permitido si la inscripción actual está en estado 'baja'; en otro
    caso lanza 409. Lanza 404 si el estudiante no está inscripto en la cursada
    vigente, o 409 si no hay cursada vigente.
    """
    cursada = _cursada_vigente_o_error()

    inscripcion = db.obtener_inscripcion(cursada['id'], estudiante_id)
    if not inscripcion:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_INSCRIPCION_NOT_FOUND,
            message='Inscripción no encontrada',
            description=f"El estudiante '{estudiante_id}' no está inscripto en la cursada vigente"
        ), 404)

    if inscripcion['estado'] != ESTADO_INSCRIPCION_BAJA:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_REACTIVACION_INVALIDA,
            message='No se puede reactivar la inscripción',
            description='Solo se puede reactivar una inscripción cuyo estado sea baja.'
        ), 409)

    db.actualizar_estado_inscripcion(inscripcion['id'], ESTADO_INSCRIPCION_CURSANDO, None)
    _invalidar_cache_estudiantes()

    return {
        'estudiante_id': estudiante_id,
        'cursada_id':    cursada['id'],
        'estado':        ESTADO_INSCRIPCION_CURSANDO,
        'motivo_baja':   None,
    }


# ---------------------------------------------------------------
# Alta masiva por CSV (padrón de la cursada, export SIU)
# ---------------------------------------------------------------

def importar_estudiantes_csv(contenido: str) -> dict:
    """
    Da de alta estudiantes desde un CSV del detalle de inscripción (export SIU) y
    los inscribe en la cursada vigente.

    Formato (separador `;`, con cabecera): `Legajo`, `Alumno` ("Apellido, Nombre")
    y `Email` (admite el prefijo "Email Principal: "). El password inicial de un
    estudiante nuevo es su padrón. Los estudiantes que ya existen no se recrean,
    pero igual se inscriben en la cursada vigente (con `recursa=True` si ya tenían
    inscripción en otra cursada). Omite los ya inscriptos en la cursada vigente y
    reporta las filas inválidas. Requiere una cursada vigente (lanza 409 si no hay).

    Retorna `{estudiantes_creados, inscriptos, omitidos, errores}`.
    """
    filas, errores = _parsear_csv_estudiantes(contenido)

    if not filas and not errores:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_CSV_INVALIDO,
            message='CSV vacío o inválido',
            description="El CSV no tiene filas de estudiantes. Se espera separador ';' y cabecera con 'Legajo', 'Alumno' y 'Email'."
        ))

    cursada = _cursada_vigente_o_error()
    filas   = _deduplicar_filas(filas, omitidos := [])

    id_por_padron, id_por_email = _mapas_de_estudiantes()

    # Crear los estudiantes nuevos (los que no existen por padrón ni email).
    nuevos = [
        {
            'padron':        fila['padron'],
            'nombre':        fila['nombre'],
            'apellido':      fila['apellido'],
            'email':         fila['email'],
            'password_hash': hashear_password(fila['padron']),
        }
        for fila in filas
        if fila['padron'] not in id_por_padron and fila['email'].lower() not in id_por_email
    ]
    creados = db.insertar_estudiantes_bulk(nuevos)
    for estudiante in creados:
        id_por_padron[estudiante['padron']] = estudiante['id']

    # Resolver el id de cada fila e inscribir en la cursada vigente.
    ids_filas    = [id_por_padron.get(fila['padron']) or id_por_email[fila['email'].lower()] for fila in filas]
    inscripciones = db.obtener_inscripciones_de_estudiantes(ids_filas)
    ya_en_vigente = {i['estudiante_id'] for i in inscripciones if i['cursada_id'] == cursada['id']}
    en_otra       = {i['estudiante_id'] for i in inscripciones if i['cursada_id'] != cursada['id']}

    a_inscribir = []
    for fila, estudiante_id in zip(filas, ids_filas):
        if estudiante_id in ya_en_vigente:
            omitidos.append({'padron': fila['padron'], 'motivo': 'ya inscripto en la cursada vigente'})
        else:
            ya_en_vigente.add(estudiante_id)
            a_inscribir.append({
                'cursada_id':    cursada['id'],
                'estudiante_id': estudiante_id,
                'recursa':       estudiante_id in en_otra,
                'estado':        ESTADO_INSCRIPCION_DEFAULT,
            })

    inscriptos = db.insertar_inscripciones_bulk(a_inscribir)
    _invalidar_cache_estudiantes()

    return {
        'estudiantes_creados': len(creados),
        'inscriptos':          len(inscriptos),
        'omitidos':            omitidos,
        'errores':             errores,
    }


def _mapas_de_estudiantes() -> tuple[dict, dict]:
    """Retorna (id_por_padron, id_por_email) de los estudiantes existentes."""
    existentes    = db.obtener_todos_los_estudiantes()
    id_por_padron = {estudiante['padron']: estudiante['id'] for estudiante in existentes}
    id_por_email  = {(estudiante['email'] or '').lower(): estudiante['id'] for estudiante in existentes}

    return id_por_padron, id_por_email


def _deduplicar_filas(filas: list[dict], omitidos: list[dict]) -> list[dict]:
    """Descarta filas repetidas dentro del CSV (por padrón o email); las anota en omitidos."""
    vistos_padron = set()
    vistos_email  = set()
    unicas        = []

    for fila in filas:
        clave_email = fila['email'].lower()
        if fila['padron'] in vistos_padron or clave_email in vistos_email:
            omitidos.append({'padron': fila['padron'], 'motivo': 'duplicado en el archivo'})
        else:
            vistos_padron.add(fila['padron'])
            vistos_email.add(clave_email)
            unicas.append(fila)

    return unicas


def _limpiar_email(bruto: str) -> str:
    """Normaliza el email del export SIU (quita el prefijo 'Email Principal: ')."""
    bruto = (bruto or '').strip()
    if ':' in bruto:
        bruto = bruto.split(':', 1)[1]

    return bruto.strip()


def _parsear_csv_estudiantes(contenido: str) -> tuple[list[dict], list[dict]]:
    """
    Parsea el CSV y retorna (filas_validas, errores).

    filas_validas: [{padron, nombre, apellido, email}]. errores: [{fila, motivo}].
    """
    filas   = []
    errores = []
    lector  = csv.DictReader(io.StringIO(contenido), delimiter=';')

    for numero, registro in enumerate(lector, start=2):
        padron = (registro.get('Legajo') or '').strip()
        alumno = (registro.get('Alumno') or '').strip()
        email  = _limpiar_email(registro.get('Email') or '')

        if not padron or not alumno:
            errores.append({'fila': numero, 'motivo': 'Falta Legajo o Alumno'})
        elif ', ' not in alumno:
            errores.append({'fila': numero, 'motivo': f"Alumno sin formato 'Apellido, Nombre': {alumno}"})
        elif '@' not in email:
            errores.append({'fila': numero, 'motivo': f'Email inválido: {email}'})
        else:
            apellido, nombre = alumno.split(', ', 1)
            filas.append({
                'padron':   padron,
                'nombre':   nombre.strip(),
                'apellido': apellido.strip(),
                'email':    email,
            })

    return filas, errores


def _validar_email_unico(email: str, excluir_id: int | None = None) -> None:
    """Verifica que el email no esté usado por otro estudiante. Lanza 409 si ya está en uso."""
    otro = db.obtener_estudiante_por_email(email)

    if otro and otro['id'] != excluir_id:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_EMAIL_DUPLICADO,
            message='Email en uso',
            description=f"Ya existe un estudiante con el email '{email}'"
        ), 409)


def _validar_padron_unico(padron: str, excluir_id: int | None = None) -> None:
    """Verifica que el padrón no esté usado por otro estudiante. Lanza 409 si ya está en uso."""
    otro = db.obtener_estudiante_por_padron(padron)

    if otro and otro['id'] != excluir_id:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_PADRON_DUPLICADO,
            message='Padrón en uso',
            description=f"Ya existe un estudiante con el padrón '{padron}'"
        ), 409)


def _obtener_estudiante_o_404(estudiante_id: int) -> dict:
    """Retorna la fila del estudiante o lanza 404."""
    estudiante = db.obtener_estudiante_por_id(estudiante_id)

    if not estudiante:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_ESTUDIANTE_NOT_FOUND,
            message='Estudiante no encontrado',
            description=f"No existe un estudiante con id '{estudiante_id}'"
        ), 404)

    return estudiante

CSV_HEADER_ESTUDIANTES = ['Legajo', 'Alumno', 'Email']


def exportar_estudiantes_csv(anio, cuatrimestre) -> str:
    """
    Serializa los inscriptos de la cursada al mismo CSV que acepta el import
    (separador ';', cabecera Legajo / Alumno / Email).
    """
    estudiantes = listar_estudiantes_de_cursada(anio, cuatrimestre)
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=';', lineterminator='\r\n')
    writer.writerow(CSV_HEADER_ESTUDIANTES)

    for estudiante in estudiantes:
        alumno = f"{estudiante.get('apellido') or ''}, {estudiante.get('nombre') or ''}"
        writer.writerow([
            estudiante.get('padron') or '',
            alumno,
            estudiante.get('email') or '',
        ])

    return buffer.getvalue()