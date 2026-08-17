from ..constants import ERROR_CODE_INVALID_BODY
from ..utils import (
    construir_error_api,
    validar_string_no_vacio,
    validar_booleano,
)
from .auth import validar_body_presente


def validar_body_permisos_rol(body: dict) -> list[str]:
    """
    Valida el body para setear los permisos de un rol.

    Espera `{"permisos": ["docentes.leer", ...]}` y retorna la lista de códigos.
    """
    validar_body_presente(body)

    permisos = body.get('permisos')

    if not isinstance(permisos, list):
        raise ValueError(construir_error_api(
            code=ERROR_CODE_INVALID_BODY,
            message="Campo 'permisos' inválido",
            description="Se espera un arreglo de códigos de permiso en 'permisos'"
        ))

    return [validar_string_no_vacio(codigo, 'permiso') for codigo in permisos]


def validar_body_overrides(body: dict) -> list[dict]:
    """
    Valida el body para setear overrides de permisos de una persona.

    Espera `{"permisos": [{"permiso": "docentes.gestionar", "concedido": true}, ...]}`
    y retorna `[{codigo, concedido}]`.
    """
    validar_body_presente(body)

    permisos = body.get('permisos')

    if not isinstance(permisos, list):
        raise ValueError(construir_error_api(
            code=ERROR_CODE_INVALID_BODY,
            message="Campo 'permisos' inválido",
            description="Se espera un arreglo de overrides en 'permisos'"
        ))

    resultado = []
    errores   = []

    for override in permisos:
        if not isinstance(override, dict):
            errores.append(construir_error_api(
                code=ERROR_CODE_INVALID_BODY,
                message='Override inválido',
                description='Cada override debe ser un objeto {permiso, concedido}'
            )['errors'][0])
        else:
            try:
                codigo    = validar_string_no_vacio(override.get('permiso'), 'permiso')
                concedido = validar_booleano(override.get('concedido'), 'concedido')
                resultado.append({'codigo': codigo, 'concedido': concedido})
            except ValueError as error:
                errores.extend(error.args[0]['errors'])

    if errores:
        raise ValueError({'errors': errores})

    return resultado
