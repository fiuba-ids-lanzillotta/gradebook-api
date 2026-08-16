from ..config import CACHE_TTL_ITEMS_SEGUNDOS
from ..constants import ERROR_CODE_ITEM_NOT_FOUND, ERROR_CODE_NOMBRE_DUPLICADO
from ..utils import construir_error_api
from ..validators.items import validar_body_item
from .. import db, cache

# Clave de cache de las filas de items.
_CACHE_ITEMS = 'items:filas'


def construir_item_dto(item: dict) -> dict:
    """DTO público de un item."""
    return {
        'id':          item['id'],
        'nombre':      item['nombre'],
        'descripcion': item['descripcion'],
        'activo':      item['activo'],
    }


def listar_items() -> list[dict]:
    """
    Retorna todos los items ordenados por id.

    Las filas se cachean en Redis (cache-aside) y se invalidan en cada escritura.
    """
    filas = cache.obtener(_CACHE_ITEMS)
    if filas is None:
        filas = db.obtener_todos_los_items()
        cache.guardar(_CACHE_ITEMS, filas, CACHE_TTL_ITEMS_SEGUNDOS)

    return [construir_item_dto(item) for item in filas]


def buscar_item_por_id(item_id: int) -> dict:
    """Busca un item por id. Lanza ValueError 404 si no existe."""
    item = _obtener_item_o_404(item_id)

    return construir_item_dto(item)


def crear_item(body: dict) -> dict:
    """Valida el body e inserta un item. Lanza ValueError 409 si el nombre ya existe."""
    datos = validar_body_item(body)
    _validar_nombre_unico(datos['nombre'])

    nuevo_id = db.insertar_item(datos['nombre'], datos['descripcion'], datos['activo'])
    cache.invalidar(_CACHE_ITEMS)

    return buscar_item_por_id(nuevo_id)


def actualizar_item(item_id: int, body: dict) -> dict:
    """Valida el body y actualiza un item. Lanza ValueError 404 si no existe, 409 si el nombre choca."""
    _obtener_item_o_404(item_id)
    datos = validar_body_item(body)
    _validar_nombre_unico(datos['nombre'], excluir_id=item_id)

    db.actualizar_item(item_id, datos['nombre'], datos['descripcion'], datos['activo'])
    cache.invalidar(_CACHE_ITEMS)

    return buscar_item_por_id(item_id)


def eliminar_item_por_id(item_id: int) -> None:
    """Elimina un item por id, o lanza ValueError 404 si no existe."""
    _obtener_item_o_404(item_id)

    db.eliminar_item(item_id)
    cache.invalidar(_CACHE_ITEMS)


def _validar_nombre_unico(nombre: str, excluir_id: int | None = None) -> None:
    """
    Verifica que el nombre no esté usado por otro item (la columna es única).

    `excluir_id` permite ignorar al propio item en una actualización.
    Lanza ValueError 409 si ya está en uso.
    """
    otro = db.obtener_item_por_nombre(nombre)

    if otro and otro['id'] != excluir_id:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_NOMBRE_DUPLICADO,
            message='Nombre en uso',
            description=f"Ya existe un item con el nombre '{nombre}'"
        ), 409)


def _obtener_item_o_404(item_id: int) -> dict:
    """Retorna la fila cruda del item o lanza 404."""
    item = db.obtener_item_por_id(item_id)

    if not item:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_ITEM_NOT_FOUND,
            message='Item no encontrado',
            description=f"No existe un item con id '{item_id}'"
        ), 404)

    return item
