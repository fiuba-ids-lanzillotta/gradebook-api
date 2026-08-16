from ..constants import MAXIMO_NOMBRE, MAXIMO_DESCRIPCION
from ..utils import (
    validar_string_no_vacio,
    validar_largo_string,
    validar_booleano,
)
from .auth import validar_body_presente


def validar_body_item(body: dict) -> dict:
    """
    Valida el body para crear/actualizar un item.

    Campos obligatorios: nombre (único, 1..MAXIMO_NOMBRE).
    Campos opcionales: descripcion (hasta MAXIMO_DESCRIPCION) y activo (bool, default True).
    Acumula los errores de todos los campos antes de lanzar.
    """
    validar_body_presente(body)

    errores     = []
    nombre      = None
    descripcion = None
    activo      = True

    try:
        nombre = validar_string_no_vacio(body.get('nombre'), 'nombre')
        nombre = validar_largo_string(nombre, 1, MAXIMO_NOMBRE, 'nombre')
    except ValueError as error:
        errores.extend(error.args[0]['errors'])

    # descripcion opcional
    if body.get('descripcion') is not None and str(body.get('descripcion')).strip():
        try:
            descripcion = validar_string_no_vacio(body.get('descripcion'), 'descripcion')
            descripcion = validar_largo_string(descripcion, 1, MAXIMO_DESCRIPCION, 'descripcion')
        except ValueError as error:
            errores.extend(error.args[0]['errors'])

    # activo opcional (default True)
    if body.get('activo') is not None:
        try:
            activo = validar_booleano(body.get('activo'), 'activo')
        except ValueError as error:
            errores.extend(error.args[0]['errors'])

    if errores:
        raise ValueError({'errors': errores})

    return {
        'nombre':      nombre,
        'descripcion': descripcion,
        'activo':      activo,
    }
