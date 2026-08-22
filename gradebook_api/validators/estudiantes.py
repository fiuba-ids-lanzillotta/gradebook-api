from ..constants import (
    MAXIMO_NOMBRE,
    MAXIMO_APELLIDO,
    MAXIMO_PADRON,
    ESTADOS_INSCRIPCION,
    ERROR_CODE_INVALID_ESTADO_INSCRIPCION,
)
from ..utils import (
    construir_error_api,
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


def validar_body_estado_inscripcion(body: dict) -> dict:
    """
    Valida el body para cambiar el estado de una inscripción (baja lógica / abandono).

    `estado` obligatorio (∈ ESTADOS_INSCRIPCION). `motivo` obligatorio solo si
    `estado == 'baja'`; para el resto es opcional.
    """
    validar_body_presente(body)

    errores = []
    estado  = None
    motivo  = None

    try:
        estado = validar_string_no_vacio(body.get('estado'), 'estado')

        if estado not in ESTADOS_INSCRIPCION:
            raise ValueError(construir_error_api(
                code=ERROR_CODE_INVALID_ESTADO_INSCRIPCION,
                message='Estado de inscripción inválido',
                description=f"El estado '{estado}' no es válido. Valores permitidos: {', '.join(ESTADOS_INSCRIPCION)}"
            ))
    except ValueError as error:
        errores.extend(error.args[0]['errors'])

    if estado == 'baja':
        try:
            motivo = validar_string_no_vacio(body.get('motivo'), 'motivo')
        except ValueError as error:
            errores.extend(error.args[0]['errors'])
    else:
        crudo  = body.get('motivo')
        motivo = crudo.strip() if isinstance(crudo, str) and crudo.strip() else None

    if errores:
        raise ValueError({'errors': errores})

    return {'estado': estado, 'motivo': motivo}
