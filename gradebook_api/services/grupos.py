"""Equipos de las evaluaciones grupales de una cursada."""
from ..constants import (
    ERROR_CODE_CURSADA_NOT_FOUND,
    ERROR_CODE_ESTUDIANTE_NOT_FOUND,
    ERROR_CODE_GRUPO_MIEMBRO,
    ERROR_CODE_GRUPO_NOT_FOUND,
    ERROR_CODE_GRUPO_OWNER,
    ERROR_CODE_GRUPO_TUTOR,
    ERROR_CODE_INVALID_BODY,
)
from ..utils import construir_error_api, validar_entero, validar_minimo
from .. import db

MAXIMO_NOMBRE_GRUPO = 150
ESTADO_CURSANDO = 'cursando'


def listar_de_cursada(cursada_id: int) -> dict:
    """Grupos de las evaluaciones grupales de la cursada, con tutor e integrantes."""
    cursada_id = validar_minimo(validar_entero(cursada_id, 'id'), 1, 'id')
    _cursada_o_404(cursada_id)
    evaluaciones = db.listar_evaluaciones_grupales(cursada_id)
    nombres = {fila['id']: fila.get('nombre') or '' for fila in evaluaciones}
    grupos = db.listar_grupos_de_evaluaciones([fila['id'] for fila in evaluaciones])
    miembros = db.miembros_de_grupos([fila['id'] for fila in grupos])
    por_grupo = _agrupar_miembros(miembros)

    return {
        'grupos': [_dto_listado(fila, nombres, por_grupo.get(fila['id'], [])) for fila in grupos],
    }


def detalle(grupo_id: int) -> dict:
    grupo = _grupo_o_404(grupo_id)
    grupo_id = grupo['id']
    evaluacion = db.obtener_evaluacion(grupo['evaluacion_id'])
    cursada_id = evaluacion.get('cursada_id')
    cursada = db.obtener_cursada_por_id(cursada_id) if cursada_id else {}
    miembros = db.miembros_de_grupos([grupo_id])
    grupos_evaluacion = db.listar_grupos_de_evaluaciones([grupo['evaluacion_id']])
    ocupados = {
        fila['estudiante_id']
        for fila in db.miembros_de_grupos([item['id'] for item in grupos_evaluacion])
    }
    candidatos = [
        estudiante
        for fila in (db.inscriptos_cursando(cursada_id) if cursada_id else [])
        for estudiante in [_estudiante_de_inscripcion(fila)]
        if estudiante.get('id') and estudiante['id'] not in ocupados
    ]

    return {
        **_dto_base(grupo),
        'evaluacion_nombre': evaluacion.get('nombre') or '',
        'cursada_id': cursada_id,
        'anio': cursada.get('anio'),
        'cuatrimestre': cursada.get('cuatrimestre'),
        'integrantes': _integrantes(miembros, grupo['owner_id']),
        'otros_grupos': [
            {'id': fila['id'], 'nombre': fila['nombre']}
            for fila in grupos_evaluacion
            if fila['id'] != grupo_id
        ],
        'candidatos': candidatos,
    }


def renombrar(grupo_id: int, nombre: str) -> dict:
    _grupo_o_404(grupo_id)
    limpio = (nombre or '').strip()

    if not limpio or len(limpio) > MAXIMO_NOMBRE_GRUPO:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_INVALID_BODY,
            message='Nombre inválido',
            description=f'El nombre del equipo es obligatorio y de hasta {MAXIMO_NOMBRE_GRUPO} caracteres.',
        ), 400)

    db.actualizar_grupo(grupo_id, {'nombre': limpio})

    return detalle(grupo_id)


def asignar_tutores(asignaciones: list[dict]) -> dict:
    """Actualiza el tutor de varios equipos. tutor_id null deja el equipo sin tutor."""
    if not isinstance(asignaciones, list) or not asignaciones:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_INVALID_BODY,
            message='Asignaciones inválidas',
            description='Hay que enviar al menos un equipo.',
        ), 400)

    sin_tutor = 0

    for item in asignaciones:
        if not isinstance(item, dict):
            raise ValueError(construir_error_api(
                code=ERROR_CODE_INVALID_BODY,
                message='Asignaciones inválidas',
                description='Cada asignación tiene que ser un objeto con grupo_id y tutor_id.',
            ), 400)

        grupo_id = validar_minimo(validar_entero(item.get('grupo_id'), 'grupo_id'), 1, 'grupo_id')
        _grupo_o_404(grupo_id)
        tutor_id = _tutor_valido(item.get('tutor_id'))
        db.actualizar_grupo(grupo_id, {'tutor_id': tutor_id})
        sin_tutor += 1 if tutor_id is None else 0

    return {'actualizados': len(asignaciones), 'sin_tutor': sin_tutor}


def agregar_integrante(grupo_id: int, estudiante_id: int) -> dict:
    grupo = _grupo_o_404(grupo_id)
    estudiante_id = validar_minimo(validar_entero(estudiante_id, 'estudiante_id'), 1, 'estudiante_id')
    evaluacion = db.obtener_evaluacion(grupo['evaluacion_id'])
    inscripcion = db.obtener_inscripcion(evaluacion.get('cursada_id'), estudiante_id)

    if not inscripcion or inscripcion.get('estado') != ESTADO_CURSANDO:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_ESTUDIANTE_NOT_FOUND,
            message='Estudiante no inscripto',
            description='Solo se puede sumar a un alumno que esté cursando esta cursada.',
        ), 404)

    if _esta_en_la_evaluacion(grupo['evaluacion_id'], estudiante_id):
        raise ValueError(construir_error_api(
            code=ERROR_CODE_GRUPO_MIEMBRO,
            message='Ya integra un equipo',
            description='Ese alumno ya está en un equipo de esta evaluación.',
        ), 409)

    db.agregar_miembro(grupo_id, estudiante_id)

    return detalle(grupo_id)


def echar_integrante(grupo_id: int, estudiante_id: int) -> dict:
    grupo = _grupo_o_404(grupo_id)
    estudiante_id = validar_minimo(validar_entero(estudiante_id, 'estudiante_id'), 1, 'estudiante_id')
    ids = _ids_miembros(grupo_id)

    if estudiante_id not in ids:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_GRUPO_MIEMBRO,
            message='No integra el equipo',
            description='Ese alumno no está en el equipo.',
        ), 404)

    if grupo['owner_id'] == estudiante_id:
        otros = [miembro for miembro in ids if miembro != estudiante_id]

        if not otros:
            raise ValueError(construir_error_api(
                code=ERROR_CODE_GRUPO_OWNER,
                message='El equipo no puede quedar sin owner',
                description='Transferí el equipo o sumá a otra persona antes de echar a quien lo creó.',
            ), 409)

        db.actualizar_grupo(grupo_id, {'owner_id': min(otros)})

    db.quitar_miembro(grupo_id, estudiante_id)

    return detalle(grupo_id)


def transferir_integrante(grupo_id: int, estudiante_id: int, grupo_destino_id: int) -> dict:
    grupo = _grupo_o_404(grupo_id)
    destino = _grupo_o_404(grupo_destino_id)
    estudiante_id = validar_minimo(validar_entero(estudiante_id, 'estudiante_id'), 1, 'estudiante_id')

    if destino['evaluacion_id'] != grupo['evaluacion_id'] or destino['id'] == grupo['id']:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_GRUPO_MIEMBRO,
            message='Equipo de destino inválido',
            description='El destino tiene que ser otro equipo de la misma evaluación.',
        ), 400)

    ids = _ids_miembros(grupo_id)

    if estudiante_id not in ids:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_GRUPO_MIEMBRO,
            message='No integra el equipo',
            description='Ese alumno no está en el equipo.',
        ), 404)

    if grupo['owner_id'] == estudiante_id:
        otros = [miembro for miembro in ids if miembro != estudiante_id]

        if not otros:
            raise ValueError(construir_error_api(
                code=ERROR_CODE_GRUPO_OWNER,
                message='El equipo no puede quedar sin owner',
                description='Sumá a otra persona antes de transferir a quien creó el equipo.',
            ), 409)

        db.actualizar_grupo(grupo_id, {'owner_id': min(otros)})

    db.quitar_miembro(grupo_id, estudiante_id)
    db.agregar_miembro(destino['id'], estudiante_id)

    return detalle(grupo_id)


def _cursada_o_404(cursada_id: int) -> dict:
    cursada = db.obtener_cursada_por_id(cursada_id)

    if not cursada:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_CURSADA_NOT_FOUND,
            message='Cursada no encontrada',
            description=f"No existe una cursada con id '{cursada_id}'.",
        ), 404)

    return cursada


def _grupo_o_404(grupo_id: int) -> dict:
    grupo_id = validar_minimo(validar_entero(grupo_id, 'id'), 1, 'id')
    grupo = db.obtener_grupo(grupo_id)

    if not grupo:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_GRUPO_NOT_FOUND,
            message='Equipo no encontrado',
            description=f"No existe un equipo con id '{grupo_id}'.",
        ), 404)

    return grupo


def _tutor_valido(tutor_id):
    if tutor_id is None or str(tutor_id).strip() == '':
        return None

    tutor_id = validar_minimo(validar_entero(tutor_id, 'tutor_id'), 1, 'tutor_id')
    docente = db.obtener_docente_por_id(tutor_id)

    if not docente or docente.get('activo') is False:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_GRUPO_TUTOR,
            message='Tutor inválido',
            description='El tutor tiene que ser un docente activo.',
        ), 400)

    return tutor_id


def _esta_en_la_evaluacion(evaluacion_id: int, estudiante_id: int) -> bool:
    grupos = db.listar_grupos_de_evaluaciones([evaluacion_id])
    ocupados = {
        fila['estudiante_id']
        for fila in db.miembros_de_grupos([grupo['id'] for grupo in grupos])
    }

    return estudiante_id in ocupados


def _ids_miembros(grupo_id: int) -> list[int]:
    return [fila['estudiante_id'] for fila in db.miembros_de_grupos([grupo_id])]


def _agrupar_miembros(filas: list[dict]) -> dict:
    por_grupo = {}

    for fila in filas:
        por_grupo.setdefault(fila['grupo_id'], []).append(fila)

    return por_grupo


def _estudiante_de_inscripcion(fila: dict) -> dict:
    return fila.get('estudiantes') or {}


def _integrantes(filas: list[dict], owner_id: int) -> list[dict]:
    integrantes = []

    for fila in filas:
        estudiante = fila.get('estudiantes') or {}
        integrantes.append({
            'id': estudiante.get('id') or fila.get('estudiante_id'),
            'padron': estudiante.get('padron') or '',
            'nombre': estudiante.get('nombre') or '',
            'apellido': estudiante.get('apellido') or '',
            'owner': (estudiante.get('id') or fila.get('estudiante_id')) == owner_id,
        })

    return sorted(integrantes, key=lambda fila: (not fila['owner'], fila.get('apellido') or '', fila.get('nombre') or ''))


def _dto_base(grupo: dict) -> dict:
    tutor = db.obtener_docente_por_id(grupo['tutor_id']) if grupo.get('tutor_id') else {}

    return {
        'id': grupo['id'],
        'numero': grupo['numero'],
        'nombre': grupo['nombre'],
        'evaluacion_id': grupo['evaluacion_id'],
        'owner_id': grupo['owner_id'],
        'tutor_id': grupo.get('tutor_id'),
        'tutor_nombre': f"{tutor.get('nombre') or ''} {tutor.get('apellido') or ''}".strip(),
    }


def _dto_listado(grupo: dict, nombres: dict, miembros: list[dict]) -> dict:
    return {
        **_dto_base(grupo),
        'evaluacion_nombre': nombres.get(grupo['evaluacion_id']) or '',
        'integrantes': len(miembros),
    }
