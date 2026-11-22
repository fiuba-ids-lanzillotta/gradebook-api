"""Tests de GET /me/notas: las calificaciones del alumno."""
import pytest

import app as app_module
from gradebook_api import db, cache, registro
from gradebook_api.services import auth as auth_service
from gradebook_api.services.notas import cargar, mis_notas, notas_de
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


@pytest.fixture
def permitir_todo(monkeypatch):
    monkeypatch.setattr(auth_service, 'tiene_permiso', lambda payload, codigo: True)


@pytest.fixture
def espiar_registro(monkeypatch):
    llamadas = []
    monkeypatch.setattr(registro, 'registrar', lambda *args, **kwargs: llamadas.append((args, kwargs)))
    return llamadas


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


# ---------------------------------------------------------------
# GET /instancias/{id}/notas — vista docente (alumnos o equipos + nota)
# ---------------------------------------------------------------

INSTANCIA_FILA = {'id': 3, 'evaluacion_id': 7, 'numero': 1,
                  'nombre': '1er parcial', 'fecha': '2026-10-05', 'estado': 'abierta'}


def _mock_instancia(monkeypatch, evaluacion):
    monkeypatch.setattr(db, 'obtener_instancia', lambda instancia_id: INSTANCIA_FILA)
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: evaluacion)


def test_notas_de_instancia_individual(monkeypatch):
    _mock_instancia(monkeypatch, EVAL)
    monkeypatch.setattr(db, 'inscriptos_cursando', lambda cursada_id: [
        {'estudiante_id': 4, 'estudiantes': {'id': 4, 'padron': '105183', 'nombre': 'L', 'apellido': 'C'}},
        {'estudiante_id': 5, 'estudiantes': {'id': 5, 'padron': '115142', 'nombre': 'V', 'apellido': 'G'}},
    ])
    monkeypatch.setattr(db, 'notas_de_instancia', lambda instancia_id: [
        {'estudiante_id': 4, 'nota': 8.5, 'estado': None, 'observaciones': 'Bien',
         'corrector': CORRECTOR, 'corregido_at': '2026-10-10'},
    ])

    resultado = notas_de(3)
    con_nota, pendiente = resultado['items']

    assert resultado['evaluacion']['nombre'] == 'Parcial'
    assert resultado['instancia']['nombre'] == '1er parcial'
    assert con_nota['nota'] == 8.5 and con_nota['corrector'] == CORRECTOR
    assert pendiente['estudiante']['id'] == 5 and pendiente['nota'] is None


def test_notas_de_instancia_grupal(monkeypatch):
    _mock_instancia(monkeypatch, EVAL_GRUPAL)
    monkeypatch.setattr(db, 'listar_grupos_de_evaluaciones', lambda ids: [
        {'id': 9, 'evaluacion_id': 8, 'numero': 1, 'nombre': 'Halcones'},
    ])
    monkeypatch.setattr(db, 'miembros_de_grupos', lambda ids: [
        {'grupo_id': 9, 'estudiantes': {'id': 4, 'padron': '1', 'nombre': 'L', 'apellido': 'C'}},
    ])
    monkeypatch.setattr(db, 'notas_grupo_de_instancia', lambda instancia_id: [
        {'grupo_id': 9, 'nota': None, 'estado': 'aprobado', 'observaciones': None,
         'corrector': None, 'corregido_at': '2026-10-10'},
    ])

    item = notas_de(3)['items'][0]

    assert item['equipo']['nombre'] == 'Halcones'
    assert len(item['equipo']['integrantes']) == 1
    assert item['estado'] == 'aprobado'


def test_cargar_individual_upsert_y_audita(monkeypatch, espiar_registro):
    upserts = []
    _mock_instancia(monkeypatch, EVAL)
    monkeypatch.setattr(db, 'inscriptos_cursando', lambda cursada_id: [
        {'estudiante_id': 4, 'estudiantes': {}},
    ])
    monkeypatch.setattr(db, 'notas_de_instancia', lambda instancia_id: [])
    monkeypatch.setattr(db, 'upsert_nota',
                        lambda iid, eid, cid, datos: upserts.append((eid, cid, datos)))

    resultado = cargar(3, {'notas': [{'estudiante_id': 4, 'nota': 7,
                                    'observaciones': 'Ok'}]}, corrector_id=2)

    assert upserts == [(4, 2, {'nota': 7, 'estado': None, 'observaciones': 'Ok'})]
    assert '1 notas' in espiar_registro[0][0][1]
    assert 'items' in resultado


def test_cargar_grupal_valida_estado_y_grupo(monkeypatch):
    upserts = []
    _mock_instancia(monkeypatch, EVAL_GRUPAL)
    monkeypatch.setattr(db, 'listar_grupos_de_evaluaciones', lambda ids: [
        {'id': 9, 'evaluacion_id': 8, 'numero': 1, 'nombre': 'Halcones'},
    ])
    monkeypatch.setattr(db, 'miembros_de_grupos', lambda ids: [])
    monkeypatch.setattr(db, 'notas_grupo_de_instancia', lambda instancia_id: [])
    monkeypatch.setattr(db, 'upsert_nota_grupo',
                        lambda iid, gid, cid, datos: upserts.append((gid, datos)))

    cargar(3, {'notas': [{'grupo_id': 9, 'estado': 'aprobado'}]}, corrector_id=2)

    assert upserts == [(9, {'nota': None, 'estado': 'aprobado', 'observaciones': None})]

    with pytest.raises(ValueError):
        cargar(3, {'notas': [{'grupo_id': 99, 'estado': 'aprobado'}]}, corrector_id=2)

    with pytest.raises(ValueError):
        cargar(3, {'notas': [{'grupo_id': 9, 'estado': 'regular'}]}, corrector_id=2)


def test_cargar_valida_nota_del_criterio(monkeypatch):
    _mock_instancia(monkeypatch, EVAL)
    monkeypatch.setattr(db, 'inscriptos_cursando', lambda cursada_id: [
        {'estudiante_id': 4, 'estudiantes': {}},
    ])

    for body in ({'notas': [{'estudiante_id': 4, 'nota': 11}]},
                 {'notas': [{'estudiante_id': 4}]},
                 {'notas': [{'estudiante_id': 4, 'nota': 'ocho'}]}):
        with pytest.raises(ValueError):
            cargar(3, body, corrector_id=2)


def test_cargar_instancia_inexistente_404(monkeypatch):
    monkeypatch.setattr(db, 'obtener_instancia', lambda instancia_id: {})

    with pytest.raises(ValueError) as error:
        cargar(99, {'notas': [{'estudiante_id': 4, 'nota': 7}]}, corrector_id=2)

    assert error.value.args[1] == 404


def test_put_instancia_notas_200(client, monkeypatch, permitir_todo, espiar_registro):
    upserts = []
    _mock_instancia(monkeypatch, EVAL)
    monkeypatch.setattr(db, 'inscriptos_cursando', lambda cursada_id: [
        {'estudiante_id': 4, 'estudiantes': {}},
    ])
    monkeypatch.setattr(db, 'notas_de_instancia', lambda instancia_id: [])
    monkeypatch.setattr(db, 'upsert_nota',
                        lambda iid, eid, cid, datos: upserts.append(cid))

    respuesta = client.put('/gradebook_api/instancias/3/notas',
                           json={'notas': [{'estudiante_id': 4, 'nota': 7}]},
                           headers=_auth(tipo='docente'))

    assert respuesta.status_code == 200
    assert upserts == [4]
