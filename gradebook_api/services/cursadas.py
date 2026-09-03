"""Cursos/cursadas: listado, alta y modificación."""
from datetime import date

from ..constants import (
    CUATRIMESTRES,
    ERROR_CODE_INVALID_CUATRIMESTRE,
    ERROR_CODE_MATERIA_NOT_FOUND,
    ERROR_CODE_CURSADA_NOT_FOUND,
    ERROR_CODE_CURSADA_DUPLICADA,
)
from ..config import CACHE_TTL_CURSADAS_SEGUNDOS
from ..utils import construir_error_api, validar_entero, validar_minimo
from ..validators.cursadas import validar_body_cursada
from .. import db, cache

# Cache del listado de cursadas. Como las claves varían por filtros, se usa un
# contador de versión: cada escritura lo incrementa e invalida todo el namespace.
_CACHE_VERSION_KEY = 'cursadas:version'
_CACHE_VERSION_TTL = 86400


def listar_cursadas(codigo=None, anio=None, cuatrimestre=None) -> list[dict]:
    """
    Lista las cursadas (con su materia), filtrando opcionalmente por código de
    materia (parcial), año y cuatrimestre.

    Cada item: {id, codigo, nombre, anio, cuatrimestre, fecha_inicio, fecha_fin, vigente}.
    `vigente` indica si la cursada está transcurriendo hoy (inicio ≤ hoy ≤ fin).
    """
    anio_validado   = _validar_anio(anio)
    cuatri_validado = _validar_cuatrimestre(cuatrimestre)
    codigo_filtro   = (codigo or '').strip() or None

    clave = _clave_cache_listado(codigo_filtro, anio_validado, cuatri_validado)
    filas = cache.obtener(clave)
    if filas is None:
        filas = db.buscar_cursadas(codigo_filtro, anio_validado, cuatri_validado)
        cache.guardar(clave, filas, CACHE_TTL_CURSADAS_SEGUNDOS)

    hoy = date.today().isoformat()

    return [_construir_curso_dto(fila, hoy) for fila in filas if fila.get('materias')]


def crear_cursada(body: dict) -> dict:
    """
    Crea una cursada. Si la materia (codigo) no existe, la crea con el nombre
    dado. Lanza 409 si ya existe una cursada para esa materia/año/cuatrimestre.
    """
    datos   = validar_body_cursada(body)
    materia = _obtener_o_crear_materia(datos['codigo'], datos['nombre'])

    _validar_cursada_unica(materia['id'], datos['anio'], datos['cuatrimestre'])

    cursada = db.insertar_cursada(
        materia['id'],
        datos['anio'],
        datos['cuatrimestre'],
        datos['fecha_inicio'],
        datos['fecha_fin'],
    )

    _invalidar_cache_cursadas()

    return _construir_curso_dto_con_materia(cursada, materia)


def actualizar_cursada(cursada_id: int, body: dict) -> dict:
    """
    Actualiza una cursada existente. El codigo debe corresponder a la materia
    asignada (no se permite cambiar la materia por este endpoint). Lanza 404 si
    no existe la cursada o la materia, y 409 si el nuevo año/cuatrimestre ya
    está ocupado por otra cursada de la misma materia.
    """
    cursada_id = validar_minimo(validar_entero(cursada_id, 'id'), 1, 'id')
    datos      = validar_body_cursada(body)

    cursada = db.obtener_cursada_por_id(cursada_id)
    if not cursada:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_CURSADA_NOT_FOUND,
            message='Cursada no encontrada',
            description=f"No existe una cursada con id '{cursada_id}'"
        ), 404)

    materia = db.obtener_materia_por_codigo(datos['codigo'])
    if not materia:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_MATERIA_NOT_FOUND,
            message='Materia no encontrada',
            description=f"No existe una materia con código '{datos['codigo']}'"
        ), 404)

    if materia['id'] != cursada['materia_id']:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_CURSADA_NOT_FOUND,
            message='Código de materia no coincide',
            description='No se puede cambiar la materia de una cursada existente.'
        ), 400)

    if materia.get('nombre') != datos['nombre']:
        db.actualizar_materia(materia['id'], {'nombre': datos['nombre']})
        materia['nombre'] = datos['nombre']

    _validar_cursada_unica(materia['id'], datos['anio'], datos['cuatrimestre'],
                           excluir_cursada_id=cursada_id)

    cursada_actualizada = db.actualizar_cursada(cursada_id, {
        'anio':         datos['anio'],
        'cuatrimestre': datos['cuatrimestre'],
        'fecha_inicio': datos['fecha_inicio'],
        'fecha_fin':    datos['fecha_fin'],
    })

    _invalidar_cache_cursadas()

    return _construir_curso_dto_con_materia(cursada_actualizada, materia)


def _obtener_o_crear_materia(codigo: str, nombre: str) -> dict:
    materia = db.obtener_materia_por_codigo(codigo)

    if materia:
        if materia.get('nombre') != nombre:
            db.actualizar_materia(materia['id'], {'nombre': nombre})
            materia['nombre'] = nombre

        return materia

    return db.insertar_materia(codigo, nombre, None)


def _validar_cursada_unica(materia_id: int, anio: int, cuatrimestre: int,
                           excluir_cursada_id: int | None = None) -> None:
    existente = db.obtener_cursada_por_materia_anio_cuatri(materia_id, anio, cuatrimestre)

    if existente and existente['id'] != excluir_cursada_id:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_CURSADA_DUPLICADA,
            message='Cursada duplicada',
            description=f"Ya existe una cursada de la materia '{materia_id}' para el año {anio}C{cuatrimestre}."
        ), 409)


def _validar_anio(anio):
    if anio is None or str(anio).strip() == '':
        return None

    return validar_entero(anio, 'anio')


def _validar_cuatrimestre(cuatrimestre):
    if cuatrimestre is None or str(cuatrimestre).strip() == '':
        return None

    valor = validar_entero(cuatrimestre, 'cuatrimestre')

    if valor not in CUATRIMESTRES:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_INVALID_CUATRIMESTRE,
            message='Cuatrimestre inválido',
            description=f"El cuatrimestre debe ser uno de: {', '.join(str(c) for c in CUATRIMESTRES)}"
        ))

    return valor


def _version_cache_cursadas() -> int:
    version = cache.obtener(_CACHE_VERSION_KEY)

    return version if isinstance(version, int) else 1


def _invalidar_cache_cursadas() -> None:
    cache.guardar(_CACHE_VERSION_KEY, _version_cache_cursadas() + 1, _CACHE_VERSION_TTL)


def _clave_cache_listado(codigo: str | None, anio: int | None, cuatrimestre: int | None) -> str:
    partes = [
        _version_cache_cursadas(),
        codigo or '',
        anio if anio is not None else '',
        cuatrimestre if cuatrimestre is not None else '',
    ]

    return f'cursadas:v{partes[0]}:' + ':'.join(str(parte) for parte in partes[1:])


def _construir_curso_dto(fila: dict, hoy: str) -> dict:
    materia = fila['materias']

    return _construir_curso_dto_con_materia(fila, materia, hoy)


def _construir_curso_dto_con_materia(fila: dict, materia: dict, hoy: str | None = None) -> dict:
    if hoy is None:
        hoy = date.today().isoformat()

    return {
        'id':           fila['id'],
        'codigo':       materia['codigo'],
        'nombre':       materia['nombre'],
        'anio':         fila['anio'],
        'cuatrimestre': fila['cuatrimestre'],
        'fecha_inicio': fila['fecha_inicio'],
        'fecha_fin':    fila['fecha_fin'],
        'vigente':      fila['fecha_inicio'] <= hoy <= fila['fecha_fin'],
    }
