"""Tests de instancias de evaluación (evaluacion_instancias + sus endpoints)."""
import pytest

import app as app_module
from gradebook_api import db, cache, registro
from gradebook_api.services import instancias as service
from gradebook_api.services import auth as auth_service
from gradebook_api.utils import generar_token

EVALUACION = {'id': 7, 'cursada_id': 3, 'nombre': 'Parcial', 'modalidad': 'individual'}
INSTANCIA = {'id': 21, 'evaluacion_id': 7, 'numero': 1, 'nombre': '1er parcial',
             'fecha': '2026-04-10', 'estado': 'abierta',
             'created_at': '2026-03-01T10:00:00+00:00', 'updated_at': None}


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
    monkeypatch.setattr(registro, 'registrar', lambda *args, **kwargs: llamadas.append((args, kwargs)) or True)
    return llamadas


def _auth(tipo='docente', rol='super_admin'):
    return {'Authorization': f'Bearer {generar_token(1, tipo, rol, "p@fi.uba.ar")}'}


# --- service: listar ---

def test_listar_evaluacion_inexistente_404(monkeypatch):
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: {})

    with pytest.raises(ValueError) as error:
        service.listar(9)

    assert error.value.args[1] == 404
    assert error.value.args[0]['errors'][0]['code'] == 'evaluacion.not.found'


def test_listar_retorna_dtos_ordenados(monkeypatch):
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: EVALUACION)
    otra = {**INSTANCIA, 'id': 22, 'numero': 2, 'nombre': 'Recuperatorio'}
    monkeypatch.setattr(db, 'buscar_instancias', lambda evaluacion_id: [INSTANCIA, otra])

    resultado = service.listar(7)

    assert [fila['numero'] for fila in resultado['instancias']] == [1, 2]
    assert resultado['instancias'][0]['evaluacion_nombre'] == 'Parcial'


# --- service: crear ---

def test_crear_sin_nombre_400(monkeypatch):
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: EVALUACION)

    with pytest.raises(ValueError) as error:
        service.crear(7, {'fecha': '2026-04-10'})

    assert error.value.args[0]['errors'][0]['code'] == 'required.nombre'


def test_crear_fecha_invalida_400(monkeypatch):
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: EVALUACION)

    with pytest.raises(ValueError) as error:
        service.crear(7, {'nombre': '1er parcial', 'fecha': '10/04/2026'})

    assert error.value.args[0]['errors'][0]['code'] == 'invalid.fecha.format'


def test_crear_asigna_numero_y_audita(monkeypatch, espiar_registro):
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: EVALUACION)
    monkeypatch.setattr(db, 'proximo_numero_instancia', lambda evaluacion_id: 2)
    capturado = {}
    monkeypatch.setattr(db, 'insertar_instancia',
                        lambda eid, numero, nombre, fecha:
                        capturado.update({'eid': eid, 'numero': numero, 'nombre': nombre, 'fecha': fecha})
                        or {**INSTANCIA, 'numero': numero, 'nombre': nombre, 'fecha': fecha})

    resultado = service.crear(7, {'nombre': 'Recuperatorio 1', 'fecha': '2026-05-20'})

    assert capturado == {'eid': 7, 'numero': 2, 'nombre': 'Recuperatorio 1', 'fecha': '2026-05-20'}
    assert resultado['numero'] == 2 and resultado['estado'] == 'abierta'
    args, kwargs = espiar_registro[0]
    assert args[0] == 'instancias.crear'
    assert kwargs['cursada_id'] == 3
    assert kwargs['detalle']['instancia_id'] == 21


# --- service: actualizar ---

def test_actualizar_instancia_inexistente_404(monkeypatch):
    monkeypatch.setattr(db, 'obtener_instancia', lambda instancia_id: {})

    with pytest.raises(ValueError) as error:
        service.actualizar(9, {'nombre': 'x'})

    assert error.value.args[1] == 404
    assert error.value.args[0]['errors'][0]['code'] == 'instancia.not.found'


def test_actualizar_body_vacio_400(monkeypatch):
    monkeypatch.setattr(db, 'obtener_instancia', lambda instancia_id: INSTANCIA)

    with pytest.raises(ValueError) as error:
        service.actualizar(21, {})

    assert error.value.args[0]['errors'][0]['code'] == 'invalid.body'


def test_actualizar_estado_invalido_400(monkeypatch):
    monkeypatch.setattr(db, 'obtener_instancia', lambda instancia_id: INSTANCIA)

    with pytest.raises(ValueError) as error:
        service.actualizar(21, {'estado': 'suspendida'})

    assert error.value.args[0]['errors'][0]['code'] == 'invalid.estado.instancia'


def test_actualizar_renombrar_audita_edicion(monkeypatch, espiar_registro):
    monkeypatch.setattr(db, 'obtener_instancia', lambda instancia_id: INSTANCIA)
    capturado = {}
    monkeypatch.setattr(db, 'actualizar_instancia',
                        lambda iid, datos: capturado.update(datos) or {**INSTANCIA, **datos})
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: EVALUACION)

    resultado = service.actualizar(21, {'nombre': '1er parcial (reprogramado)', 'fecha': '2026-04-17'})

    assert capturado['nombre'] == '1er parcial (reprogramado)'
    assert capturado['fecha'] == '2026-04-17'
    assert resultado['nombre'] == '1er parcial (reprogramado)'
    assert espiar_registro[0][0][0] == 'instancias.editar'


def test_actualizar_cerrar_audita_cierre(monkeypatch, espiar_registro):
    monkeypatch.setattr(db, 'obtener_instancia', lambda instancia_id: INSTANCIA)
    monkeypatch.setattr(db, 'actualizar_instancia',
                        lambda iid, datos: {**INSTANCIA, **datos})
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: EVALUACION)

    resultado = service.actualizar(21, {'estado': 'cerrada'})

    assert resultado['estado'] == 'cerrada'
    assert espiar_registro[0][0][0] == 'instancias.cerrar'


def test_actualizar_ya_cerrada_audita_edicion(monkeypatch, espiar_registro):
    monkeypatch.setattr(db, 'obtener_instancia', lambda instancia_id: {**INSTANCIA, 'estado': 'cerrada'})
    monkeypatch.setattr(db, 'actualizar_instancia', lambda iid, datos: {**INSTANCIA, **datos})
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: EVALUACION)

    service.actualizar(21, {'fecha': None})

    assert espiar_registro[0][0][0] == 'instancias.editar'


# --- rutas ---

def test_get_instancias_200(client, monkeypatch, permitir_todo):
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: EVALUACION)
    monkeypatch.setattr(db, 'buscar_instancias', lambda evaluacion_id: [INSTANCIA])

    respuesta = client.get('/gradebook_api/evaluaciones/7/instancias', headers=_auth())

    assert respuesta.status_code == 200
    assert respuesta.get_json()['instancias'][0]['nombre'] == '1er parcial'


def test_get_instancias_404(client, monkeypatch, permitir_todo):
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: {})

    respuesta = client.get('/gradebook_api/evaluaciones/99/instancias', headers=_auth())

    assert respuesta.status_code == 404
    assert respuesta.get_json()['errors'][0]['code'] == 'evaluacion.not.found'


def test_get_instancias_403_sin_permiso(client, monkeypatch):
    monkeypatch.setattr(auth_service, 'tiene_permiso', lambda payload, codigo: False)

    respuesta = client.get('/gradebook_api/evaluaciones/7/instancias', headers=_auth())

    assert respuesta.status_code == 403


def test_post_instancia_201(client, monkeypatch, permitir_todo):
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: EVALUACION)
    monkeypatch.setattr(db, 'proximo_numero_instancia', lambda evaluacion_id: 1)
    monkeypatch.setattr(db, 'insertar_instancia',
                        lambda eid, numero, nombre, fecha:
                        {**INSTANCIA, 'numero': numero, 'nombre': nombre, 'fecha': fecha})

    respuesta = client.post('/gradebook_api/evaluaciones/7/instancias',
                            json={'nombre': 'Entrega', 'fecha': '2026-06-01'}, headers=_auth())

    assert respuesta.status_code == 201
    assert respuesta.get_json()['numero'] == 1


def test_post_instancia_400_body_invalido(client, monkeypatch, permitir_todo):
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: EVALUACION)

    respuesta = client.post('/gradebook_api/evaluaciones/7/instancias', json={}, headers=_auth())

    assert respuesta.status_code == 400


def test_put_instancia_200(client, monkeypatch, permitir_todo):
    monkeypatch.setattr(db, 'obtener_instancia', lambda instancia_id: INSTANCIA)
    monkeypatch.setattr(db, 'actualizar_instancia', lambda iid, datos: {**INSTANCIA, **datos})
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: EVALUACION)

    respuesta = client.put('/gradebook_api/instancias/21',
                           json={'estado': 'cerrada'}, headers=_auth())

    assert respuesta.status_code == 200
    assert respuesta.get_json()['estado'] == 'cerrada'


def test_put_instancia_404(client, monkeypatch, permitir_todo):
    monkeypatch.setattr(db, 'obtener_instancia', lambda instancia_id: {})

    respuesta = client.put('/gradebook_api/instancias/99',
                           json={'nombre': 'x'}, headers=_auth())

    assert respuesta.status_code == 404
    assert respuesta.get_json()['errors'][0]['code'] == 'instancia.not.found'
