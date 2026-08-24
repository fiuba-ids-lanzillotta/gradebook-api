from ..constants import (
    MAXIMO_NOMBRE,
    ERROR_CODE_ASISTENCIA_MARCAR_BODY,
)
from ..utils import (
    construir_error_api,
    validar_string_no_vacio,
    validar_largo_string,
    validar_fecha,
)
from .auth import validar_body_presente


def validar_body_clase(body: dict) -> dict:
    """
    Valida el body de crear/disparar una clase de asistencia.

    `fecha` (requerida, ISO YYYY-MM-DD) y `titulo` (opcional, máx 150). El rango
    válido de la fecha (dentro de la cursada) se verifica en el service.
    """
    validar_body_presente(body)

    errores = []
    fecha   = None
    titulo  = (body.get('titulo') or '').strip() or None

    try:
        fecha = validar_fecha(body.get('fecha'), 'fecha')
    except ValueError as error:
        errores.extend(error.args[0]['errors'])

    if titulo is not None:
        try:
            validar_largo_string(titulo, 1, 150, 'titulo')
        except ValueError as error:
            errores.extend(error.args[0]['errors'])

    if errores:
        raise ValueError({'errors': errores})

    return {'fecha': fecha, 'titulo': titulo}


def validar_body_marcar(body: dict) -> dict:
    """
    Valida el body de marcar asistencia: exactamente uno de `codigo` (QR o
    tipeado) o `padron` (fallback). `manual` (opcional, bool) distingue el código
    tipeado a mano del escaneado por QR. Retorna `{codigo, padron, manual}`.
    """
    validar_body_presente(body)

    codigo = (body.get('codigo') or '').strip() or None
    padron = (body.get('padron') or '').strip() or None
    manual = bool(body.get('manual'))

    if bool(codigo) == bool(padron):
        raise ValueError(construir_error_api(
            code=ERROR_CODE_ASISTENCIA_MARCAR_BODY,
            message='Body inválido para marcar asistencia',
            description="Debe enviarse exactamente uno de 'codigo' o 'padron'."
        ))

    if padron is not None:
        validar_largo_string(validar_string_no_vacio(padron, 'padron'), 1, MAXIMO_NOMBRE, 'padron')

    return {'codigo': codigo, 'padron': padron, 'manual': manual}
