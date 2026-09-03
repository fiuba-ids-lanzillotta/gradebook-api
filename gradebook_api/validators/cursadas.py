"""Validadores para altas y modificaciones de cursadas."""
from datetime import date, datetime

from ..constants import (
    CUATRIMESTRES,
    MAXIMO_CODIGO_MATERIA,
    MAXIMO_NOMBRE_MATERIA,
    MINIMO_ANIO_CURSADA,
    MAXIMO_ANIO_CURSADA,
    ERROR_CODE_INVALID_CUATRIMESTRE,
    ERROR_CODE_FECHA_RANGO_INVALIDO,
    ERROR_CODE_FECHA_INICIO_POSTERIOR_FIN,
    ERROR_CODE_FECHA_CUATRIMESTRE_INVALIDA,
)
from ..utils import (
    construir_error_api,
    validar_string_no_vacio,
    validar_largo_string,
    validar_entero,
    validar_minimo,
    validar_maximo,
    validar_fecha,
)
from .auth import validar_body_presente


def validar_body_cursada(body: dict) -> dict:
    """
    Valida el body para crear o actualizar una cursada.

    Obligatorios: codigo, nombre, anio, cuatrimestre, fecha_inicio, fecha_fin.
    - `codigo` y `nombre` son de la materia.
    - `anio` es el año académico.
    - `cuatrimestre` ∈ {1, 2}.
    - `fecha_inicio` < `fecha_fin`.
    - Ambas fechas deben caer en el año de la cursada y dentro del rango del
      cuatrimestre (1C: 1/ene - 30/jun; 2C: 1/jul - 31/dic).
    """
    validar_body_presente(body)

    errores        = []
    codigo         = None
    nombre         = None
    anio           = None
    cuatrimestre   = None
    fecha_inicio   = None
    fecha_fin      = None

    try:
        codigo = validar_largo_string(
            validar_string_no_vacio(body.get('codigo'), 'codigo'),
            1, MAXIMO_CODIGO_MATERIA, 'codigo'
        )
    except ValueError as error:
        errores.extend(error.args[0]['errors'])

    try:
        nombre = validar_largo_string(
            validar_string_no_vacio(body.get('nombre'), 'nombre'),
            1, MAXIMO_NOMBRE_MATERIA, 'nombre'
        )
    except ValueError as error:
        errores.extend(error.args[0]['errors'])

    try:
        anio = validar_maximo(
            validar_minimo(validar_entero(body.get('anio'), 'anio'), MINIMO_ANIO_CURSADA, 'anio'),
            MAXIMO_ANIO_CURSADA, 'anio'
        )
    except ValueError as error:
        errores.extend(error.args[0]['errors'])

    try:
        cuatrimestre = validar_entero(body.get('cuatrimestre'), 'cuatrimestre')

        if cuatrimestre not in CUATRIMESTRES:
            raise ValueError(construir_error_api(
                code=ERROR_CODE_INVALID_CUATRIMESTRE,
                message='Cuatrimestre inválido',
                description=f"El cuatrimestre debe ser uno de: {', '.join(str(c) for c in CUATRIMESTRES)}"
            ))
    except ValueError as error:
        errores.extend(error.args[0]['errors'])

    try:
        fecha_inicio = validar_fecha(body.get('fecha_inicio'), 'fecha_inicio')
    except ValueError as error:
        errores.extend(error.args[0]['errors'])

    try:
        fecha_fin = validar_fecha(body.get('fecha_fin'), 'fecha_fin')
    except ValueError as error:
        errores.extend(error.args[0]['errors'])

    if anio is not None and fecha_inicio is not None and fecha_fin is not None:
        _validar_rango_fechas(anio, cuatrimestre, fecha_inicio, fecha_fin, errores)

    if errores:
        raise ValueError({'errors': errores})

    return {
        'codigo':         codigo,
        'nombre':         nombre,
        'anio':           anio,
        'cuatrimestre':   cuatrimestre,
        'fecha_inicio':   fecha_inicio,
        'fecha_fin':      fecha_fin,
    }


def _validar_rango_fechas(anio: int, cuatrimestre: int | None,
                          fecha_inicio: str, fecha_fin: str, errores: list) -> None:
    inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
    fin    = datetime.strptime(fecha_fin, '%Y-%m-%d').date()

    if inicio >= fin:
        errores.append(construir_error_api(
            code=ERROR_CODE_FECHA_INICIO_POSTERIOR_FIN,
            message='Rango de fechas inválido',
            description='La fecha de inicio debe ser anterior a la fecha de fin.'
        )['errors'][0])

    if inicio.year != anio or fin.year != anio:
        errores.append(construir_error_api(
            code=ERROR_CODE_FECHA_RANGO_INVALIDO,
            message='Año de fechas inválido',
            description=f"Las fechas deben corresponder al año de la cursada ({anio})."
        )['errors'][0])

    if cuatrimestre is None:
        return

    if cuatrimestre == 1:
        inicio_min = date(anio, 1, 1)
        fin_max    = date(anio, 6, 30)
    else:
        inicio_min = date(anio, 7, 1)
        fin_max    = date(anio, 12, 31)

    if inicio < inicio_min or fin > fin_max:
        periodo = '1 de enero al 30 de junio' if cuatrimestre == 1 else '1 de julio al 31 de diciembre'
        errores.append(construir_error_api(
            code=ERROR_CODE_FECHA_CUATRIMESTRE_INVALIDA,
            message='Fechas fuera del cuatrimestre',
            description=f"El cuatrimestre {cuatrimestre} exige fechas entre el {periodo} del año {anio}."
        )['errors'][0])
