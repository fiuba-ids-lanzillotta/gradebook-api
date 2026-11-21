"""Tests del flag permite_crear_grupos (PUT /evaluaciones/{id}/crear-grupos)."""
import pytest

import app as app_module
from gradebook_api import db, cache, registro
from gradebook_api.services import evaluaciones as service
from gradebook_api.services import auth as auth_service
from gradebook_api.utils import generar_token

EVAL_GRUPAL = {'id': 7, 'cursada_id': 3, 'nombre': 'TP Bash', 'modalidad': 'grupal',
               'permite_crear_grupos': False}


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


# --- service ---

def test_evaluacion_inexistente_404(monkeypatch):
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: {})

    with pytest.raises(ValueError) as error:
        service.habilitar_crear_grupos(9, True)

    assert error.value.args[1] == 404
    assert error.value.args[0]['errors'][0]['code'] == 'evaluacion.not.found'


def test_habilitado_invalido_400(monkeypatch):
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: EVAL_GRUPAL)

    with pytest.raises(ValueError) as error:
        service.habilitar_crear_grupos(7, 'si')

    assert error.value.args[0]['errors'][0]['code'] == 'invalid.bool'


def test_evaluacion_no_grupal_400(monkeypatch):
    monkeypatch.setattr(db, 'obtener_evaluacion',
                        lambda evaluacion_id: {**EVAL_GRUPAL, 'modalidad': 'individual'})

    with pytest.raises(ValueError) as error:
        service.habilitar_crear_grupos(7, True)

    assert error.value.args[1] == 400
    assert error.value.args[0]['errors'][0]['code'] == 'evaluacion.no.grupal'


def test_habilitar_con_otra_activa_409(monkeypatch):
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: EVAL_GRUPAL)
    monkeypatch.setattr(db, 'buscar_evaluacion_con_creacion_grupos',
                        lambda cursada_id: {**EVAL_GRUPAL, 'id': 8, 'nombre': 'TP Redes',
                                            'permite_crear_grupos': True})

    with pytest.raises(ValueError) as error:
        service.habilitar_crear_grupos(7, True)

    assert error.value.args[1] == 409
    assert error.value.args[0]['errors'][0]['code'] == 'grupos.creacion.ocupada'


def test_habilitar_misma_evaluacion_ya_activa_ok(monkeypatch, espiar_registro):
    """Re-habilitar la misma evaluación no es conflicto (idempotente)."""
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: EVAL_GRUPAL)
    monkeypatch.setattr(db, 'buscar_evaluacion_con_creacion_grupos', lambda cursada_id: EVAL_GRUPAL)
    monkeypatch.setattr(db, 'actualizar_evaluacion',
                        lambda eid, datos: {**EVAL_GRUPAL, **datos})

    resultado = service.habilitar_crear_grupos(7, True)

    assert resultado['permite_crear_grupos'] is True


def test_habilitar_ok_y_audita(monkeypatch, espiar_registro):
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: EVAL_GRUPAL)
    monkeypatch.setattr(db, 'buscar_evaluacion_con_creacion_grupos', lambda cursada_id: {})
    capturado = {}
    monkeypatch.setattr(db, 'actualizar_evaluacion',
                        lambda eid, datos: capturado.update(datos) or {**EVAL_GRUPAL, **datos})

    resultado = service.habilitar_crear_grupos(7, True)

    assert capturado == {'permite_crear_grupos': True}
    assert resultado['permite_crear_grupos'] is True
    args, kwargs = espiar_registro[0]
    assert args[0] == 'evaluaciones.grupos'
    assert 'Habilitó' in args[1]
    assert kwargs['cursada_id'] == 3


def test_deshabilitar_ok_y_audita(monkeypatch, espiar_registro):
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: EVAL_GRUPAL)
    monkeypatch.setattr(db, 'actualizar_evaluacion',
                        lambda eid, datos: {**EVAL_GRUPAL, **datos})

    resultado = service.habilitar_crear_grupos(7, False)

    assert resultado['permite_crear_grupos'] is False
    assert 'Deshabilitó' in espiar_registro[0][0][1]


# --- ruta ---

def test_put_crear_grupos_200(client, monkeypatch, permitir_todo):
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: EVAL_GRUPAL)
    monkeypatch.setattr(db, 'buscar_evaluacion_con_creacion_grupos', lambda cursada_id: {})
    monkeypatch.setattr(db, 'actualizar_evaluacion',
                        lambda eid, datos: {**EVAL_GRUPAL, **datos})

    respuesta = client.put('/gradebook_api/evaluaciones/7/crear-grupos',
                           json={'habilitado': True}, headers=_auth())

    assert respuesta.status_code == 200
    assert respuesta.get_json()['permite_crear_grupos'] is True


def test_put_crear_grupos_409(client, monkeypatch, permitir_todo):
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: EVAL_GRUPAL)
    monkeypatch.setattr(db, 'buscar_evaluacion_con_creacion_grupos',
                        lambda cursada_id: {**EVAL_GRUPAL, 'id': 8})

    respuesta = client.put('/gradebook_api/evaluaciones/7/crear-grupos',
                           json={'habilitado': True}, headers=_auth())

    assert respuesta.status_code == 409
    assert respuesta.get_json()['errors'][0]['code'] == 'grupos.creacion.ocupada'


def test_put_crear_grupos_403_sin_permiso(client, monkeypatch):
    monkeypatch.setattr(auth_service, 'tiene_permiso', lambda payload, codigo: False)

    respuesta = client.put('/gradebook_api/evaluaciones/7/crear-grupos',
                           json={'habilitado': True}, headers=_auth())

    assert respuesta.status_code == 403


def test_put_crear_grupos_400_body_invalido(client, monkeypatch, permitir_todo):
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: EVAL_GRUPAL)

    respuesta = client.put('/gradebook_api/evaluaciones/7/crear-grupos',
                           json={}, headers=_auth())

    assert respuesta.status_code == 400
    assert respuesta.get_json()['errors'][0]['code'] == 'invalid.bool'
