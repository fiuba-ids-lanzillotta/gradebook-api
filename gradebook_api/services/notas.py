"""Lógica de calificaciones."""
from .. import db


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
