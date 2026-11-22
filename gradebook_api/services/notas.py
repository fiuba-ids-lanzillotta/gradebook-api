"""Lógica de calificaciones."""
from .. import db, registro
from ..constants import (
    ACCION_NOTAS_CARGA,
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
