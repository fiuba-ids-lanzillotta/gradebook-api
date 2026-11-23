"""Tests de GET /cursadas/{id}/metricas: estadísticas del dashboard."""
import pytest

import app as app_module
from gradebook_api import db, cache
from gradebook_api.services import auth as auth_service
from gradebook_api.services.metricas import metricas
from gradebook_api.utils import generar_token


CURSADA = {'id': 1, 'codigo': '75.47', 'anio': 2026, 'cuatrimestre': 2}
PARCIAL = {'id': 10, 'nombre': 'Parcial', 'modalidad': 'individual',
           'criterio': 'nota', 'tipo': 'obligatorio', 'visibilidad': 'habilitado',
           'cursada_id': 1}
TP = {'id': 11, 'nombre': 'TP Backend', 'modalidad': 'grupal',
      'criterio': 'aprobado_desaprobado', 'tipo': 'obligatorio',
      'visibilidad': 'habilitado', 'permite_crear_grupos': True, 'cursada_id': 1}
INST_1 = {'id': 20, 'evaluacion_id': 10, 'numero': 1,
          'nombre': '1er parcial', 'fecha': '2026-10-05', 'estado': 'cerrada'}
INST_2 = {'id': 21, 'evaluacion_id': 10, 'numero': 2,
          'nombre': 'Recuperatorio', 'fecha': '2026-11-02', 'estado': 'cerrada'}
INST_TP = {'id': 22, 'evaluacion_id': 11, 'numero': 1,
           'nombre': 'Entrega', 'fecha': '2026-11-20', 'estado': 'abierta'}
ANA = {'id': 2, 'nombre': 'Ana', 'apellido': 'Gomez'}
LUIS = {'id': 3, 'nombre': 'Luis', 'apellido': 'Paz'}


def _inscripciones():
    return [
        {'estudiante_id': 4, 'estado': 'cursando'},
        {'estudiante_id': 5, 'estado': 'cursando'},
        {'estudiante_id': 6, 'estado': 'baja'},
        {'estudiante_id': 7, 'estado': 'abandono'},
    ]


def _mock_db(monkeypatch, evaluaciones=None, instancias=None, inscripciones=None,
             grupos=None, miembros=None, notas=None, notas_grupo=None,
             docentes=None):
    monkeypatch.setattr(db, 'obtener_cursada_por_id', lambda cursada_id: CURSADA)
    monkeypatch.setattr(db, 'listar_evaluaciones',
                        lambda cursada_id: evaluaciones or [])
    monkeypatch.setattr(db, 'instancias_de_evaluaciones',
                        lambda eval_ids: instancias or [])
    monkeypatch.setattr(db, 'inscripciones_de_cursada',
                        lambda cursada_id: inscripciones or [])
    monkeypatch.setattr(db, 'listar_grupos_de_evaluaciones',
                        lambda eval_ids: grupos or [])
    monkeypatch.setattr(db, 'miembros_de_grupos',
                        lambda grupo_ids: miembros or [])
    monkeypatch.setattr(db, 'notas_en_instancias',
                        lambda instancia_ids: notas or [])
    monkeypatch.setattr(db, 'notas_grupo_en_instancias',
                        lambda instancia_ids: notas_grupo or [])
    monkeypatch.setattr(db, 'obtener_todos_los_docentes',
                        lambda: docentes or [])


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


def _auth(tipo='docente', rol='admin'):
    return {'Authorization': f'Bearer {generar_token(1, tipo, rol, "d@fi.uba.ar")}'}


def test_metricas_cursada_vacia(monkeypatch):
    _mock_db(monkeypatch)

    resultado = metricas(1)

    assert resultado['alumnos'] == {'total': 0, 'cursando': 0, 'baja': 0,
                                    'abandono': 0, 'promocionados': 0}
    assert resultado['instancias'] == []
    assert resultado['equipos'] == {'total': 0, 'sin_equipo': None}
    assert resultado['docentes'] == []


def test_metricas_cursada_inexistente(monkeypatch):
    monkeypatch.setattr(db, 'obtener_cursada_por_id', lambda cursada_id: None)

    with pytest.raises(ValueError) as error:
        metricas(99)

    assert error.value.args[1] == 404


def test_metricas_instancia_individual(monkeypatch):
    _mock_db(
        monkeypatch,
        evaluaciones=[PARCIAL],
        instancias=[INST_1, INST_2],
        inscripciones=_inscripciones(),
        notas=[
            {'instancia_id': 20, 'estudiante_id': 4, 'nota': 8.0,
             'estado': None, 'corrector_id': 2},
            {'instancia_id': 20, 'estudiante_id': 5, 'nota': 3.0,
             'estado': None, 'corrector_id': 3},
            {'instancia_id': 21, 'estudiante_id': 5, 'nota': 6.0,
             'estado': None, 'corrector_id': 2},
        ],
        docentes=[ANA, LUIS],
    )

    resultado = metricas(1)

    assert resultado['alumnos']['total'] == 4
    assert resultado['alumnos']['cursando'] == 2
    assert resultado['alumnos']['baja'] == 1
    assert resultado['alumnos']['abandono'] == 1

    primero, recup = resultado['instancias']
    assert primero['instancia']['nombre'] == '1er parcial'
    assert primero['rendidos'] == 2
    assert primero['pendientes'] == 0
    assert primero['promedio'] == 5.5
    assert [item['cantidad'] for item in primero['por_corrector']] == [1, 1]
    assert {item['docente']['nombre'] for item in primero['por_corrector']} == {'Ana', 'Luis'}

    assert recup['rendidos'] == 1
    assert recup['pendientes'] == 1
    assert recup['promedio'] == 6.0

    # Alumno 4 aprobó en el parcial; el 5 desaprobó el 1ero pero aprobó el recup
    # → la última instancia con nota es la que vale: los dos promocionan.
    assert resultado['alumnos']['promocionados'] == 2


def test_metricas_promocionados_ultima_instancia_desaprobada(monkeypatch):
    """Si la última instancia rendida está desaprobada, no promociona aunque
    haya aprobado antes."""
    _mock_db(
        monkeypatch,
        evaluaciones=[PARCIAL],
        instancias=[INST_1, INST_2],
        inscripciones=[{'estudiante_id': 4, 'estado': 'cursando'}],
        notas=[
            {'instancia_id': 20, 'estudiante_id': 4, 'nota': 8.0,
             'estado': None, 'corrector_id': 2},
            {'instancia_id': 21, 'estudiante_id': 4, 'nota': 2.0,
             'estado': None, 'corrector_id': 2},
        ],
    )

    assert metricas(1)['alumnos']['promocionados'] == 0


def test_metricas_grupal_y_sin_equipo(monkeypatch):
    """Rendidos por equipo, pendientes por equipo sin nota y sin_equipo
    cuenta los cursando fuera de la evaluación con creación abierta."""
    _mock_db(
        monkeypatch,
        evaluaciones=[TP],
        instancias=[INST_TP],
        inscripciones=_inscripciones(),
        grupos=[
            {'id': 30, 'evaluacion_id': 11, 'nombre': 'Halcones', 'tutor_id': 2},
            {'id': 31, 'evaluacion_id': 11, 'nombre': 'Pumas', 'tutor_id': 2},
        ],
        miembros=[
            {'grupo_id': 30, 'estudiante_id': 4},
            {'grupo_id': 31, 'estudiante_id': 5},
        ],
        notas_grupo=[
            {'instancia_id': 22, 'grupo_id': 30, 'nota': None,
             'estado': 'aprobado', 'corrector_id': 2},
        ],
        docentes=[ANA],
    )

    resultado = metricas(1)

    instancia = resultado['instancias'][0]
    assert instancia['rendidos'] == 1
    assert instancia['pendientes'] == 1
    assert instancia['promedio'] is None
    assert instancia['estados'] == {'aprobado': 1}
    assert instancia['por_corrector'] == [
        {'docente': ANA, 'cantidad': 1},
    ]

    assert resultado['equipos'] == {'total': 2, 'sin_equipo': 0}
    assert resultado['docentes'] == [{'docente': ANA, 'equipos': 2}]
    assert resultado['alumnos']['promocionados'] == 1


def test_metricas_promocionados_exige_todas_las_obligatorias(monkeypatch):
    """Aprobar una sola obligatoria no alcanza si hay otra sin nota."""
    _mock_db(
        monkeypatch,
        evaluaciones=[PARCIAL, TP],
        instancias=[INST_1],
        inscripciones=[{'estudiante_id': 4, 'estado': 'cursando'}],
        notas=[{'instancia_id': 20, 'estudiante_id': 4, 'nota': 9.0,
                'estado': None, 'corrector_id': 2}],
    )

    assert metricas(1)['alumnos']['promocionados'] == 0


def test_metricas_sin_obligatorias_no_promociona(monkeypatch):
    opcional = {**PARCIAL, 'tipo': 'opcional'}
    _mock_db(
        monkeypatch,
        evaluaciones=[opcional],
        instancias=[INST_1],
        inscripciones=[{'estudiante_id': 4, 'estado': 'cursando'}],
        notas=[{'instancia_id': 20, 'estudiante_id': 4, 'nota': 9.0,
                'estado': None, 'corrector_id': 2}],
    )

    assert metricas(1)['alumnos']['promocionados'] == 0


def test_metricas_sin_equipo_sin_evaluacion_abierta(monkeypatch):
    cerrada = {**TP, 'permite_crear_grupos': False}
    _mock_db(
        monkeypatch,
        evaluaciones=[cerrada],
        inscripciones=_inscripciones(),
        grupos=[{'id': 30, 'evaluacion_id': 11, 'nombre': 'Halcones',
                 'tutor_id': None}],
    )

    assert metricas(1)['equipos'] == {'total': 1, 'sin_equipo': None}


def test_ruta_metricas(client, permitir_todo, monkeypatch):
    _mock_db(monkeypatch, inscripciones=_inscripciones())

    respuesta = client.get('/gradebook_api/cursadas/1/metricas', headers=_auth())

    assert respuesta.status_code == 200
    assert respuesta.get_json()['alumnos']['total'] == 4


def test_ruta_metricas_sin_permiso(client, monkeypatch):
    monkeypatch.setattr(auth_service, 'tiene_permiso', lambda payload, codigo: False)

    respuesta = client.get('/gradebook_api/cursadas/1/metricas', headers=_auth())

    assert respuesta.status_code == 403


def test_ruta_metricas_cursada_inexistente(client, permitir_todo, monkeypatch):
    monkeypatch.setattr(db, 'obtener_cursada_por_id', lambda cursada_id: None)

    respuesta = client.get('/gradebook_api/cursadas/99/metricas', headers=_auth())

    assert respuesta.status_code == 404
    assert respuesta.get_json()['errors'][0]['code'] == 'cursada.not.found'
