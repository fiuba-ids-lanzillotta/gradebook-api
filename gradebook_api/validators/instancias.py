"""Validadores para altas y modificaciones de instancias de evaluación."""
from ..constants import (
    ESTADOS_INSTANCIA,
    MAXIMO_NOMBRE_INSTANCIA,
    ERROR_CODE_INVALID_ESTADO_INSTANCIA,
)
from ..utils import (
    construir_error_api,
    validar_string_no_vacio,
    validar_largo_string,
    validar_fecha,
)
from .auth import validar_body_presente


def _nombre(body: dict, errores: list, requerido: bool = True):
    if not requerido and 'nombre' not in body:
        return None, False

    try:
        valor = validar_largo_string(
            validar_string_no_vacio(body.get('nombre'), 'nombre'),
            1, MAXIMO_NOMBRE_INSTANCIA, 'nombre'
        )
        return valor, True
    except ValueError as error:
        errores.extend(error.args[0]['errors'])
        return None, False


def _fecha(body: dict, errores: list, requerido: bool = False):
    if 'fecha' not in body:
        return None, False

    if body.get('fecha') is None:
        return None, True

    try:
        return validar_fecha(body.get('fecha'), 'fecha'), True
    except ValueError as error:
        errores.extend(error.args[0]['errors'])
        return None, False


def _estado(body: dict, errores: list):
    if 'estado' not in body:
        return None, False

    valor = body.get('estado')

    if valor in ESTADOS_INSTANCIA:
        return valor, True

    errores.append(construir_error_api(
        code=ERROR_CODE_INVALID_ESTADO_INSTANCIA,
        message='Estado de instancia inválido',
        description=f"El estado debe ser uno de: {', '.join(ESTADOS_INSTANCIA)}"
    )['errors'][0])
    return None, False


def validar_body_instancia(body: dict) -> dict:
    """
    Valida el body para crear una instancia.
    Obligatorio: nombre. Opcional: fecha (ISO, o null).
    La instancia nace con estado 'abierta'.
    """
    validar_body_presente(body)

    errores = []
    nombre, _ = _nombre(body, errores)
    fecha,  _ = _fecha(body, errores)

    if errores:
        raise ValueError({'errors': errores})

    return {'nombre': nombre, 'fecha': fecha}


def validar_body_actualizar_instancia(body: dict) -> dict:
    """
    Valida el body para editar una instancia.
    Acepta cualquier subconjunto de nombre/fecha/estado, pero al menos uno.
    `fecha: null` limpia la fecha.
    """
    validar_body_presente(body)

    errores = []
    nombre, hay_nombre = _nombre(body, errores, requerido=False)
    fecha,  hay_fecha  = _fecha(body, errores)
    estado, hay_estado = _estado(body, errores)

    if errores:
        raise ValueError({'errors': errores})

    datos = {}
    if hay_nombre:
        datos['nombre'] = nombre
    if hay_fecha:
        datos['fecha'] = fecha
    if hay_estado:
        datos['estado'] = estado

    if not datos:
        raise ValueError(construir_error_api(
            code='invalid.body',
            message='Body inválido',
            description='Se espera al menos uno de los campos: nombre, fecha, estado'
        ))

    return datos
