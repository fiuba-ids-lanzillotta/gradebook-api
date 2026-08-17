from ..constants import (
    ERROR_CODE_ESTUDIANTE_NOT_FOUND,
    ERROR_CODE_EMAIL_DUPLICADO,
    ERROR_CODE_PADRON_DUPLICADO,
)
from ..utils import construir_error_api, hashear_password
from ..validators.estudiantes import validar_body_estudiante
from .. import db


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


def listar_estudiantes() -> list[dict]:
    """Retorna todos los estudiantes (ordenados por apellido)."""
    return [construir_estudiante_dto(estudiante) for estudiante in db.obtener_todos_los_estudiantes()]


def buscar_estudiante_por_id(estudiante_id: int) -> dict:
    """Busca un estudiante por id. Lanza ValueError 404 si no existe."""
    return construir_estudiante_dto(_obtener_estudiante_o_404(estudiante_id))


def crear_estudiante(body: dict) -> dict:
    """Valida el body, verifica padrón/email únicos, hashea el password e inserta."""
    datos = validar_body_estudiante(body, requiere_password=True)
    _validar_padron_unico(datos['padron'])
    _validar_email_unico(datos['email'])

    nuevo_id = db.insertar_estudiante(
        datos['padron'], datos['nombre'], datos['apellido'], datos['email'],
        hashear_password(datos['password'])
    )

    return buscar_estudiante_por_id(nuevo_id)


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

    return buscar_estudiante_por_id(estudiante_id)


def eliminar_estudiante_por_id(estudiante_id: int) -> None:
    """Elimina un estudiante por id, o lanza ValueError 404 si no existe."""
    _obtener_estudiante_o_404(estudiante_id)

    db.eliminar_estudiante(estudiante_id)


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
