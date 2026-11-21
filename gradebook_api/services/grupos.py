"""Equipos de las evaluaciones grupales de una cursada."""
import random

from ..constants import (
    ERROR_CODE_CURSADA_NOT_FOUND,
    ERROR_CODE_ESTUDIANTE_NOT_FOUND,
    ERROR_CODE_GRUPO_MIEMBRO,
    ERROR_CODE_GRUPO_NOT_FOUND,
    ERROR_CODE_GRUPO_OWNER,
    ERROR_CODE_GRUPO_TUTOR,
    ERROR_CODE_INVALID_BODY,
    ERROR_CODE_SIN_PERMISO,
    ERROR_CODE_GRUPOS_CERRADOS,
    ACCION_GRUPO_CREAR,
    ACCION_GRUPO_TUTORES,
    ACCION_GRUPO_RENOMBRAR,
    ACCION_GRUPO_AGREGAR,
    ACCION_GRUPO_ECHAR,
    ACCION_GRUPO_TRANSFERIR,
    ACCION_GRUPO_SALIR,
)
from ..utils import construir_error_api, validar_entero, validar_minimo
from .. import db, registro

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
    grupo = _grupo_o_404(grupo_id)
    limpio = (nombre or '').strip()

    if not limpio or len(limpio) > MAXIMO_NOMBRE_GRUPO:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_INVALID_BODY,
            message='Nombre inválido',
            description=f'El nombre del equipo es obligatorio y de hasta {MAXIMO_NOMBRE_GRUPO} caracteres.',
        ), 400)

    db.actualizar_grupo(grupo_id, {'nombre': limpio})
    registro.registrar(
        ACCION_GRUPO_RENOMBRAR,
        f'Renombró el equipo "{grupo.get("nombre")}" a "{limpio}"',
        detalle={'grupo_id': grupo['id'], 'nombre_anterior': grupo.get('nombre'), 'nombre_nuevo': limpio},
        cursada_id=_cursada_id_del_grupo(grupo),
    )

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

    registro.registrar(
        ACCION_GRUPO_TUTORES,
        f'Asignó tutores a {len(asignaciones)} equipos',
        detalle={'asignaciones': asignaciones, 'sin_tutor': sin_tutor},
    )

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
    registro.registrar(
        ACCION_GRUPO_AGREGAR,
        f'Sumó a {_etiqueta_estudiante(estudiante_id)} al equipo "{grupo.get("nombre")}"',
        detalle={'grupo_id': grupo['id'], 'estudiante_id': estudiante_id},
        cursada_id=evaluacion.get('cursada_id'),
    )

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
    registro.registrar(
        ACCION_GRUPO_ECHAR,
        f'Echó a {_etiqueta_estudiante(estudiante_id)} del equipo "{grupo.get("nombre")}"',
        detalle={'grupo_id': grupo['id'], 'estudiante_id': estudiante_id},
        cursada_id=_cursada_id_del_grupo(grupo),
    )

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
    registro.registrar(
        ACCION_GRUPO_TRANSFERIR,
        f'Transfirió a {_etiqueta_estudiante(estudiante_id)} del equipo "{grupo.get("nombre")}" a "{destino.get("nombre")}"',
        detalle={'grupo_id': grupo['id'], 'grupo_destino_id': destino['id'], 'estudiante_id': estudiante_id},
        cursada_id=_cursada_id_del_grupo(grupo),
    )

    return detalle(grupo_id)


def mi_equipo(estudiante_id: int, con_candidatos: bool = False) -> dict:
    """El equipo del alumno en la evaluación que tiene abierta la creación, o el que ya integra."""
    estudiante_id = validar_minimo(validar_entero(estudiante_id, 'id'), 1, 'id')
    yo = db.obtener_estudiante_por_id(estudiante_id)
    evaluaciones = _evaluaciones_de_sus_cursadas(estudiante_id)
    abierta = _abierta(evaluaciones)
    grupo = _grupo_en(abierta.get('id'), estudiante_id) if abierta else {}
    evaluacion = abierta

    if not grupo:
        grupo, evaluacion_del_grupo = _primer_grupo(evaluaciones, estudiante_id)
        evaluacion = abierta or evaluacion_del_grupo

    puede_crear = bool(abierta) and not _grupo_en(abierta.get('id'), estudiante_id)
    puede_editar = bool(grupo) and grupo.get('owner_id') == estudiante_id and bool(evaluacion.get('permite_crear_grupos'))
    grupo_dto = _grupo_alumno(grupo, estudiante_id) if grupo else None

    if con_candidatos and puede_editar and grupo_dto:
        grupo_dto['candidatos'] = _candidatos(evaluacion.get('id'), evaluacion.get('cursada_id'))

    return {
        'yo': _yo(yo),
        'evaluacion': _evaluacion_dto(evaluacion),
        'puede_crear': puede_crear,
        'puede_editar': puede_editar,
        'grupo': grupo_dto,
    }


def crear_mi_equipo(estudiante_id: int, nombre: str, padrones: list) -> dict:
    """Crea el equipo del alumno en la única evaluación con creación habilitada."""
    estudiante_id = validar_minimo(validar_entero(estudiante_id, 'id'), 1, 'id')
    abierta = _abierta(_evaluaciones_de_sus_cursadas(estudiante_id))

    if not abierta:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_GRUPOS_CERRADOS,
            message='La creación de equipos está cerrada',
            description='La cátedra no habilitó la creación de equipos.',
        ), 409)

    if _grupo_en(abierta['id'], estudiante_id):
        raise ValueError(construir_error_api(
            code=ERROR_CODE_GRUPO_MIEMBRO,
            message='Ya integrás un equipo',
            description='Ya estás en un equipo de esta evaluación.',
        ), 409)

    limpio = _nombre_valido(nombre)
    ids = _resolver_padrones(abierta, estudiante_id, padrones)
    numero = db.proximo_numero_grupo(abierta['id'])
    grupo = db.insertar_grupo(abierta['id'], numero, limpio, estudiante_id)
    db.agregar_miembro(grupo['id'], estudiante_id)

    for integrante_id in ids:
        db.agregar_miembro(grupo['id'], integrante_id)

    registro.registrar(
        ACCION_GRUPO_CREAR,
        f'Creó el equipo "{limpio}"',
        detalle={'grupo_id': grupo.get('id'), 'evaluacion_id': abierta['id']},
        cursada_id=abierta.get('cursada_id'),
    )

    return mi_equipo(estudiante_id)


def renombrar_mi_equipo(estudiante_id: int, nombre: str) -> dict:
    """El owner cambia el nombre mientras la creación de esa evaluación sigue habilitada."""
    estudiante_id = validar_minimo(validar_entero(estudiante_id, 'id'), 1, 'id')
    grupo, evaluacion = _equipo_editable(estudiante_id)
    limpio = _nombre_valido(nombre)
    anterior = grupo.get('nombre')
    db.actualizar_grupo(grupo['id'], {'nombre': limpio})
    registro.registrar(
        ACCION_GRUPO_RENOMBRAR,
        f'Renombró el equipo "{anterior}" a "{limpio}"',
        detalle={'grupo_id': grupo['id'], 'nombre_anterior': anterior, 'nombre_nuevo': limpio},
        cursada_id=evaluacion.get('cursada_id'),
    )

    return mi_equipo(estudiante_id)


def agregar_por_padron(estudiante_id: int, padron: str) -> dict:
    """El owner suma a un alumno por padrón mientras la creación sigue habilitada."""
    estudiante_id = validar_minimo(validar_entero(estudiante_id, 'id'), 1, 'id')
    grupo, evaluacion = _equipo_editable(estudiante_id)
    ids = _resolver_padrones(evaluacion, estudiante_id, [padron])

    if not ids:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_INVALID_BODY,
            message='Padrón inválido',
            description='Ingresá el padrón de un alumno que no seas vos.',
        ), 400)

    db.agregar_miembro(grupo['id'], ids[0])
    registro.registrar(
        ACCION_GRUPO_AGREGAR,
        f'Sumó un integrante al equipo "{grupo.get("nombre")}"',
        detalle={'grupo_id': grupo['id'], 'estudiante_id': ids[0]},
        cursada_id=evaluacion.get('cursada_id'),
    )

    return mi_equipo(estudiante_id)


def salir_de_mi_equipo(estudiante_id: int) -> dict:
    """El alumno deja su equipo. Si es el owner y hay otros, la corona pasa a uno al azar."""
    estudiante_id = validar_minimo(validar_entero(estudiante_id, 'id'), 1, 'id')
    estado = mi_equipo(estudiante_id)
    grupo = estado.get('grupo') or {}
    evaluacion = estado.get('evaluacion') or {}

    if not grupo:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_GRUPO_MIEMBRO,
            message='No integrás un equipo',
            description='No estás en un equipo del que puedas salir.',
        ), 404)

    grupo_db = _grupo_en(evaluacion.get('id'), estudiante_id)
    otros = [miembro for miembro in _ids_miembros(grupo_db['id']) if miembro != estudiante_id]

    if grupo_db.get('owner_id') == estudiante_id and not otros:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_GRUPO_OWNER,
            message='El equipo no puede quedar sin owner',
            description='Si sos el único integrante, no podés salir del equipo.',
        ), 409)

    if grupo_db.get('owner_id') == estudiante_id:
        db.actualizar_grupo(grupo_db['id'], {'owner_id': random.choice(otros)})

    db.quitar_miembro(grupo_db['id'], estudiante_id)
    registro.registrar(
        ACCION_GRUPO_SALIR,
        f'Salió del equipo "{grupo_db.get("nombre")}"',
        detalle={'grupo_id': grupo_db['id'], 'estudiante_id': estudiante_id},
        cursada_id=evaluacion.get('cursada_id'),
    )

    return mi_equipo(estudiante_id)


def _candidatos(evaluacion_id, cursada_id) -> list[dict]:
    """Alumnos cursando que todavía no están en un equipo de esa evaluación."""
    if not evaluacion_id or not cursada_id:
        return []

    grupos = db.listar_grupos_de_evaluaciones([evaluacion_id])
    ocupados = {
        fila['estudiante_id']
        for fila in db.miembros_de_grupos([item['id'] for item in grupos])
    }

    return [
        estudiante
        for fila in db.inscriptos_cursando(cursada_id)
        for estudiante in [_estudiante_de_inscripcion(fila)]
        if estudiante.get('id') and estudiante['id'] not in ocupados
    ]


def _equipo_editable(estudiante_id: int) -> tuple:
    estado = mi_equipo(estudiante_id)
    grupo = estado.get('grupo') or {}
    evaluacion = estado.get('evaluacion') or {}

    if not grupo or not estado.get('puede_editar'):
        raise ValueError(construir_error_api(
            code=ERROR_CODE_SIN_PERMISO,
            message='No podés modificar el equipo',
            description='Solo quien creó el equipo puede cambiarlo, y solo mientras la creación esté habilitada.',
        ), 403)

    return _grupo_en(evaluacion.get('id'), estudiante_id), evaluacion


def _evaluaciones_de_sus_cursadas(estudiante_id: int) -> list[dict]:
    evaluaciones = []

    for inscripcion in db.inscripciones_cursando_de(estudiante_id):
        evaluaciones.extend(db.listar_evaluaciones_grupales(inscripcion['cursada_id']))

    return evaluaciones


def _abierta(evaluaciones: list[dict]) -> dict:
    """La evaluación con creación de equipos habilitada. El producto admite una sola."""
    for evaluacion in evaluaciones:
        if evaluacion.get('permite_crear_grupos'):
            return evaluacion

    return {}


def _primer_grupo(evaluaciones: list[dict], estudiante_id: int) -> tuple:
    for evaluacion in evaluaciones:
        grupo = _grupo_en(evaluacion.get('id'), estudiante_id)

        if grupo:
            return grupo, evaluacion

    return {}, {}


def _grupo_en(evaluacion_id, estudiante_id: int) -> dict:
    if not evaluacion_id:
        return {}

    grupos = {fila['id']: fila for fila in db.listar_grupos_de_evaluaciones([evaluacion_id])}

    for miembro in db.miembros_de_grupos(list(grupos)):
        if miembro.get('estudiante_id') == estudiante_id:
            return grupos.get(miembro.get('grupo_id')) or {}

    return {}


def _nombre_valido(nombre: str) -> str:
    limpio = (nombre or '').strip()

    if not limpio or len(limpio) > MAXIMO_NOMBRE_GRUPO:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_INVALID_BODY,
            message='Nombre inválido',
            description=f'El nombre del equipo es obligatorio y de hasta {MAXIMO_NOMBRE_GRUPO} caracteres.',
        ), 400)

    return limpio


def _resolver_padrones(evaluacion: dict, owner_id: int, padrones: list) -> list[int]:
    """Ids a sumar. El padrón del owner se ignora. Falla si no existe, no cursa o ya tiene equipo."""
    if not isinstance(padrones, list):
        padrones = []

    ids = []
    vistos = set()

    for crudo in padrones:
        limpio = str(crudo or '').strip()
        repetido = not limpio or limpio in vistos

        if not repetido:
            vistos.add(limpio)
            ids.extend(_id_para_sumar(evaluacion, owner_id, limpio))

    return ids


def _id_para_sumar(evaluacion: dict, owner_id: int, padron: str) -> list[int]:
    estudiante = db.obtener_estudiante_por_padron(padron)

    if not estudiante:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_ESTUDIANTE_NOT_FOUND,
            message='Alumno no encontrado',
            description=f'No hay un alumno con padrón {padron}.',
        ), 404)

    if estudiante['id'] == owner_id:
        return []

    inscripcion = db.obtener_inscripcion(evaluacion.get('cursada_id'), estudiante['id'])

    if not inscripcion or inscripcion.get('estado') != ESTADO_CURSANDO:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_ESTUDIANTE_NOT_FOUND,
            message='Alumno no inscripto',
            description=f'El padrón {padron} no está cursando esta materia.',
        ), 404)

    if _grupo_en(evaluacion.get('id'), estudiante['id']):
        raise ValueError(construir_error_api(
            code=ERROR_CODE_GRUPO_MIEMBRO,
            message='Ya integra un equipo',
            description=f'El padrón {padron} ya está en un equipo de esta evaluación.',
        ), 409)

    return [estudiante['id']]


def _yo(estudiante: dict) -> dict:
    return {
        'id': estudiante.get('id'),
        'padron': estudiante.get('padron') or '',
        'nombre': estudiante.get('nombre') or '',
        'apellido': estudiante.get('apellido') or '',
    }


def _evaluacion_dto(evaluacion: dict) -> dict:
    if not evaluacion:
        return None

    return {
        'id': evaluacion.get('id'),
        'nombre': evaluacion.get('nombre') or '',
        'cursada_id': evaluacion.get('cursada_id'),
        'permite_crear_grupos': bool(evaluacion.get('permite_crear_grupos')),
    }


def _grupo_alumno(grupo: dict, estudiante_id: int) -> dict:
    return {
        'id': grupo.get('id'),
        'nombre': grupo.get('nombre') or '',
        'soy_owner': grupo.get('owner_id') == estudiante_id,
        'integrantes': _integrantes(db.miembros_de_grupos([grupo['id']]), grupo.get('owner_id')),
    }


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


def _cursada_id_del_grupo(grupo: dict):
    """cursada_id de la evaluación del grupo (para el registro; None si falla la consulta)."""
    try:
        evaluacion = db.obtener_evaluacion(grupo['evaluacion_id']) or {}
    except Exception:
        evaluacion = {}

    return evaluacion.get('cursada_id')


def _etiqueta_estudiante(estudiante_id: int) -> str:
    """Nombre legible del estudiante para la descripción del registro (degrada al id si falla la consulta)."""
    try:
        estudiante = db.obtener_estudiante_por_id(estudiante_id) or {}
    except Exception:
        estudiante = {}

    if not estudiante:
        return f'el estudiante {estudiante_id}'

    return f"{estudiante.get('apellido')}, {estudiante.get('nombre')} (padrón {estudiante.get('padron')})"


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
