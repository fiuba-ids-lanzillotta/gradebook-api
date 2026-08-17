from ..config import CACHE_TTL_ROLES_SEGUNDOS
from ..constants import (
    ERROR_CODE_ROL_NOT_FOUND,
    ERROR_CODE_PERMISO_NOT_FOUND,
    ERROR_CODE_DOCENTE_NOT_FOUND,
    ERROR_CODE_ESTUDIANTE_NOT_FOUND,
)
from ..utils import construir_error_api
from ..validators.permisos import validar_body_permisos_rol, validar_body_overrides
from .. import db, cache

# Claves de cache (cache-aside con invalidación al escribir). La lista completa
# de roles y, por separado, la matriz de permisos de cada rol (usada en el
# hot-path de resolución de permisos por request).
_CACHE_ROLES_LISTA = 'roles:lista'


def _cache_key_permisos_rol(codigo: str) -> str:
    return f'roles:permisos:{codigo}'


# ---------------------------------------------------------------
# Roles y catálogo de permisos
# ---------------------------------------------------------------

def listar_roles() -> list[dict]:
    """Retorna los roles con la lista de códigos de permiso que tiene cada uno (cacheado)."""
    cacheado = cache.obtener(_CACHE_ROLES_LISTA)
    if cacheado is not None:
        return cacheado

    roles = [
        {
            'codigo':      rol['codigo'],
            'nombre':      rol['nombre'],
            'descripcion': rol['descripcion'],
            'permisos':    db.obtener_codigos_permisos_de_rol(rol['id']),
        }
        for rol in db.obtener_todos_los_roles()
    ]
    cache.guardar(_CACHE_ROLES_LISTA, roles, CACHE_TTL_ROLES_SEGUNDOS)

    return roles


def codigos_permisos_de_rol(codigo_rol: str) -> list[str]:
    """
    Retorna los códigos de permiso de un rol (cacheado por rol).

    Se usa en la resolución de permisos efectivos de cada request; el cache se
    invalida cuando se cambian los permisos del rol.
    """
    clave    = _cache_key_permisos_rol(codigo_rol)
    cacheado = cache.obtener(clave)
    if cacheado is not None:
        return cacheado

    rol     = db.obtener_rol_por_codigo(codigo_rol)
    codigos = db.obtener_codigos_permisos_de_rol(rol['id']) if rol else []
    cache.guardar(clave, codigos, CACHE_TTL_ROLES_SEGUNDOS)

    return codigos


def listar_permisos() -> list[dict]:
    """Retorna el catálogo de permisos (código + descripción)."""
    return [
        {'codigo': permiso['codigo'], 'descripcion': permiso['descripcion']}
        for permiso in db.obtener_todos_los_permisos()
    ]


def asignar_permisos_a_rol(codigo_rol: str, body: dict) -> dict:
    """Reemplaza el conjunto de permisos de un rol (nivel general)."""
    rol     = _obtener_rol_o_404(codigo_rol)
    codigos = validar_body_permisos_rol(body)
    ids     = _resolver_permiso_ids(codigos)

    db.reemplazar_permisos_de_rol(rol['id'], ids)
    cache.invalidar(_CACHE_ROLES_LISTA, _cache_key_permisos_rol(rol['codigo']))

    return {
        'codigo':   rol['codigo'],
        'permisos': db.obtener_codigos_permisos_de_rol(rol['id']),
    }


# ---------------------------------------------------------------
# Overrides por persona
# ---------------------------------------------------------------

def asignar_overrides_docente(docente_id: int, body: dict) -> dict:
    """Reemplaza los overrides de permisos de un docente."""
    if not db.obtener_docente_por_id(docente_id):
        raise ValueError(construir_error_api(
            code=ERROR_CODE_DOCENTE_NOT_FOUND,
            message='Docente no encontrado',
            description=f"No existe un docente con id '{docente_id}'"
        ), 404)

    filas = _resolver_overrides(validar_body_overrides(body))
    db.reemplazar_overrides_docente(docente_id, filas)

    return {'docente_id': docente_id, 'permisos': db.obtener_overrides_docente(docente_id)}


def asignar_overrides_estudiante(estudiante_id: int, body: dict) -> dict:
    """Reemplaza los overrides de permisos de un estudiante."""
    if not db.obtener_estudiante_por_id(estudiante_id):
        raise ValueError(construir_error_api(
            code=ERROR_CODE_ESTUDIANTE_NOT_FOUND,
            message='Estudiante no encontrado',
            description=f"No existe un estudiante con id '{estudiante_id}'"
        ), 404)

    filas = _resolver_overrides(validar_body_overrides(body))
    db.reemplazar_overrides_estudiante(estudiante_id, filas)

    return {'estudiante_id': estudiante_id, 'permisos': db.obtener_overrides_estudiante(estudiante_id)}


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

def _obtener_rol_o_404(codigo_rol: str) -> dict:
    rol = db.obtener_rol_por_codigo(codigo_rol)

    if not rol:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_ROL_NOT_FOUND,
            message='Rol no encontrado',
            description=f"No existe un rol con código '{codigo_rol}'"
        ), 404)

    return rol


def _mapa_codigo_a_id(codigos: list[str]) -> dict:
    """Resuelve códigos de permiso a sus ids. Lanza 404 si alguno no existe."""
    encontrados = {permiso['codigo']: permiso['id'] for permiso in db.obtener_permisos_por_codigos(codigos)}
    faltantes   = [codigo for codigo in codigos if codigo not in encontrados]

    if faltantes:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_PERMISO_NOT_FOUND,
            message='Permiso inexistente',
            description=f"Códigos de permiso no válidos: {', '.join(faltantes)}"
        ), 404)

    return encontrados


def _resolver_permiso_ids(codigos: list[str]) -> list[int]:
    mapa = _mapa_codigo_a_id(codigos)

    return [mapa[codigo] for codigo in codigos]


def _resolver_overrides(overrides: list[dict]) -> list[dict]:
    """Convierte [{codigo, concedido}] en [{permiso_id, concedido}]."""
    mapa = _mapa_codigo_a_id([override['codigo'] for override in overrides])

    return [{'permiso_id': mapa[override['codigo']], 'concedido': override['concedido']}
            for override in overrides]
