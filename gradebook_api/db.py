from datetime import datetime, timezone

from supabase import create_client, Client

from .config import SUPABASE_URL, SUPABASE_KEY

# Cliente de Supabase compartido por toda la aplicación (habla PostgREST).
cliente: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def _ahora_iso() -> str:
    """Timestamp actual en ISO-8601 (UTC). La API mantiene `updated_at` (no hay trigger en la base)."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------
# Roles y permisos (RBAC)
# ---------------------------------------------------------------

CAMPOS_ROL     = 'id, codigo, nombre, descripcion'
CAMPOS_PERMISO = 'id, codigo, descripcion'


def obtener_todos_los_roles() -> list[dict]:
    """Retorna el catálogo de roles ordenado por id."""
    return cliente.table('roles').select(CAMPOS_ROL).order('id').execute().data


def obtener_rol_por_codigo(codigo: str) -> dict:
    """Retorna el rol con el código dado, o un dict vacío si no existe."""
    filas = cliente.table('roles').select(CAMPOS_ROL).eq('codigo', codigo).execute().data

    return filas[0] if filas else {}


def obtener_todos_los_permisos() -> list[dict]:
    """Retorna el catálogo de permisos ordenado por código."""
    return cliente.table('permisos').select(CAMPOS_PERMISO).order('codigo').execute().data


def obtener_permisos_por_codigos(codigos: list[str]) -> list[dict]:
    """Retorna los permisos cuyos códigos están en la lista dada."""
    if not codigos:
        return []

    return cliente.table('permisos').select(CAMPOS_PERMISO).in_('codigo', codigos).execute().data


def obtener_codigos_permisos_de_rol(rol_id: int) -> list[str]:
    """Retorna los códigos de permiso asociados a un rol (matriz roles_permisos)."""
    filas = cliente.table('roles_permisos').select('permisos(codigo)').eq('rol_id', rol_id).execute().data

    return [fila['permisos']['codigo'] for fila in filas if fila.get('permisos')]


def reemplazar_permisos_de_rol(rol_id: int, permiso_ids: list[int]) -> None:
    """Reemplaza el conjunto de permisos de un rol (borra e inserta)."""
    cliente.table('roles_permisos').delete().eq('rol_id', rol_id).execute()

    if permiso_ids:
        cliente.table('roles_permisos').insert(
            [{'rol_id': rol_id, 'permiso_id': permiso_id} for permiso_id in permiso_ids]
        ).execute()


# ---------------------------------------------------------------
# Docentes
# ---------------------------------------------------------------

CAMPOS_DOCENTE      = 'id, nombre, apellido, email, rol, foto, activo, created_at, updated_at'
CAMPOS_DOCENTE_AUTH = CAMPOS_DOCENTE + ', password_hash'


def obtener_todos_los_docentes() -> list[dict]:
    """Retorna todos los docentes ordenados por apellido."""
    return cliente.table('docentes').select(CAMPOS_DOCENTE).order('apellido').execute().data


def obtener_docente_por_id(docente_id: int) -> dict:
    """Retorna el docente con el id dado, o un dict vacío si no existe."""
    filas = cliente.table('docentes').select(CAMPOS_DOCENTE).eq('id', docente_id).execute().data

    return filas[0] if filas else {}


def obtener_docente_por_email(email: str) -> dict:
    """Retorna el docente con el email dado (incluye password_hash, para login)."""
    filas = cliente.table('docentes').select(CAMPOS_DOCENTE_AUTH).eq('email', email).execute().data

    return filas[0] if filas else {}


def insertar_docente(nombre: str, apellido: str, email: str, rol: str,
                     foto: str, password_hash: str) -> int:
    """Inserta un nuevo docente y retorna el id generado."""
    filas = cliente.table('docentes').insert({
        'nombre':        nombre,
        'apellido':      apellido,
        'email':         email,
        'rol':           rol,
        'foto':          foto,
        'password_hash': password_hash,
    }).execute().data

    return filas[0]['id']


def actualizar_docente(docente_id: int, nombre: str, apellido: str,
                       email: str, rol: str, foto: str) -> int:
    """Actualiza los datos de perfil de un docente (no el password)."""
    filas = cliente.table('docentes').update({
        'nombre':     nombre,
        'apellido':   apellido,
        'email':      email,
        'rol':        rol,
        'foto':       foto,
        'updated_at': _ahora_iso(),
    }).eq('id', docente_id).execute().data

    return len(filas)


def actualizar_password_docente(docente_id: int, password_hash: str) -> int:
    """Actualiza el password_hash de un docente."""
    filas = cliente.table('docentes').update(
        {'password_hash': password_hash, 'updated_at': _ahora_iso()}
    ).eq('id', docente_id).execute().data

    return len(filas)


def eliminar_docente(docente_id: int) -> int:
    """Elimina un docente por id. Retorna la cantidad de filas afectadas."""
    filas = cliente.table('docentes').delete().eq('id', docente_id).execute().data

    return len(filas)


def obtener_overrides_docente(docente_id: int) -> list[dict]:
    """Retorna los overrides de permisos de un docente: [{codigo, concedido}]."""
    filas = (cliente.table('docentes_permisos')
             .select('concedido, permisos(codigo)')
             .eq('docente_id', docente_id)
             .execute().data)

    return [{'codigo': fila['permisos']['codigo'], 'concedido': fila['concedido']}
            for fila in filas if fila.get('permisos')]


def reemplazar_overrides_docente(docente_id: int, overrides: list[dict]) -> None:
    """Reemplaza los overrides de un docente. `overrides`: [{permiso_id, concedido}]."""
    cliente.table('docentes_permisos').delete().eq('docente_id', docente_id).execute()

    if overrides:
        cliente.table('docentes_permisos').insert(
            [{'docente_id': docente_id, **override} for override in overrides]
        ).execute()


# ---------------------------------------------------------------
# Estudiantes
# ---------------------------------------------------------------

CAMPOS_ESTUDIANTE      = 'id, padron, nombre, apellido, email, activo, created_at, updated_at'
CAMPOS_ESTUDIANTE_AUTH = CAMPOS_ESTUDIANTE + ', password_hash'


def obtener_todos_los_estudiantes() -> list[dict]:
    """Retorna todos los estudiantes ordenados por apellido."""
    return cliente.table('estudiantes').select(CAMPOS_ESTUDIANTE).order('apellido').execute().data


def obtener_estudiante_por_id(estudiante_id: int) -> dict:
    """Retorna el estudiante con el id dado, o un dict vacío si no existe."""
    filas = cliente.table('estudiantes').select(CAMPOS_ESTUDIANTE).eq('id', estudiante_id).execute().data

    return filas[0] if filas else {}


def obtener_estudiante_por_email(email: str) -> dict:
    """Retorna el estudiante con el email dado (incluye password_hash, para login)."""
    filas = cliente.table('estudiantes').select(CAMPOS_ESTUDIANTE_AUTH).eq('email', email).execute().data

    return filas[0] if filas else {}


def obtener_estudiante_por_padron(padron: str) -> dict:
    """Retorna el estudiante con el padrón dado, o un dict vacío si no existe."""
    filas = cliente.table('estudiantes').select(CAMPOS_ESTUDIANTE).eq('padron', padron).execute().data

    return filas[0] if filas else {}


def insertar_estudiante(padron: str, nombre: str, apellido: str,
                        email: str, password_hash: str) -> int:
    """Inserta un nuevo estudiante y retorna el id generado."""
    filas = cliente.table('estudiantes').insert({
        'padron':        padron,
        'nombre':        nombre,
        'apellido':      apellido,
        'email':         email,
        'password_hash': password_hash,
    }).execute().data

    return filas[0]['id']


def actualizar_estudiante(estudiante_id: int, padron: str, nombre: str,
                          apellido: str, email: str) -> int:
    """Actualiza los datos de perfil de un estudiante (no el password)."""
    filas = cliente.table('estudiantes').update({
        'padron':     padron,
        'nombre':     nombre,
        'apellido':   apellido,
        'email':      email,
        'updated_at': _ahora_iso(),
    }).eq('id', estudiante_id).execute().data

    return len(filas)


def actualizar_password_estudiante(estudiante_id: int, password_hash: str) -> int:
    """Actualiza el password_hash de un estudiante."""
    filas = cliente.table('estudiantes').update(
        {'password_hash': password_hash, 'updated_at': _ahora_iso()}
    ).eq('id', estudiante_id).execute().data

    return len(filas)


def eliminar_estudiante(estudiante_id: int) -> int:
    """Elimina un estudiante por id. Retorna la cantidad de filas afectadas."""
    filas = cliente.table('estudiantes').delete().eq('id', estudiante_id).execute().data

    return len(filas)


def obtener_overrides_estudiante(estudiante_id: int) -> list[dict]:
    """Retorna los overrides de permisos de un estudiante: [{codigo, concedido}]."""
    filas = (cliente.table('estudiantes_permisos')
             .select('concedido, permisos(codigo)')
             .eq('estudiante_id', estudiante_id)
             .execute().data)

    return [{'codigo': fila['permisos']['codigo'], 'concedido': fila['concedido']}
            for fila in filas if fila.get('permisos')]


def reemplazar_overrides_estudiante(estudiante_id: int, overrides: list[dict]) -> None:
    """Reemplaza los overrides de un estudiante. `overrides`: [{permiso_id, concedido}]."""
    cliente.table('estudiantes_permisos').delete().eq('estudiante_id', estudiante_id).execute()

    if overrides:
        cliente.table('estudiantes_permisos').insert(
            [{'estudiante_id': estudiante_id, **override} for override in overrides]
        ).execute()
