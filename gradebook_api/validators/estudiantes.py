from ..constants import (
    MAXIMO_NOMBRE,
    MAXIMO_APELLIDO,
    MAXIMO_PADRON,
)
from ..utils import (
    validar_string_no_vacio,
    validar_largo_string,
    validar_formato_email,
)
from .auth import validar_body_presente


def validar_body_estudiante(body: dict, requiere_password: bool = True) -> dict:
    """
    Valida el body para crear/actualizar un estudiante.

    Obligatorios: padron, nombre, apellido, email. `password` es obligatorio al
    crear (requiere_password=True) y opcional al actualizar.
    """
    validar_body_presente(body)

    errores  = []
    padron   = None
    nombre   = None
    apellido = None
    email    = None
    password = None

    try:
        padron = validar_largo_string(validar_string_no_vacio(body.get('padron'), 'padron'),
                                      1, MAXIMO_PADRON, 'padron')
    except ValueError as error:
        errores.extend(error.args[0]['errors'])

    try:
        nombre = validar_largo_string(validar_string_no_vacio(body.get('nombre'), 'nombre'),
                                      1, MAXIMO_NOMBRE, 'nombre')
    except ValueError as error:
        errores.extend(error.args[0]['errors'])

    try:
        apellido = validar_largo_string(validar_string_no_vacio(body.get('apellido'), 'apellido'),
                                        1, MAXIMO_APELLIDO, 'apellido')
    except ValueError as error:
        errores.extend(error.args[0]['errors'])

    try:
        email = validar_formato_email(validar_string_no_vacio(body.get('email'), 'email'))
    except ValueError as error:
        errores.extend(error.args[0]['errors'])

    if requiere_password or body.get('password') is not None:
        try:
            password = validar_string_no_vacio(body.get('password'), 'password')
        except ValueError as error:
            errores.extend(error.args[0]['errors'])

    if errores:
        raise ValueError({'errors': errores})

    return {
        'padron':   padron,
        'nombre':   nombre,
        'apellido': apellido,
        'email':    email,
        'password': password,
    }
