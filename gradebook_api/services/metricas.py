"""Agregados y estadísticas de una cursada (dashboards del docente)."""
from .. import db
from ..constants import (
    ERROR_CODE_CURSADA_NOT_FOUND,
    ESTADO_INSCRIPCION_ABANDONO,
    ESTADO_INSCRIPCION_BAJA,
    ESTADO_INSCRIPCION_CURSANDO,
)
from ..utils import construir_error_api, validar_entero, validar_minimo
from .evaluaciones import MODALIDAD_GRUPAL

NOTA_APROBACION = 4
ESTADOS_APROBADOS = ('aprobado', 'entregado')
TIPO_OBLIGATORIO = 'obligatorio'


def metricas(cursada_id: int) -> dict:
    """
    Estadísticas de la cursada para el dashboard del docente: inscripciones por
    estado, rendidos/pendientes y correcciones por instancia, equipos y promoción.
    """
    cursada_id = validar_minimo(validar_entero(cursada_id, 'cursada_id'), 1, 'cursada_id')

    if not db.obtener_cursada_por_id(cursada_id):
        raise ValueError(construir_error_api(
            code=ERROR_CODE_CURSADA_NOT_FOUND,
            message='Cursada no encontrada',
            description=f"No existe una cursada con id '{cursada_id}'.",
        ), 404)

    evaluaciones = db.listar_evaluaciones(cursada_id)
    instancias = db.instancias_de_evaluaciones([fila['id'] for fila in evaluaciones])
    inscripciones = db.inscripciones_de_cursada(cursada_id)

    grupales = [fila for fila in evaluaciones if fila.get('modalidad') == MODALIDAD_GRUPAL]
    grupos = db.listar_grupos_de_evaluaciones([fila['id'] for fila in grupales])
    miembros = db.miembros_de_grupos([fila['id'] for fila in grupos])

    instancia_ids = [fila['id'] for fila in instancias]
    notas = db.notas_en_instancias(instancia_ids)
    notas_grupo = db.notas_grupo_en_instancias(instancia_ids)
    docentes = {fila['id']: _dto_docente(fila) for fila in db.obtener_todos_los_docentes()}

    cursando = [fila for fila in inscripciones
                if fila['estado'] == ESTADO_INSCRIPCION_CURSANDO]

    return {
        'alumnos':    _alumnos(inscripciones, cursando, evaluaciones,
                               instancias, grupos, miembros, notas, notas_grupo),
        'instancias': [_instancia_metrica(instancia, evaluaciones, instancias, grupos,
                                          len(cursando), notas, notas_grupo, docentes)
                       for instancia in sorted(instancias, key=lambda fila: (
                           fila['evaluacion_id'], fila.get('numero') or 0))],
        'equipos':    _equipos(grupales, grupos, miembros, len(cursando)),
        'docentes':   _docentes(grupos, docentes),
    }


def _alumnos(inscripciones: list, cursando: list, evaluaciones: list,
             instancias: list, grupos: list, miembros: list,
             notas: list, notas_grupo: list) -> dict:
    return {
        'total':         len(inscripciones),
        'cursando':      len(cursando),
        'baja':          _cuenta(inscripciones, ESTADO_INSCRIPCION_BAJA),
        'abandono':      _cuenta(inscripciones, ESTADO_INSCRIPCION_ABANDONO),
        'promocionados': _promocionados(cursando, evaluaciones, instancias,
                                        grupos, miembros, notas, notas_grupo),
    }


def _cuenta(inscripciones: list, estado: str) -> int:
    return len([fila for fila in inscripciones if fila['estado'] == estado])


def _promocionados(cursando: list, evaluaciones: list, instancias: list,
                   grupos: list, miembros: list, notas: list, notas_grupo: list) -> int:
    """Cursando con TODAS las obligatorias aprobadas (nota ≥4 / aprobado / entregado
    en la última instancia en que tienen nota cargada)."""
    obligatorias = [fila for fila in evaluaciones if fila.get('tipo') == TIPO_OBLIGATORIO]
    if not obligatorias:
        return 0

    eval_grupal = {fila['id'] for fila in obligatorias
                   if fila.get('modalidad') == MODALIDAD_GRUPAL}
    grupo_de = {}
    for grupo in grupos:
        if grupo['evaluacion_id'] in eval_grupal:
            grupo_de[grupo['id']] = grupo['evaluacion_id']

    grupos_de_alumno = {}
    for fila in miembros:
        if fila['grupo_id'] in grupo_de:
            grupos_de_alumno.setdefault(fila['estudiante_id'], set()).add(fila['grupo_id'])

    criterios = {fila['id']: fila.get('criterio') for fila in obligatorias}
    numeros = {fila['id']: fila.get('numero') or 0 for fila in instancias}
    instancia_eval = {fila['id']: fila['evaluacion_id'] for fila in instancias}

    notas_por_alumno = {}
    for fila in notas:
        clave = (fila['estudiante_id'], instancia_eval.get(fila['instancia_id']))
        if clave[1] in criterios and clave[1] not in eval_grupal:
            _guardar_ultima(notas_por_alumno, clave, fila, numeros)

    grupo_eval = {fila['grupo_id']: instancia_eval.get(fila['instancia_id'])
                  for fila in notas_grupo}
    for fila in notas_grupo:
        evaluacion_id = grupo_eval[fila['grupo_id']]
        if evaluacion_id not in eval_grupal:
            continue
        for estudiante_id, sus_grupos in grupos_de_alumno.items():
            if fila['grupo_id'] in sus_grupos:
                _guardar_ultima(notas_por_alumno, (estudiante_id, evaluacion_id), fila, numeros)

    return len([fila for fila in cursando
                if all(_aprobado(notas_por_alumno.get((fila['estudiante_id'], evaluacion['id'])),
                                 criterios[evaluacion['id']])
                       for evaluacion in obligatorias)])


def _guardar_ultima(notas_por_alumno: dict, clave: tuple, fila: dict, numeros: dict) -> None:
    """Se queda con la nota de la instancia de mayor número (la última rendida)."""
    actual = notas_por_alumno.get(clave)
    if not actual or numeros.get(fila['instancia_id'], 0) >= numeros.get(actual['instancia_id'], 0):
        notas_por_alumno[clave] = fila


def _aprobado(nota: dict, criterio: str) -> bool:
    if not nota:
        return False

    if criterio == 'nota':
        return nota.get('nota') is not None and nota['nota'] >= NOTA_APROBACION

    return nota.get('estado') in ESTADOS_APROBADOS


def _instancia_metrica(instancia: dict, evaluaciones: list, instancias: list,
                       grupos: list, cursando: int, notas: list,
                       notas_grupo: list, docentes: dict) -> dict:
    evaluacion = _evaluacion_de(instancia, evaluaciones)
    grupal = evaluacion.get('modalidad') == MODALIDAD_GRUPAL

    if grupal:
        filas = [fila for fila in notas_grupo if fila['instancia_id'] == instancia['id']]
        total = len([grupo for grupo in grupos
                     if grupo['evaluacion_id'] == evaluacion['id']])
    else:
        filas = [fila for fila in notas if fila['instancia_id'] == instancia['id']]
        total = cursando

    return {
        'evaluacion':    {campo: evaluacion.get(campo)
                          for campo in ('id', 'nombre', 'tipo', 'criterio',
                                        'modalidad', 'visibilidad')},
        'instancia':     {campo: instancia.get(campo)
                          for campo in ('id', 'numero', 'nombre', 'fecha', 'estado')},
        'rendidos':      len(filas),
        'pendientes':    max(total - len(filas), 0),
        'promedio':      _promedio(filas) if evaluacion.get('criterio') == 'nota' else None,
        'estados':       _estados(filas),
        'por_corrector': _por_corrector(filas, docentes),
    }


def _evaluacion_de(instancia: dict, evaluaciones: list) -> dict:
    for evaluacion in evaluaciones:
        if evaluacion['id'] == instancia['evaluacion_id']:
            return evaluacion

    return {}


def _promedio(filas: list):
    notas = [fila['nota'] for fila in filas if fila.get('nota') is not None]

    return round(sum(notas) / len(notas), 2) if notas else None


def _estados(filas: list) -> dict:
    estados = {}
    for fila in filas:
        if fila.get('estado'):
            estados[fila['estado']] = estados.get(fila['estado'], 0) + 1

    return estados


def _por_corrector(filas: list, docentes: dict) -> list:
    cantidades = {}
    for fila in filas:
        if fila.get('corrector_id'):
            cantidades[fila['corrector_id']] = cantidades.get(fila['corrector_id'], 0) + 1

    return sorted(
        [{'docente': docentes.get(corrector_id, {'id': corrector_id}),
          'cantidad': cantidad}
         for corrector_id, cantidad in cantidades.items()],
        key=lambda item: -item['cantidad'],
    )


def _equipos(grupales: list, grupos: list, miembros: list, cursando: int) -> dict:
    abierta = next((fila for fila in grupales if fila.get('permite_crear_grupos')), None)
    sin_equipo = None

    if abierta:
        grupos_abierta = {grupo['id'] for grupo in grupos
                          if grupo['evaluacion_id'] == abierta['id']}
        con_equipo = {fila['estudiante_id'] for fila in miembros
                      if fila['grupo_id'] in grupos_abierta}
        sin_equipo = max(cursando - len(con_equipo), 0)

    return {'total': len(grupos), 'sin_equipo': sin_equipo}


def _docentes(grupos: list, docentes: dict) -> list:
    cantidades = {}
    for grupo in grupos:
        if grupo.get('tutor_id'):
            cantidades[grupo['tutor_id']] = cantidades.get(grupo['tutor_id'], 0) + 1

    return sorted(
        [{'docente': docentes.get(tutor_id, {'id': tutor_id}), 'equipos': cantidad}
         for tutor_id, cantidad in cantidades.items()],
        key=lambda item: -item['equipos'],
    )


def _dto_docente(fila: dict) -> dict:
    return {'id': fila.get('id'), 'nombre': fila.get('nombre'),
            'apellido': fila.get('apellido')}
