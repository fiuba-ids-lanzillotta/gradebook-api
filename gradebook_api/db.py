from supabase import create_client, Client

from .config import SUPABASE_URL, SUPABASE_KEY

# Cliente de Supabase compartido por toda la aplicación (habla PostgREST).
cliente: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ---------------------------------------------------------------
# Items (recurso de ejemplo)
# ---------------------------------------------------------------

CAMPOS_ITEM = 'id, nombre, descripcion, activo'


def obtener_todos_los_items() -> list[dict]:
    """Retorna todos los items ordenados por id."""
    return cliente.table('items').select(CAMPOS_ITEM).order('id').execute().data


def obtener_item_por_id(item_id: int) -> dict:
    """Retorna el item con el id dado, o un dict vacío si no existe."""
    filas = cliente.table('items').select(CAMPOS_ITEM).eq('id', item_id).execute().data

    return filas[0] if filas else {}


def obtener_item_por_nombre(nombre: str) -> dict:
    """Retorna el item con el nombre dado, o un dict vacío si no existe."""
    filas = cliente.table('items').select(CAMPOS_ITEM).eq('nombre', nombre).execute().data

    return filas[0] if filas else {}


def insertar_item(nombre: str, descripcion: str, activo: bool) -> int:
    """Inserta un nuevo item y retorna el id generado."""
    filas = cliente.table('items').insert({
        'nombre':      nombre,
        'descripcion': descripcion,
        'activo':      activo,
    }).execute().data

    return filas[0]['id']


def actualizar_item(item_id: int, nombre: str, descripcion: str, activo: bool) -> int:
    """Actualiza un item por id. Retorna la cantidad de filas afectadas."""
    filas = cliente.table('items').update({
        'nombre':      nombre,
        'descripcion': descripcion,
        'activo':      activo,
    }).eq('id', item_id).execute().data

    return len(filas)


def eliminar_item(item_id: int) -> int:
    """Elimina un item por id. Retorna la cantidad de filas afectadas."""
    filas = cliente.table('items').delete().eq('id', item_id).execute().data

    return len(filas)
