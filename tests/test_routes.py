"""Tests end-to-end de las rutas con test_client; db mockeado y JWT real."""
import pytest

import app as app_module
from gradebook_api import db, cache
from gradebook_api.utils import generar_token


@pytest.fixture
def client():
    app_module.app.config['TESTING'] = True
    return app_module.app.test_client()


@pytest.fixture(autouse=True)
def _cache_desactivado(monkeypatch):
    """Neutraliza el cache en todos los tests de rutas (evita depender de Redis)."""
    monkeypatch.setattr(cache, 'obtener', lambda clave: None)
    monkeypatch.setattr(cache, 'guardar', lambda clave, valor, ttl: None)
    monkeypatch.setattr(cache, 'invalidar', lambda *claves: None)


def _auth(rol='admin'):
    return {'Authorization': f'Bearer {generar_token("admin", rol)}'}


# --- GET /items (público) ---

def test_get_items(client, monkeypatch):
    monkeypatch.setattr(db, 'obtener_todos_los_items', lambda: [
        {'id': 1, 'nombre': 'A', 'descripcion': None, 'activo': True},
    ])

    respuesta = client.get('/gradebook_api/items')
    datos = respuesta.get_json()

    assert respuesta.status_code == 200
    assert datos == [{'id': 1, 'nombre': 'A', 'descripcion': None, 'activo': True}]
    assert respuesta.headers.get('Cache-Control') == 'no-store'


def test_get_item_404(client, monkeypatch):
    monkeypatch.setattr(db, 'obtener_item_por_id', lambda item_id: {})

    respuesta = client.get('/gradebook_api/items/999')

    assert respuesta.status_code == 404
    assert respuesta.get_json()['errors'][0]['code'] == 'item.not.found'


# --- POST /items (auth admin) ---

def test_post_item_sin_token(client):
    respuesta = client.post('/gradebook_api/items', json={'nombre': 'X'})

    assert respuesta.status_code == 401


def test_post_item_rol_insuficiente(client):
    respuesta = client.post('/gradebook_api/items', json={'nombre': 'X'}, headers=_auth(rol='otro'))

    assert respuesta.status_code == 403


def test_post_item_ok(client, monkeypatch):
    monkeypatch.setattr(db, 'obtener_item_por_nombre', lambda nombre: {})
    monkeypatch.setattr(db, 'insertar_item', lambda *args: 5)
    monkeypatch.setattr(db, 'obtener_item_por_id',
                        lambda item_id: {'id': item_id, 'nombre': 'X', 'descripcion': None, 'activo': True})

    respuesta = client.post('/gradebook_api/items', json={'nombre': 'X'}, headers=_auth())

    assert respuesta.status_code == 201
    assert respuesta.get_json()['id'] == 5


def test_post_item_nombre_duplicado_409(client, monkeypatch):
    monkeypatch.setattr(db, 'obtener_item_por_nombre', lambda nombre: {'id': 2, 'nombre': nombre})

    respuesta = client.post('/gradebook_api/items', json={'nombre': 'X'}, headers=_auth())

    assert respuesta.status_code == 409
    assert respuesta.get_json()['errors'][0]['code'] == 'nombre.duplicated'


def test_post_item_body_invalido_400(client):
    respuesta = client.post('/gradebook_api/items', json={}, headers=_auth())

    assert respuesta.status_code == 400
    assert respuesta.get_json()['errors'][0]['code'] == 'required.nombre'


# --- DELETE /items/<id> ---

def test_delete_item_ok(client, monkeypatch):
    monkeypatch.setattr(db, 'obtener_item_por_id',
                        lambda item_id: {'id': item_id, 'nombre': 'X', 'descripcion': None, 'activo': True})
    monkeypatch.setattr(db, 'eliminar_item', lambda item_id: 1)

    respuesta = client.delete('/gradebook_api/items/1', headers=_auth())

    assert respuesta.status_code == 204


# --- auth (login / me) ---

def test_login_credenciales_invalidas_401(client):
    respuesta = client.post('/gradebook_api/login', json={'usuario': 'admin', 'password': 'mal'})

    assert respuesta.status_code == 401
    assert respuesta.get_json()['errors'][0]['code'] == 'invalid.credentials'


def test_me_con_token(client):
    respuesta = client.get('/gradebook_api/me', headers=_auth())

    assert respuesta.status_code == 200
    assert respuesta.get_json() == {'usuario': 'admin', 'rol': 'admin'}


# --- API key (restringe el consumo al frontend) ---

def test_api_key_faltante_401(client, monkeypatch):
    monkeypatch.setattr(app_module, 'API_KEY', 'secreto')
    monkeypatch.setattr(db, 'obtener_todos_los_items', lambda: [])

    respuesta = client.get('/gradebook_api/items')

    assert respuesta.status_code == 401
    assert respuesta.get_json()['errors'][0]['code'] == 'api.key.invalid'


def test_api_key_valida_pasa(client, monkeypatch):
    monkeypatch.setattr(app_module, 'API_KEY', 'secreto')
    monkeypatch.setattr(db, 'obtener_todos_los_items', lambda: [])

    respuesta = client.get('/gradebook_api/items', headers={'X-API-Key': 'secreto'})

    assert respuesta.status_code == 200


# --- rate limiting ---

def test_rate_limit_excedido_429(client, monkeypatch):
    monkeypatch.setattr(app_module, 'esta_permitido', lambda identificador: False)

    respuesta = client.get('/gradebook_api/items')

    assert respuesta.status_code == 429
    assert respuesta.get_json()['errors'][0]['code'] == 'rate.limit.exceeded'
