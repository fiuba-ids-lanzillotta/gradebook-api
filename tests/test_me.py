"""Tests de GET /me/asistencias y GET /me/companeros (alumno autenticado)."""
import pytest

import app as app_module
from gradebook_api import db, cache
from gradebook_api.services import auth as auth_service
from gradebook_api.services.asistencias import mis_asistencias
from gradebook_api.services.estudiantes import mis_companeros
from gradebook_api.utils import generar_token


CURSADA = {'id': 3, 'anio': 2026, 'cuatrimestre': 2,
           'fecha_inicio': '2026-01-01', 'fecha_fin': '2026-12-31'}


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


def _auth(tipo='estudiante'):
    return {'Authorization': f'Bearer {generar_token(4, tipo, "usuario", "a@fi.uba.ar")}'}


def _mock_cursada_alumno(monkeypatch):
    """El alumno 4 cursa la cursada 3 (vigente)."""
    monkeypatch.setattr(db, 'inscripciones_cursando_de',
                        lambda estudiante_id: [{'cursada_id': 3}])
    monkeypatch.setattr(db, 'obtener_cursada_por_id',
                        lambda cursada_id: dict(CURSADA))


# --- mis_asistencias ---

def test_mis_asistencias_con_resumen(monkeypatch):
    _mock_cursada_alumno(monkeypatch)
    monkeypatch.setattr(db, 'asistencias_de_estudiante', lambda estudiante_id: [
        {'estado': 'presente', 'metodo': 'qr', 'marcado_at': 't1',
         'clase': {'id': 11, 'cursada_id': 3, 'fecha': '2026-10-01', 'titulo': 'Clase 1', 'estado': 'cerrada'}},
        {'estado': 'ausente', 'metodo': None, 'marcado_at': None,
         'clase': {'id': 12, 'cursada_id': 3, 'fecha': '2026-10-08', 'titulo': 'Clase 2', 'estado': 'cerrada'}},
        {'estado': 'presente', 'metodo': 'manual', 'marcado_at': 't2',
         'clase': {'id': 99, 'cursada_id': 8, 'fecha': '2025-01-01', 'titulo': 'Otra', 'estado': 'cerrada'}},
    ])

    resultado = mis_asistencias(4)

    # La clase de otra cursada se descarta; ordenadas por fecha
    assert len(resultado['asistencias']) == 2
    assert resultado['asistencias'][0]['clase']['titulo'] == 'Clase 1'
    assert resultado['asistencias'][0]['estado'] == 'presente'
    assert resultado['resumen'] == {'pendiente': 0, 'presente': 1, 'ausente': 1}


def test_mis_asistencias_sin_cursada_404(monkeypatch):
    monkeypatch.setattr(db, 'inscripciones_cursando_de', lambda estudiante_id: [])

    with pytest.raises(ValueError) as error:
        mis_asistencias(4)

    assert error.value.args[1] == 404


def test_get_me_asistencias_200(client, monkeypatch):
    _mock_cursada_alumno(monkeypatch)
    monkeypatch.setattr(db, 'asistencias_de_estudiante', lambda estudiante_id: [
        {'estado': 'presente', 'metodo': 'qr', 'marcado_at': 't1',
         'clase': {'id': 11, 'cursada_id': 3, 'fecha': '2026-10-01', 'titulo': 'Clase 1', 'estado': 'cerrada'}},
    ])

    respuesta = client.get('/gradebook_api/me/asistencias', headers=_auth())

    assert respuesta.status_code == 200
    datos = respuesta.get_json()
    assert datos['asistencias'][0]['clase']['titulo'] == 'Clase 1'
    assert datos['resumen']['presente'] == 1


def test_get_me_asistencias_docente_403(client):
    respuesta = client.get('/gradebook_api/me/asistencias',
                           headers=_auth(tipo='docente'))

    assert respuesta.status_code == 403


# --- mis_companeros ---

def test_mis_companeros_con_equipo(monkeypatch):
    _mock_cursada_alumno(monkeypatch)
    monkeypatch.setattr(db, 'inscriptos_cursando', lambda cursada_id: [
        {'estudiante_id': 4, 'estudiantes': {'id': 4, 'nombre': 'Luz', 'apellido': 'Perez', 'padron': '111'}},
        {'estudiante_id': 5, 'estudiantes': {'id': 5, 'nombre': 'Ana', 'apellido': 'Abad', 'padron': '222'}},
        {'estudiante_id': 6, 'estudiantes': {'id': 6, 'nombre': 'Nico', 'apellido': 'Sosa', 'padron': '333'}},
    ])
    monkeypatch.setattr(db, 'buscar_evaluacion_con_creacion_grupos',
                        lambda cursada_id: {'id': 11, 'nombre': 'TP Backend'})
    monkeypatch.setattr(db, 'listar_grupos_de_evaluaciones',
                        lambda ids: [{'id': 9, 'evaluacion_id': 11, 'nombre': 'Halcones'}])
    monkeypatch.setattr(db, 'miembros_de_grupos',
                        lambda ids: [{'grupo_id': 9, 'estudiante_id': 5}])

    resultado = mis_companeros(4)

    # No se incluye a sí mismo; orden alfabético por apellido
    assert [c['padron'] for c in resultado['companeros']] == ['222', '333']
    assert resultado['companeros'][0]['equipo'] == {'id': 9, 'nombre': 'Halcones'}
    assert resultado['companeros'][1]['equipo'] is None


def test_mis_companeros_sin_evaluacion_abierta(monkeypatch):
    _mock_cursada_alumno(monkeypatch)
    monkeypatch.setattr(db, 'inscriptos_cursando', lambda cursada_id: [
        {'estudiante_id': 5, 'estudiantes': {'id': 5, 'nombre': 'Ana', 'apellido': 'Abad', 'padron': '222'}},
    ])
    monkeypatch.setattr(db, 'buscar_evaluacion_con_creacion_grupos', lambda cursada_id: {})

    resultado = mis_companeros(4)

    assert resultado['companeros'][0]['equipo'] is None


def test_mis_companeros_sin_cursada_404(monkeypatch):
    monkeypatch.setattr(db, 'inscripciones_cursando_de', lambda estudiante_id: [])

    with pytest.raises(ValueError) as error:
        mis_companeros(4)

    assert error.value.args[1] == 404


def test_get_me_companeros_200(client, monkeypatch):
    _mock_cursada_alumno(monkeypatch)
    monkeypatch.setattr(db, 'inscriptos_cursando', lambda cursada_id: [
        {'estudiante_id': 5, 'estudiantes': {'id': 5, 'nombre': 'Ana', 'apellido': 'Abad', 'padron': '222'}},
    ])
    monkeypatch.setattr(db, 'buscar_evaluacion_con_creacion_grupos', lambda cursada_id: {})

    respuesta = client.get('/gradebook_api/me/companeros', headers=_auth())

    assert respuesta.status_code == 200
    assert respuesta.get_json()['companeros'][0]['padron'] == '222'


def test_get_me_companeros_docente_403(client):
    respuesta = client.get('/gradebook_api/me/companeros',
                           headers=_auth(tipo='docente'))

    assert respuesta.status_code == 403
