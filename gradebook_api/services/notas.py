"""Lógica de calificaciones."""
from datetime import date

from .. import db, registro
from ..constants import (
    ACCION_NOTAS_CARGA,
    ERROR_CODE_CURSADA_NOT_FOUND,
    ERROR_CODE_ESTUDIANTE_NOT_FOUND,
    ERROR_CODE_INSCRIPCION_NOT_FOUND,
    ERROR_CODE_INSTANCIA_NOT_FOUND,
    ERROR_CODE_NOTA_INVALIDA,
)
from ..utils import construir_error_api, validar_entero, validar_minimo
from .evaluaciones import MODALIDAD_GRUPAL

CRITERIO_NOTA = 'nota'
ESTADOS_POR_CRITERIO = {
    'aprobado_desaprobado':  ('aprobado', 'desaprobado'),
    'entregado_no_entregado': ('entregado', 'no_entregado'),
}
NOTA_MINIMA, NOTA_MAXIMA = 0, 10


def mis_notas(estudiante_id: int) -> dict:
    """
    Las calificaciones del alumno ordenadas por evaluación e instancia:
    las individuales más las que sacaron los equipos que integra.
    """
    grupos = {
        fila['grupo']['id']: fila['grupo']
        for fila in db.grupos_de_estudiante(estudiante_id)
        if fila.get('grupo')
    }

    notas = [_dto_nota(fila) for fila in db.notas_de_estudiante(estudiante_id)]
    for fila in db.notas_grupo_de_grupos(list(grupos)):
        equipo = grupos[fila['grupo_id']]
        if _evaluacion_id(fila) == equipo['evaluacion_id']:
            notas.append(_dto_nota(fila, equipo))

    notas.sort(key=lambda item: (
        item['evaluacion'].get('nombre') or '',
        item['instancia'].get('numero') or 0,
    ))

    return {'notas': notas}


def _evaluacion_id(nota: dict):
    return (nota.get('instancia') or {}).get('evaluacion', {}).get('id')


def _dto_nota(fila: dict, equipo: dict = None) -> dict:
    instancia = fila.get('instancia') or {}

    return {
        'evaluacion':    instancia.get('evaluacion') or {},
        'instancia':     {campo: instancia.get(campo)
                          for campo in ('id', 'numero', 'nombre', 'fecha')},
        'equipo':        {'id': equipo['id'], 'nombre': equipo['nombre']} if equipo else None,
        'nota':          fila.get('nota'),
        'estado':        fila.get('estado'),
        'observaciones': fila.get('observaciones'),
        'corrector':     fila.get('corrector'),
        'corregido_at':  fila.get('corregido_at'),
    }


VISIBILIDAD_HABILITADA = 'habilitado'


def mis_calificaciones(estudiante_id: int) -> dict:
    """El mismo perfil que ve el docente, de la cursada que el alumno está cursando."""
    estudiante_id = validar_minimo(validar_entero(estudiante_id, 'estudiante_id'), 1, 'estudiante_id')
    cursada = _cursada_del_alumno(estudiante_id)

    if not cursada:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_INSCRIPCION_NOT_FOUND,
            message='No estás cursando',
            description='El perfil muestra las notas de la cursada en la que estás inscripto.',
        ), 404)

    return calificaciones_de(cursada['id'], estudiante_id)


def _cursada_del_alumno(estudiante_id: int) -> dict:
    """Entre las que cursa, la vigente; si ninguna lo está, la más reciente."""
    cursadas = [
        fila for fila in (
            db.obtener_cursada_por_id(inscripcion['cursada_id'])
            for inscripcion in db.inscripciones_cursando_de(estudiante_id)
        ) if fila
    ]
    hoy = date.today().isoformat()
    vigentes = [
        cursada for cursada in cursadas
        if (cursada.get('fecha_inicio') or '') <= hoy <= (cursada.get('fecha_fin') or '')
    ]

    return max(vigentes or cursadas, key=lambda cursada: (
        cursada.get('anio') or 0, cursada.get('cuatrimestre') or 0, cursada.get('id') or 0,
    ), default={})


def calificaciones_de(cursada_id: int, estudiante_id: int) -> dict:
    """
    Categorías habilitadas de la cursada, con las instancias y la nota del alumno.
    En una grupal, la nota es la del equipo; sin equipo, las instancias vienen sin nota.
    """
    cursada_id = validar_minimo(validar_entero(cursada_id, 'cursada_id'), 1, 'cursada_id')
    estudiante_id = validar_minimo(validar_entero(estudiante_id, 'estudiante_id'), 1, 'estudiante_id')

    if not db.obtener_cursada_por_id(cursada_id):
        raise ValueError(construir_error_api(
            code=ERROR_CODE_CURSADA_NOT_FOUND,
            message='Cursada no encontrada',
            description=f"No existe una cursada con id '{cursada_id}'.",
        ), 404)

    estudiante = db.obtener_estudiante_por_id(estudiante_id)

    if not estudiante:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_ESTUDIANTE_NOT_FOUND,
            message='Estudiante no encontrado',
            description=f"No existe un estudiante con id '{estudiante_id}'.",
        ), 404)

    if not db.inscripcion_en_cursada(estudiante_id, cursada_id):
        raise ValueError(construir_error_api(
            code=ERROR_CODE_INSCRIPCION_NOT_FOUND,
            message='El alumno no está en la cursada',
            description='El perfil muestra las notas de la cursada elegida.',
        ), 404)

    evaluaciones = [
        fila for fila in db.listar_evaluaciones(cursada_id)
        if fila.get('visibilidad') == VISIBILIDAD_HABILITADA
    ]
    instancias = db.instancias_de_evaluaciones([fila['id'] for fila in evaluaciones])
    por_evaluacion = {}

    for instancia in instancias:
        por_evaluacion.setdefault(instancia['evaluacion_id'], []).append(instancia)

    for lista in por_evaluacion.values():
        lista.sort(key=lambda item: item.get('numero') or 0)

    grupos = {}

    for fila in db.grupos_de_estudiante(estudiante_id):
        grupo = fila.get('grupo') or {}

        if grupo.get('evaluacion_id'):
            grupos[grupo['evaluacion_id']] = grupo

    notas = {
        (fila.get('instancia') or {}).get('id'): fila
        for fila in db.notas_de_estudiante(estudiante_id)
    }
    notas_grupo = {
        ((fila.get('instancia') or {}).get('id'), fila.get('grupo_id')): fila
        for fila in db.notas_grupo_de_grupos([grupo['id'] for grupo in grupos.values()])
    }

    return {
        'estudiante': {
            'id': estudiante.get('id'),
            'nombre': estudiante.get('nombre') or '',
            'apellido': estudiante.get('apellido') or '',
            'padron': estudiante.get('padron') or '',
        },
        'categorias': [
            _categoria(evaluacion, por_evaluacion.get(evaluacion['id'], []), grupos, notas, notas_grupo)
            for evaluacion in evaluaciones
        ],
    }


def vista_de_cursada(cursada_id: int, q: str = None) -> dict:
    """
    Planilla de la cursada: cada inscripto con su estado y la nota de cada
    instancia de las categorías habilitadas. En una grupal, la nota es la del equipo.
    """
    cursada_id = validar_minimo(validar_entero(cursada_id, 'cursada_id'), 1, 'cursada_id')
    cursada = db.obtener_cursada_por_id(cursada_id)

    if not cursada:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_CURSADA_NOT_FOUND,
            message='Cursada no encontrada',
            description=f"No existe una cursada con id '{cursada_id}'.",
        ), 404)

    evaluaciones = [
        fila for fila in db.listar_evaluaciones(cursada_id)
        if fila.get('visibilidad') == VISIBILIDAD_HABILITADA
    ]
    instancias = db.instancias_de_evaluaciones([fila['id'] for fila in evaluaciones])
    por_evaluacion = {}

    for instancia in instancias:
        por_evaluacion.setdefault(instancia['evaluacion_id'], []).append(instancia)

    for lista in por_evaluacion.values():
        lista.sort(key=lambda item: item.get('numero') or 0)

    ids = [instancia['id'] for instancia in instancias]
    notas = {
        (fila['estudiante_id'], fila['instancia_id']): fila
        for fila in db.notas_de_instancias(ids)
    }
    notas_grupo = {
        (fila['grupo_id'], fila['instancia_id']): fila
        for fila in db.notas_grupo_de_instancias(ids)
    }
    grupales = [fila['id'] for fila in evaluaciones if fila.get('modalidad') == MODALIDAD_GRUPAL]
    grupos = db.listar_grupos_de_evaluaciones(grupales)
    evaluacion_de_grupo = {grupo['id']: grupo['evaluacion_id'] for grupo in grupos}
    grupo_de = {
        (miembro['estudiante_id'], evaluacion_de_grupo[miembro['grupo_id']]): miembro['grupo_id']
        for miembro in db.miembros_de_grupos(list(evaluacion_de_grupo))
        if miembro['grupo_id'] in evaluacion_de_grupo
    }
    alumnos = []

    for fila in db.buscar_inscripciones_de_cursada(cursada['anio'], cursada['cuatrimestre'], q=q):
        estudiante = fila.get('estudiantes') or {}
        celdas = {}

        for evaluacion in evaluaciones:
            grupal = evaluacion.get('modalidad') == MODALIDAD_GRUPAL
            equipo = grupo_de.get((estudiante.get('id'), evaluacion['id'])) if grupal else None

            for instancia in por_evaluacion.get(evaluacion['id'], []):
                nota = notas_grupo.get((equipo, instancia['id'])) if grupal else notas.get((estudiante.get('id'), instancia['id']))
                celdas[str(instancia['id'])] = _celda(nota)

        alumnos.append({
            'id': estudiante.get('id'),
            'apellido': estudiante.get('apellido') or '',
            'nombre': estudiante.get('nombre') or '',
            'padron': estudiante.get('padron') or '',
            'email': estudiante.get('email') or '',
            'estado': fila.get('estado') or '',
            'notas': celdas,
        })

    alumnos.sort(key=lambda alumno: (alumno['apellido'].casefold(), alumno['nombre'].casefold(), alumno['padron']))

    return {
        'categorias': [
            {
                'id': evaluacion.get('id'),
                'nombre': evaluacion.get('nombre') or '',
                'criterio': evaluacion.get('criterio') or '',
                'instancias': [
                    {'id': instancia.get('id'), 'nombre': instancia.get('nombre') or '', 'numero': instancia.get('numero')}
                    for instancia in por_evaluacion.get(evaluacion['id'], [])
                ],
            }
            for evaluacion in evaluaciones
        ],
        'alumnos': alumnos,
    }


def _celda(nota: dict) -> dict:
    corrector = (nota or {}).get('corrector') if isinstance((nota or {}).get('corrector'), dict) else None
    apellido = ''

    if corrector:
        apellido = corrector.get('apellido') or corrector.get('nombre') or ''

    return {
        'nota': None if not nota else nota.get('nota'),
        'estado': None if not nota else nota.get('estado'),
        'corrector': apellido,
    }


def _categoria(evaluacion: dict, instancias: list, grupos: dict, notas: dict, notas_grupo: dict) -> dict:
    grupal = evaluacion.get('modalidad') == MODALIDAD_GRUPAL
    equipo = grupos.get(evaluacion['id']) if grupal else None

    return {
        'id': evaluacion.get('id'),
        'nombre': evaluacion.get('nombre') or '',
        'criterio': evaluacion.get('criterio') or '',
        'modalidad': evaluacion.get('modalidad') or '',
        'requiere_corrector': evaluacion.get('requiere_corrector') is not False,
        'equipo': {'id': equipo['id'], 'nombre': equipo.get('nombre') or ''} if equipo else None,
        'instancias': [
            _instancia_calificada(instancia, _nota_de(instancia['id'], grupal, equipo, notas, notas_grupo))
            for instancia in instancias
        ],
    }


def _nota_de(instancia_id: int, grupal: bool, equipo: dict, notas: dict, notas_grupo: dict) -> dict:
    if grupal:
        return notas_grupo.get((instancia_id, equipo['id'])) if equipo else None

    return notas.get(instancia_id)


def _instancia_calificada(instancia: dict, nota: dict) -> dict:
    corrector = (nota or {}).get('corrector') if isinstance((nota or {}).get('corrector'), dict) else None

    return {
        'id': instancia.get('id'),
        'numero': instancia.get('numero'),
        'nombre': instancia.get('nombre') or '',
        'nota': None if not nota else nota.get('nota'),
        'estado': None if not nota else nota.get('estado'),
        'corrector': None if not corrector else {
            'id': corrector.get('id'),
            'nombre': corrector.get('nombre') or '',
            'apellido': corrector.get('apellido') or '',
        },
    }


def notas_de(instancia_id: int) -> dict:
    """
    La instancia para el docente: evaluación e ítems a calificar — los alumnos
    inscriptos si es individual, los equipos si es grupal — con su nota (o
    pendiente si todavía no se cargó).
    """
    instancia, evaluacion = _instancia_y_evaluacion(instancia_id)
    items = (_items_grupales(instancia, evaluacion)
             if evaluacion.get('modalidad') == MODALIDAD_GRUPAL
             else _items_individuales(instancia, evaluacion))

    return {
        'evaluacion': {campo: evaluacion.get(campo)
                       for campo in ('id', 'nombre', 'modalidad', 'criterio', 'requiere_corrector')},
        'instancia':  {campo: instancia.get(campo)
                       for campo in ('id', 'numero', 'nombre', 'fecha', 'estado')},
        'items':      items,
    }


def cargar(instancia_id: int, body: dict, corrector_id) -> dict:
    """
    Carga/corrige masivamente las notas de la instancia.
    Body {notas: [{estudiante_id|grupo_id, nota?, estado?, observaciones?}]}
    según la evaluación sea individual o grupal; valida contra su criterio.
    """
    instancia, evaluacion = _instancia_y_evaluacion(instancia_id)
    grupal = evaluacion.get('modalidad') == MODALIDAD_GRUPAL
    entradas = _entradas_validas(body or {}, instancia, evaluacion, grupal)

    for destino_id, datos in entradas:
        if grupal:
            db.upsert_nota_grupo(instancia['id'], destino_id, corrector_id, datos)
        else:
            db.upsert_nota(instancia['id'], destino_id, corrector_id, datos)

    registro.registrar(
        ACCION_NOTAS_CARGA,
        f'Cargó {len(entradas)} notas en "{instancia.get("nombre")}" de "{evaluacion.get("nombre")}"',
        detalle={'instancia_id': instancia['id'], 'cantidad': len(entradas)},
        cursada_id=evaluacion.get('cursada_id'),
    )

    return notas_de(instancia_id)


def _instancia_y_evaluacion(instancia_id: int) -> tuple:
    instancia = db.obtener_instancia(
        validar_minimo(validar_entero(instancia_id, 'instancia_id'), 1, 'instancia_id'))
    if not instancia:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_INSTANCIA_NOT_FOUND,
            message='Instancia no encontrada',
            description=f'No existe una instancia con id {instancia_id}.',
        ), 404)

    return instancia, db.obtener_evaluacion(instancia['evaluacion_id']) or {}


def _items_individuales(instancia: dict, evaluacion: dict) -> list[dict]:
    """Un ítem por alumno inscripto, con su nota si ya se cargó."""
    notas = {fila['estudiante_id']: fila
             for fila in db.notas_de_instancia(instancia['id'])}

    return [
        {'estudiante': inscripcion['estudiantes'],
         **_campos_nota(notas.get(inscripcion['estudiante_id']))}
        for inscripcion in db.inscriptos_cursando(evaluacion['cursada_id'])
    ]


def _items_grupales(instancia: dict, evaluacion: dict) -> list[dict]:
    """Un ítem por equipo de la evaluación, con sus integrantes y su nota si ya se cargó."""
    grupos = db.listar_grupos_de_evaluaciones([evaluacion['id']])
    miembros = db.miembros_de_grupos([grupo['id'] for grupo in grupos])
    notas = {fila['grupo_id']: fila
             for fila in db.notas_grupo_de_instancia(instancia['id'])}

    return [
        {'equipo': {'id': grupo['id'], 'numero': grupo['numero'], 'nombre': grupo['nombre'],
                    'integrantes': [fila['estudiantes'] for fila in miembros
                                    if fila['grupo_id'] == grupo['id']]},
         **_campos_nota(notas.get(grupo['id']))}
        for grupo in grupos
    ]


def _campos_nota(fila: dict) -> dict:
    fila = fila or {}

    return {'nota': fila.get('nota'), 'estado': fila.get('estado'),
            'observaciones': fila.get('observaciones'),
            'corrector': fila.get('corrector'), 'corregido_at': fila.get('corregido_at')}


def _entradas_validas(body: dict, instancia: dict, evaluacion: dict, grupal: bool) -> list:
    """Valida el body de carga y devuelve [(destino_id, {nota|estado, observaciones})]."""
    notas = body.get('notas')
    if not isinstance(notas, list) or not notas:
        raise _nota_invalida('Body inválido', 'Se espera {notas: [...]} con al menos una nota.')

    validos = _destinos_validos(evaluacion, grupal)
    clave = 'grupo_id' if grupal else 'estudiante_id'
    entradas = []

    for posicion, entrada in enumerate(notas):
        destino_id = _destino_id(entrada, clave, validos)
        datos = _datos_calificacion(entrada, evaluacion.get('criterio'), posicion)
        entradas.append((destino_id, datos))

    return entradas


def _destinos_validos(evaluacion: dict, grupal: bool) -> set:
    if grupal:
        return {grupo['id']
                for grupo in db.listar_grupos_de_evaluaciones([evaluacion['id']])}

    return {inscripcion['estudiante_id']
            for inscripcion in db.inscriptos_cursando(evaluacion['cursada_id'])}


def _destino_id(entrada: dict, clave: str, validos: set) -> int:
    destino_id = entrada.get(clave) if isinstance(entrada, dict) else None

    if not isinstance(destino_id, int) or destino_id not in validos:
        raise _nota_invalida(
            'Destino inválido',
            f'El {clave} {destino_id} no existe o no corresponde a esta evaluación.')

    return destino_id


def _datos_calificacion(entrada: dict, criterio: str, posicion: int) -> dict:
    """Valida nota/estado según el criterio de la evaluación."""
    datos = {'observaciones': (entrada.get('observaciones') or '').strip() or None}

    if criterio == CRITERIO_NOTA:
        nota = entrada.get('nota')
        if not isinstance(nota, (int, float)) or isinstance(nota, bool) \
                or not NOTA_MINIMA <= nota <= NOTA_MAXIMA:
            raise _nota_invalida(
                'Nota inválida',
                f'La nota #{posicion + 1} debe ser un número entre {NOTA_MINIMA} y {NOTA_MAXIMA}.')
        datos.update({'nota': nota, 'estado': None})
    else:
        estados = ESTADOS_POR_CRITERIO.get(criterio, ())
        if entrada.get('estado') not in estados:
            raise _nota_invalida(
                'Estado inválido',
                f'La nota #{posicion + 1} debe tener estado {" o ".join(estados)}.')
        datos.update({'nota': None, 'estado': entrada['estado']})

    return datos


def _nota_invalida(message: str, description: str) -> ValueError:
    return ValueError(construir_error_api(
        code=ERROR_CODE_NOTA_INVALIDA,
        message=message,
        description=description,
    ), 400)
