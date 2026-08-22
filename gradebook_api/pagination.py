"""
Paginación con links HATEOAS (mismo patrón que el resto de los proyectos del workspace).

Los query params son `_offset` y `_limit`. La respuesta agrega `_links` con las
relaciones `_first`, `_prev`, `_next`, `_last` según la posición en la colección.
"""
from urllib.parse import urlencode

# Nombre de cada relación en los links HATEOAS
NOMBRE_LINKS = {
    'PRIMERO':   '_first',
    'ANTERIOR':  '_prev',
    'SIGUIENTE': '_next',
    'ULTIMO':    '_last',
}

# Params de paginación que se quitan de la query string al armar los links, para
# no duplicarlos en las URLs navegables.
PARAMS_PAGINACION = {'_offset', '_limit'}


def construir_link(tipo_link: str, offset: int, limit: int, base_url: str, params: dict) -> tuple:
    """Construye un link de paginación (HATEOAS) con el offset y limit indicados."""
    params_filtrados = {clave: valor for clave, valor in params.items() if clave not in PARAMS_PAGINACION}
    params_filtrados['_offset'] = offset
    params_filtrados['_limit']  = limit

    return NOMBRE_LINKS[tipo_link], {'href': f'{base_url}?{urlencode(params_filtrados)}'}


def construir_links_paginacion(offset: int, limit: int, total: int, base_url: str, params: dict) -> dict:
    """Genera los links de paginación disponibles según la posición actual en la colección."""
    links = {}

    rel, link = construir_link('PRIMERO', 0, limit, base_url, params)
    links[rel] = link

    if offset > 0:
        rel, link = construir_link('ANTERIOR', max(offset - limit, 0), limit, base_url, params)
        links[rel] = link

    if offset + limit < total:
        rel, link = construir_link('SIGUIENTE', offset + limit, limit, base_url, params)
        links[rel] = link

    offset_ultimo = 0 if total == 0 else ((total - 1) // limit) * limit

    if offset < offset_ultimo:
        rel, link = construir_link('ULTIMO', offset_ultimo, limit, base_url, params)
        links[rel] = link

    return links


def construir_respuesta_paginada(datos: dict, total: int, offset: int, limit: int,
                                 base_url: str, params: dict) -> dict:
    """
    Construye la respuesta paginada con los datos y los links HATEOAS.

    `datos` es un dict con una única key cuyo valor es la lista de resultados
    (ej. `{'estudiantes': [...]}`).
    """
    if not isinstance(datos, dict) or len(datos) != 1:
        raise ValueError("'datos' debe ser un dict con exactamente una sola key")

    nombre_coleccion, lista_datos = next(iter(datos.items()))

    return {
        nombre_coleccion: lista_datos,
        '_links': construir_links_paginacion(offset, limit, total, base_url, params),
    }
