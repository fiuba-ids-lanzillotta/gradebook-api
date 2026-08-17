from ..constants import ERROR_CODE_DOCENTE_NOT_FOUND, ERROR_CODE_EMAIL_DUPLICADO
from ..utils import construir_error_api, hashear_password
from ..validators.docentes import validar_body_docente
from .. import db


def construir_docente_dto(docente: dict) -> dict:
    """DTO público de un docente (nunca expone el password_hash)."""
    return {
        'id':         docente['id'],
        'nombre':     docente['nombre'],
        'apellido':   docente['apellido'],
        'email':      docente['email'],
        'rol':        docente['rol'],
        'foto':       docente.get('foto'),
        'activo':     docente.get('activo', True),
        'created_at': docente.get('created_at'),
        'updated_at': docente.get('updated_at'),
    }


def listar_docentes() -> list[dict]:
    """Retorna todos los docentes (ordenados por apellido)."""
    return [construir_docente_dto(docente) for docente in db.obtener_todos_los_docentes()]


def buscar_docente_por_id(docente_id: int) -> dict:
    """Busca un docente por id. Lanza ValueError 404 si no existe."""
    return construir_docente_dto(_obtener_docente_o_404(docente_id))


def crear_docente(body: dict) -> dict:
    """Valida el body, verifica email único, hashea el password e inserta un docente."""
    datos = validar_body_docente(body, requiere_password=True)
    _validar_email_unico(datos['email'])

    nuevo_id = db.insertar_docente(
        datos['nombre'], datos['apellido'], datos['email'], datos['rol'],
        datos['foto'], hashear_password(datos['password'])
    )

    return buscar_docente_por_id(nuevo_id)


def actualizar_docente(docente_id: int, body: dict) -> dict:
    """Valida el body y actualiza un docente. Si viene password, lo actualiza."""
    _obtener_docente_o_404(docente_id)
    datos = validar_body_docente(body, requiere_password=False)
    _validar_email_unico(datos['email'], excluir_id=docente_id)

    db.actualizar_docente(
        docente_id, datos['nombre'], datos['apellido'], datos['email'], datos['rol'], datos['foto']
    )

    if datos['password']:
        db.actualizar_password_docente(docente_id, hashear_password(datos['password']))

    return buscar_docente_por_id(docente_id)


def eliminar_docente_por_id(docente_id: int) -> None:
    """Elimina un docente por id, o lanza ValueError 404 si no existe."""
    _obtener_docente_o_404(docente_id)

    db.eliminar_docente(docente_id)


def _validar_email_unico(email: str, excluir_id: int | None = None) -> None:
    """Verifica que el email no esté usado por otro docente. Lanza 409 si ya está en uso."""
    otro = db.obtener_docente_por_email(email)

    if otro and otro['id'] != excluir_id:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_EMAIL_DUPLICADO,
            message='Email en uso',
            description=f"Ya existe un docente con el email '{email}'"
        ), 409)


def _obtener_docente_o_404(docente_id: int) -> dict:
    """Retorna la fila del docente o lanza 404."""
    docente = db.obtener_docente_por_id(docente_id)

    if not docente:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_DOCENTE_NOT_FOUND,
            message='Docente no encontrado',
            description=f"No existe un docente con id '{docente_id}'"
        ), 404)

    return docente
