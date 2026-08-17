from ..constants import ERROR_CODE_INVALID_BODY
from ..utils import (
    construir_error_api,
    validar_string_no_vacio,
    validar_formato_email,
)


def validar_body_presente(body):
    if body is None:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_INVALID_BODY,
            message='Cuerpo de la solicitud inválido',
            description='El cuerpo debe ser un JSON válido con Content-Type application/json'
        ))


def validar_body_login(body: dict) -> dict:
    """Valida el body del POST /login: email y password."""
    validar_body_presente(body)

    errores  = []
    email    = None
    password = None

    try:
        email = validar_formato_email(validar_string_no_vacio(body.get('email'), 'email'))
    except ValueError as error:
        errores.extend(error.args[0]['errors'])

    try:
        password = validar_string_no_vacio(body.get('password'), 'password')
    except ValueError as error:
        errores.extend(error.args[0]['errors'])

    if errores:
        raise ValueError({'errors': errores})

    return {'email': email, 'password': password}
