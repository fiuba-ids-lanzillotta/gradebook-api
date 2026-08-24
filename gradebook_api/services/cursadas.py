"""Cursos/cursadas: listado con filtros (código, año, cuatrimestre)."""
from datetime import date

from ..constants import CUATRIMESTRES, ERROR_CODE_INVALID_CUATRIMESTRE
from ..config import CACHE_TTL_CURSADAS_SEGUNDOS
from ..utils import construir_error_api, validar_entero
from .. import db, cache


def listar_cursadas(codigo=None, anio=None, cuatrimestre=None) -> list[dict]:
    """
    Lista las cursadas (con su materia), filtrando opcionalmente por código de
    materia (parcial), año y cuatrimestre.

    Cada item: {codigo, nombre, anio, cuatrimestre, fecha_inicio, fecha_fin, vigente}.
    `vigente` indica si la cursada está transcurriendo hoy (inicio ≤ hoy ≤ fin).
    """
    anio_validado   = _validar_anio(anio)
    cuatri_validado = _validar_cuatrimestre(cuatrimestre)
    codigo_filtro   = (codigo or '').strip() or None

    # Cache-aside de las filas crudas (no del DTO): `vigente` se calcula fresco
    # con la fecha de hoy en cada request, así un TTL largo no sirve fecha vieja.
    clave = f'cursadas:{codigo_filtro or ""}:{anio_validado if anio_validado is not None else ""}:{cuatri_validado if cuatri_validado is not None else ""}'
    filas = cache.obtener(clave)
    if filas is None:
        filas = db.buscar_cursadas(codigo_filtro, anio_validado, cuatri_validado)
        cache.guardar(clave, filas, CACHE_TTL_CURSADAS_SEGUNDOS)

    hoy = date.today().isoformat()

    return [_construir_curso_dto(fila, hoy) for fila in filas if fila.get('materias')]


def _validar_anio(anio):
    if anio is None or str(anio).strip() == '':
        return None

    return validar_entero(anio, 'anio')


def _validar_cuatrimestre(cuatrimestre):
    if cuatrimestre is None or str(cuatrimestre).strip() == '':
        return None

    valor = validar_entero(cuatrimestre, 'cuatrimestre')

    if valor not in CUATRIMESTRES:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_INVALID_CUATRIMESTRE,
            message='Cuatrimestre inválido',
            description=f"El cuatrimestre debe ser uno de: {', '.join(str(c) for c in CUATRIMESTRES)}"
        ))

    return valor


def _construir_curso_dto(fila: dict, hoy: str) -> dict:
    materia = fila['materias']

    return {
        'codigo':       materia['codigo'],
        'nombre':       materia['nombre'],
        'anio':         fila['anio'],
        'cuatrimestre': fila['cuatrimestre'],
        'fecha_inicio': fila['fecha_inicio'],
        'fecha_fin':    fila['fecha_fin'],
        'vigente':      fila['fecha_inicio'] <= hoy <= fila['fecha_fin'],
    }
