"""Tests end-to-end de las rutas con test_client; db mockeado y JWT real."""
import pytest

import app as app_module
from gradebook_api import db, cache
from gradebook_api.services import auth as auth_service
from gradebook_api.utils import generar_token, hashear_password


@pytest.fixture
def client():
    app_module.app.config['TESTING'] = True
    return app_module.app.test_client()


@pytest.fixture(autouse=True)
def _cache_desactivado(monkeypatch):
    """Neutraliza el cache en todos los tests (evita depender de Redis)."""
    monkeypatch.setattr(cache, 'obtener', lambda clave: None)
    monkeypatch.setattr(cache, 'guardar', lambda clave, valor, ttl: None)
    monkeypatch.setattr(cache, 'invalidar', lambda *claves: None)


@pytest.fixture
def permitir_todo(monkeypatch):
    """Hace que el chequeo de permisos pase siempre (para probar la lógica de la ruta)."""
    monkeypatch.setattr(auth_service, 'tiene_permiso', lambda payload, codigo: True)


def _auth(tipo='docente', rol='super_admin'):
    return {'Authorization': f'Bearer {generar_token(1, tipo, rol, "p@fi.uba.ar")}'}


# --- login / me ---

def test_login_ok(client, monkeypatch):
    docente = {'id': 1, 'email': 'p@fi.uba.ar', 'rol': 'Profesor', 'activo': True,
               'password_hash': hashear_password('secreto')}
    monkeypatch.setattr(db, 'obtener_docente_por_email', lambda email: docente)

    respuesta = client.post('/gradebook_api/login', json={'email': 'p@fi.uba.ar', 'password': 'secreto'})

    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert cuerpo['token'] and cuerpo['usuario']['rol'] == 'super_admin'


def test_login_credenciales_invalidas_401(client, monkeypatch):
    monkeypatch.setattr(db, 'obtener_docente_por_email', lambda email: {})
    monkeypatch.setattr(db, 'obtener_estudiante_por_email', lambda email: {})

    respuesta = client.post('/gradebook_api/login', json={'email': 'x@fi.uba.ar', 'password': 'mal'})

    assert respuesta.status_code == 401
    assert respuesta.get_json()['errors'][0]['code'] == 'invalid.credentials'


def test_me_con_token(client, monkeypatch):
    monkeypatch.setattr(auth_service, 'permisos_efectivos_de_payload', lambda payload: ['docentes.leer'])

    respuesta = client.get('/gradebook_api/me', headers=_auth())

    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert cuerpo['email'] == 'p@fi.uba.ar' and cuerpo['permisos'] == ['docentes.leer']


# --- autorización (sin token / sin permiso) ---

def test_sin_token_401(client):
    respuesta = client.get('/gradebook_api/docentes')

    assert respuesta.status_code == 401


def test_sin_permiso_403(client, monkeypatch):
    monkeypatch.setattr(auth_service, 'tiene_permiso', lambda payload, codigo: False)

    respuesta = client.get('/gradebook_api/docentes', headers=_auth(tipo='estudiante', rol='usuario'))

    assert respuesta.status_code == 403
    assert respuesta.get_json()['errors'][0]['code'] == 'auth.forbidden'


def test_get_docentes_con_permiso_ok(client, permitir_todo, monkeypatch):
    monkeypatch.setattr(db, 'obtener_todos_los_docentes', lambda: [
        {'id': 1, 'nombre': 'Bruno', 'apellido': 'L', 'email': 'b@fi.uba.ar', 'rol': 'Profesor',
         'foto': None, 'activo': True, 'created_at': None, 'updated_at': None},
    ])

    respuesta = client.get('/gradebook_api/docentes', headers=_auth())

    assert respuesta.status_code == 200
    assert respuesta.get_json()[0]['email'] == 'b@fi.uba.ar'


# --- docentes ---

def test_post_docente_ok(client, permitir_todo, monkeypatch):
    monkeypatch.setattr(db, 'obtener_docente_por_email', lambda email: {})
    monkeypatch.setattr(db, 'insertar_docente', lambda *args: 3)
    monkeypatch.setattr(db, 'obtener_docente_por_id',
                        lambda docente_id: {'id': docente_id, 'nombre': 'Ada', 'apellido': 'L',
                                            'email': 'ada@fi.uba.ar', 'rol': 'Ayudante', 'foto': None,
                                            'activo': True, 'created_at': None, 'updated_at': None})

    respuesta = client.post('/gradebook_api/docentes', headers=_auth(),
                            json={'nombre': 'Ada', 'apellido': 'L', 'email': 'ada@fi.uba.ar',
                                  'rol': 'Ayudante', 'password': 'x'})

    assert respuesta.status_code == 201
    assert respuesta.get_json()['id'] == 3


# --- estudiantes ---

def test_post_estudiante_ok(client, permitir_todo, monkeypatch):
    monkeypatch.setattr(db, 'obtener_estudiante_por_padron', lambda padron: {})
    monkeypatch.setattr(db, 'obtener_estudiante_por_email', lambda email: {})
    monkeypatch.setattr(db, 'insertar_estudiante', lambda *args: 4)
    monkeypatch.setattr(db, 'obtener_estudiante_por_id',
                        lambda estudiante_id: {'id': estudiante_id, 'padron': '116530', 'nombre': 'Ian',
                                               'apellido': 'Acosta', 'email': 'ian@fi.uba.ar',
                                               'activo': True, 'created_at': None, 'updated_at': None})

    respuesta = client.post('/gradebook_api/estudiantes', headers=_auth(),
                            json={'padron': '116530', 'nombre': 'Ian', 'apellido': 'Acosta',
                                  'email': 'ian@fi.uba.ar', 'password': '116530'})

    assert respuesta.status_code == 201
    assert respuesta.get_json()['padron'] == '116530'


def test_post_estudiantes_csv_ok(client, permitir_todo, monkeypatch):
    import io
    monkeypatch.setattr(db, 'obtener_todos_los_estudiantes', lambda: [])
    monkeypatch.setattr(db, 'insertar_estudiantes_bulk', lambda filas: filas)

    csv_bytes = (
        ';Legajo;Alumno;Estado;Instancias;Email;Telefono\n'
        '1;222;PEREZ, ANA;Pendiente;Regularidad;Email Principal: ana@fi.uba.ar;-\n'
    ).encode('utf-8')

    respuesta = client.post(
        '/gradebook_api/estudiantes/csv',
        headers=_auth(),
        data={'archivo': (io.BytesIO(csv_bytes), 'padron.csv')},
        content_type='multipart/form-data',
    )

    assert respuesta.status_code == 201
    assert respuesta.get_json()['creados'] == 1


def test_post_estudiantes_csv_sin_archivo(client, permitir_todo):
    respuesta = client.post('/gradebook_api/estudiantes/csv', headers=_auth())

    assert respuesta.status_code == 400
    assert respuesta.get_json()['errors'][0]['code'] == 'file.missing'


# --- roles ---

def test_get_roles_ok(client, permitir_todo, monkeypatch):
    monkeypatch.setattr(db, 'obtener_todos_los_roles',
                        lambda: [{'id': 1, 'codigo': 'admin', 'nombre': 'Admin', 'descripcion': 'x'}])
    monkeypatch.setattr(db, 'obtener_codigos_permisos_de_rol', lambda rol_id: ['docentes.leer'])

    respuesta = client.get('/gradebook_api/roles', headers=_auth())

    assert respuesta.status_code == 200
    assert respuesta.get_json()[0]['permisos'] == ['docentes.leer']


# --- API key y rate limiting (before_request) ---

def test_api_key_faltante_401(client, monkeypatch):
    monkeypatch.setattr(app_module, 'API_KEY', 'secreto')

    respuesta = client.get('/gradebook_api/docentes')

    assert respuesta.status_code == 401
    assert respuesta.get_json()['errors'][0]['code'] == 'api.key.invalid'


def test_rate_limit_excedido_429(client, monkeypatch):
    monkeypatch.setattr(app_module, 'esta_permitido', lambda identificador: False)

    respuesta = client.get('/gradebook_api/docentes')

    assert respuesta.status_code == 429
    assert respuesta.get_json()['errors'][0]['code'] == 'rate.limit.exceeded'
