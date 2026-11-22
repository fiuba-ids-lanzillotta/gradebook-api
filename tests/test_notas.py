"""Tests de GET /me/notas: las calificaciones del alumno."""
import pytest

import app as app_module
from gradebook_api import db, cache
from gradebook_api.services.notas import mis_notas
from gradebook_api.utils import generar_token


EVAL = {'id': 7, 'nombre': 'Parcial', 'modalidad': 'individual',
        'criterio': 'nota', 'cursada_id': 1}
EVAL_GRUPAL = {'id': 8, 'nombre': 'TP Backend', 'modalidad': 'grupal',
               'criterio': 'aprobado_desaprobado', 'cursada_id': 1}
INSTANCIA = {'id': 3, 'numero': 1, 'nombre': '1er parcial', 'fecha': '2026-10-05'}
CORRECTOR = {'id': 2, 'nombre': 'Ana', 'apellido': 'Gomez'}


def _nota(**extra):
    return {'id': 1, 'nota': 7.5, 'estado': None, 'observaciones': 'Bien',
            'corregido_at': '2026-10-10', 'corrector': CORRECTOR,
            'instancia': {**INSTANCIA, 'evaluacion': EVAL}, **extra}


@pytest.fixture
def client():
    app_module.app.config['TESTING'] = True
    return app_module.app.test_client()


@pytest.fixture(autouse=True)
def _cache_desactivado(monkeypatch):
    monkeypatch.setattr(cache, 'obtener', lambda clave: None)
    monkeypatch.setattr(cache, 'guardar', lambda clave, valor, ttl: None)
    monkeypatch.setattr(cache, 'invalidar', lambda *claves: None)


def _auth(tipo='estudiante'):
    return {'Authorization': f'Bearer {generar_token(4, tipo, "usuario", "a@fi.uba.ar")}'}


def test_mis_notas_individuales_y_de_equipo(monkeypatch):
    monkeypatch.setattr(db, 'notas_de_estudiante', lambda estudiante_id: [_nota()])
    monkeypatch.setattr(db, 'grupos_de_estudiante', lambda estudiante_id: [
        {'grupo': {'id': 9, 'evaluacion_id': 8, 'nombre': 'Halcones'}},
    ])
    monkeypatch.setattr(db, 'notas_grupo_de_grupos', lambda grupo_ids: [
        _nota(grupo_id=9, nota=None, estado='aprobado',
              instancia={**INSTANCIA, 'evaluacion': EVAL_GRUPAL}),
    ])

    resultado = mis_notas(4)
    individuales, de_equipo = resultado['notas']

    assert len(resultado['notas']) == 2
    assert individuales['equipo'] is None
    assert individuales['evaluacion']['nombre'] == 'Parcial'
    assert individuales['nota'] == 7.5
    assert individuales['corrector'] == CORRECTOR
    assert de_equipo['equipo'] == {'id': 9, 'nombre': 'Halcones'}
    assert de_equipo['estado'] == 'aprobado'


def test_mis_notas_descarta_nota_de_equipo_de_otra_evaluacion(monkeypatch):
    """Una nota_grupo solo cuenta si la instancia es de la evaluación del equipo."""
    monkeypatch.setattr(db, 'notas_de_estudiante', lambda estudiante_id: [])
    monkeypatch.setattr(db, 'grupos_de_estudiante', lambda estudiante_id: [
        {'grupo': {'id': 9, 'evaluacion_id': 8, 'nombre': 'Halcones'}},
    ])
    monkeypatch.setattr(db, 'notas_grupo_de_grupos', lambda grupo_ids: [
        _nota(grupo_id=9, instancia={**INSTANCIA, 'evaluacion': EVAL}),
    ])

    assert mis_notas(4)['notas'] == []


def test_mis_notas_sin_notas(monkeypatch):
    monkeypatch.setattr(db, 'notas_de_estudiante', lambda estudiante_id: [])
    monkeypatch.setattr(db, 'grupos_de_estudiante', lambda estudiante_id: [])
    monkeypatch.setattr(db, 'notas_grupo_de_grupos', lambda grupo_ids: [])

    assert mis_notas(4) == {'notas': []}


def test_get_me_notas_200(client, monkeypatch):
    monkeypatch.setattr(db, 'notas_de_estudiante', lambda estudiante_id: [_nota()])
    monkeypatch.setattr(db, 'grupos_de_estudiante', lambda estudiante_id: [])
    monkeypatch.setattr(db, 'notas_grupo_de_grupos', lambda grupo_ids: [])

    respuesta = client.get('/gradebook_api/me/notas', headers=_auth())

    assert respuesta.status_code == 200
    notas = respuesta.get_json()['notas']
    assert notas[0]['evaluacion']['nombre'] == 'Parcial'
    assert notas[0]['instancia']['nombre'] == '1er parcial'
    assert notas[0]['instancia']['fecha'] == '2026-10-05'
    assert notas[0]['corrector']['apellido'] == 'Gomez'


def test_get_me_notas_docente_403(client):
    respuesta = client.get('/gradebook_api/me/notas',
                           headers=_auth(tipo='docente'))

    assert respuesta.status_code == 403
