from ..constants import (
    CARGOS_DOCENTE,
    MAXIMO_NOMBRE,
    MAXIMO_APELLIDO,
    ERROR_CODE_INVALID_CARGO,
)
from ..utils import (
    construir_error_api,
    validar_string_no_vacio,
    validar_largo_string,
    validar_formato_email,
)
from .auth import validar_body_presente


def validar_body_docente(body: dict, requiere_password: bool = True) -> dict:
    """
    Valida el body para crear/actualizar un docente.

    Obligatorios: nombre, apellido, email, rol (cargo). `password` es obligatorio
    al crear (requiere_password=True) y opcional al actualizar. `foto` opcional.
    """
    validar_body_presente(body)

    errores  = []
    nombre   = None
    apellido = None
    email    = None
    rol      = None
    password = None

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

    try:
        rol = validar_string_no_vacio(body.get('rol'), 'rol')

        if rol not in CARGOS_DOCENTE:
            raise ValueError(construir_error_api(
                code=ERROR_CODE_INVALID_CARGO,
                message='Cargo de docente inválido',
                description=f"El cargo '{rol}' no es válido. Valores permitidos: {', '.join(CARGOS_DOCENTE)}"
            ))
    except ValueError as error:
        errores.extend(error.args[0]['errors'])

    if requiere_password or body.get('password') is not None:
        try:
            password = validar_string_no_vacio(body.get('password'), 'password')
        except ValueError as error:
            errores.extend(error.args[0]['errors'])

    foto = body.get('foto')
    foto = foto if isinstance(foto, str) and foto.strip() else None

    if errores:
        raise ValueError({'errors': errores})

    return {
        'nombre':   nombre,
        'apellido': apellido,
        'email':    email,
        'rol':      rol,
        'foto':     foto,
        'password': password,
    }
