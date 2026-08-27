"""Tests end-to-end de las rutas con test_client; db mockeado y JWT real."""
import pytest

import app as app_module
from gradebook_api import db, cache, reset_tokens, mailer
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
    monkeypatch.setattr(db, 'obtener_overrides_docente', lambda docente_id: [])

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
    monkeypatch.setattr(db, 'obtener_overrides_docente', lambda docente_id: [])
    monkeypatch.setattr(mailer, 'enviar_email_nuevo_docente', lambda *args: None)
    monkeypatch.setattr(reset_tokens, 'guardar_token', lambda *a: True)
    monkeypatch.setattr(mailer, 'enviar_email_recuperacion', lambda dest, link, nombre='', apellido='': None)

    respuesta = client.post('/gradebook_api/docentes', headers=_auth(),
                            json={'nombre': 'Ada', 'apellido': 'L', 'email': 'ada@fi.uba.ar',
                                  'rol': 'Ayudante'})

    assert respuesta.status_code == 201
    assert respuesta.get_json()['id'] == 3


def test_delete_docente_borrado_logico(client, permitir_todo, monkeypatch):
    monkeypatch.setattr(db, 'obtener_docente_por_id',
                        lambda docente_id: {'id': docente_id, 'nombre': 'Ada', 'apellido': 'L',
                                            'email': 'ada@fi.uba.ar', 'rol': 'Ayudante', 'foto': None,
                                            'activo': True, 'created_at': None, 'updated_at': None})
    monkeypatch.setattr(db, 'desactivar_docente', lambda docente_id: 1)

    respuesta = client.delete('/gradebook_api/docentes/1', headers=_auth())

    assert respuesta.status_code == 204


# --- estudiantes ---

def test_post_estudiante_ok(client, permitir_todo, monkeypatch):
    monkeypatch.setattr(db, 'obtener_estudiante_por_padron', lambda padron: {})
    monkeypatch.setattr(db, 'obtener_estudiante_por_email', lambda email: {})
    monkeypatch.setattr(db, 'obtener_cursada_vigente', lambda fecha: {'id': 9})
    monkeypatch.setattr(db, 'insertar_estudiante', lambda *args: 4)
    monkeypatch.setattr(db, 'insertar_inscripcion', lambda *args: 1)
    monkeypatch.setattr(db, 'obtener_estudiante_por_id',
                        lambda estudiante_id: {'id': estudiante_id, 'padron': '116530', 'nombre': 'Ian',
                                               'apellido': 'Acosta', 'email': 'ian@fi.uba.ar',
                                               'activo': True, 'created_at': None, 'updated_at': None})

    respuesta = client.post('/gradebook_api/estudiantes', headers=_auth(),
                            json={'padron': '116530', 'nombre': 'Ian', 'apellido': 'Acosta',
                                  'email': 'ian@fi.uba.ar', 'password': '116530'})

    assert respuesta.status_code == 201
    assert respuesta.get_json()['padron'] == '116530'


def test_get_estudiantes_de_cursada(client, permitir_todo, monkeypatch):
    monkeypatch.setattr(db, 'buscar_inscripciones_de_cursada', lambda *a, **k: [
        {'recursa': False, 'estado': 'baja', 'motivo_baja': 'abandonó',
         'estudiantes': {'id': 2, 'padron': '200', 'nombre': 'Ian', 'apellido': 'Acosta',
                         'email': 'ian@fi.uba.ar'}},
    ])
    monkeypatch.setattr(db, 'buscar_bajas_de_estudiantes', lambda ids: [
        {'estudiante_id': 2, 'motivo_baja': 'abandonó', 'cursadas': {'anio': 2026, 'cuatrimestre': 2}},
    ])

    respuesta = client.get('/gradebook_api/estudiantes?anio=2026&cuatrimestre=2', headers=_auth())

    assert respuesta.status_code == 200
    datos = respuesta.get_json()
    assert datos['estudiantes'][0]['estado'] == 'baja'
    assert datos['estudiantes'][0]['motivos_baja'][0] == {'anio': 2026, 'cuatrimestre': 2, 'motivo': 'abandonó'}
    assert '_first' in datos['_links']


def test_get_estudiantes_paginado(client, permitir_todo, monkeypatch):
    filas = [
        {'recursa': False, 'estado': 'cursando', 'motivo_baja': None,
         'estudiantes': {'id': i, 'padron': str(i), 'nombre': f'N{i}', 'apellido': f'A{i}',
                         'email': f'a{i}@fi.uba.ar'}}
        for i in range(1, 6)
    ]
    monkeypatch.setattr(db, 'buscar_inscripciones_de_cursada', lambda *a, **k: filas)
    monkeypatch.setattr(db, 'buscar_bajas_de_estudiantes', lambda ids: [])

    respuesta = client.get('/gradebook_api/estudiantes?anio=2026&cuatrimestre=2&_offset=0&_limit=2',
                           headers=_auth())

    assert respuesta.status_code == 200
    datos = respuesta.get_json()
    assert len(datos['estudiantes']) == 2
    assert '_next' in datos['_links'] and '_last' in datos['_links']
    assert '_prev' not in datos['_links']


def test_get_estudiantes_busqueda_q(client, permitir_todo, monkeypatch):
    capturado = {}

    def fake(*args, **kwargs):
        capturado['args'] = args
        return [{'recursa': False, 'estado': 'cursando', 'motivo_baja': None,
                 'estudiantes': {'id': 1, 'padron': '100', 'nombre': 'Ana', 'apellido': 'Perez',
                                 'email': 'a@fi.uba.ar'}}]

    monkeypatch.setattr(db, 'buscar_inscripciones_de_cursada', fake)
    monkeypatch.setattr(db, 'buscar_bajas_de_estudiantes', lambda ids: [])

    respuesta = client.get('/gradebook_api/estudiantes?anio=2026&cuatrimestre=2&q=ana', headers=_auth())

    assert respuesta.status_code == 200
    assert capturado['args'][-1] == 'ana'   # q es el último posicional que pasa el service


def test_get_estudiantes_vacio_204(client, permitir_todo, monkeypatch):
    monkeypatch.setattr(db, 'buscar_inscripciones_de_cursada', lambda *a, **k: [])
    monkeypatch.setattr(db, 'buscar_bajas_de_estudiantes', lambda ids: [])

    respuesta = client.get('/gradebook_api/estudiantes?anio=2026&cuatrimestre=2', headers=_auth())

    assert respuesta.status_code == 204


def test_get_estudiantes_limit_invalido_400(client, permitir_todo):
    respuesta = client.get('/gradebook_api/estudiantes?anio=2026&cuatrimestre=2&_limit=0', headers=_auth())

    assert respuesta.status_code == 400


def test_get_estudiantes_sin_cursada_400(client, permitir_todo):
    respuesta = client.get('/gradebook_api/estudiantes', headers=_auth())

    assert respuesta.status_code == 400


def test_baja_estudiante(client, permitir_todo, monkeypatch):
    monkeypatch.setattr(db, 'obtener_cursada_vigente', lambda fecha: {'id': 9})
    monkeypatch.setattr(db, 'obtener_inscripcion', lambda cursada_id, est_id: {'id': 55})
    monkeypatch.setattr(db, 'actualizar_estado_inscripcion', lambda *args: 1)

    respuesta = client.post('/gradebook_api/estudiantes/7/baja', headers=_auth(),
                            json={'estado': 'baja', 'motivo': 'no cumplió la regularidad'})

    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert cuerpo['estado'] == 'baja' and cuerpo['motivo_baja'] == 'no cumplió la regularidad'


def test_baja_estudiante_sin_motivo_400(client, permitir_todo, monkeypatch):
    monkeypatch.setattr(db, 'obtener_cursada_vigente', lambda fecha: {'id': 9})

    respuesta = client.post('/gradebook_api/estudiantes/7/baja', headers=_auth(),
                            json={'estado': 'baja'})

    assert respuesta.status_code == 400
    assert respuesta.get_json()['errors'][0]['code'] == 'required.motivo'


def test_post_estudiantes_csv_ok(client, permitir_todo, monkeypatch):
    import io
    monkeypatch.setattr(db, 'obtener_cursada_vigente', lambda fecha: {'id': 9})
    monkeypatch.setattr(db, 'obtener_todos_los_estudiantes', lambda: [])
    monkeypatch.setattr(db, 'insertar_estudiantes_bulk',
                        lambda filas: [{'id': 6, 'padron': fila['padron']} for fila in filas])
    monkeypatch.setattr(db, 'obtener_inscripciones_de_estudiantes', lambda ids: [])
    monkeypatch.setattr(db, 'insertar_inscripciones_bulk', lambda filas: filas)

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
    cuerpo = respuesta.get_json()
    assert cuerpo['estudiantes_creados'] == 1 and cuerpo['inscriptos'] == 1


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

# --- password reset ---

def test_password_reset_solicitar(client, monkeypatch):
    monkeypatch.setattr(db, 'obtener_docente_por_email', lambda email: {'id': 1})
    monkeypatch.setattr(reset_tokens, 'guardar_token', lambda *a: True)
    monkeypatch.setattr(mailer, 'enviar_email_recuperacion', lambda dest, link, nombre='', apellido='': None)

    respuesta = client.post('/gradebook_api/password-reset/solicitar', json={'email': 'p@fi.uba.ar'})

    assert respuesta.status_code == 200
    assert 'mensaje' in respuesta.get_json()


def test_password_reset_confirmar_ok(client, monkeypatch):
    monkeypatch.setattr(reset_tokens, 'consumir_token', lambda token: {'tipo': 'docente', 'id': 1})
    monkeypatch.setattr(db, 'actualizar_password_docente', lambda pid, password_hash: 1)

    respuesta = client.post('/gradebook_api/password-reset/confirmar',
                            json={'token': 't', 'password': 'nuevaClave1'})

    assert respuesta.status_code == 200


def test_password_reset_confirmar_invalido(client, monkeypatch):
    monkeypatch.setattr(reset_tokens, 'consumir_token', lambda token: {})

    respuesta = client.post('/gradebook_api/password-reset/confirmar',
                            json={'token': 'x', 'password': 'y'})

    assert respuesta.status_code == 400
    assert respuesta.get_json()['errors'][0]['code'] == 'reset.token.invalido'

# --- cursadas ---

def test_get_cursadas_ok(client, permitir_todo, monkeypatch):
    monkeypatch.setattr(db, 'buscar_cursadas', lambda *a, **k: [
        {'id': 1, 'anio': 2026, 'cuatrimestre': 2, 'fecha_inicio': '2026-08-01', 'fecha_fin': '2026-12-15',
         'materias': {'codigo': 'TB022', 'nombre': 'Introducción al Desarrollo de Software'}},
    ])
    monkeypatch.setattr(cache, 'obtener', lambda clave: None)
    monkeypatch.setattr(cache, 'guardar', lambda clave, valor, ttl: None)

    respuesta = client.get('/gradebook_api/cursadas?anio=2026', headers=_auth())

    assert respuesta.status_code == 200
    datos = respuesta.get_json()
    assert datos['cursadas'][0]['codigo'] == 'TB022'
    assert '_first' in datos['_links']


def test_get_cursadas_vacio_204(client, permitir_todo, monkeypatch):
    monkeypatch.setattr(db, 'buscar_cursadas', lambda *a, **k: [])

    respuesta = client.get('/gradebook_api/cursadas', headers=_auth())

    assert respuesta.status_code == 204


def test_get_cursadas_cuatrimestre_invalido_400(client, permitir_todo):
    respuesta = client.get('/gradebook_api/cursadas?cuatrimestre=3', headers=_auth())

    assert respuesta.status_code == 400
    assert respuesta.get_json()['errors'][0]['code'] == 'invalid.cuatrimestre'


# --- asistencias ---

def test_post_clase_dispara_toma(client, permitir_todo, monkeypatch):
    monkeypatch.setattr(db, 'obtener_cursada_por_id',
                        lambda cid: {'id': 9, 'fecha_inicio': '2026-08-01', 'fecha_fin': '2026-12-15'})
    monkeypatch.setattr(db, 'obtener_clase_por_fecha', lambda cid, f: {})
    monkeypatch.setattr(db, 'insertar_clase',
                        lambda cid, f, t: {'id': 5, 'cursada_id': cid, 'fecha': f, 'titulo': t, 'estado': 'abierta'})
    monkeypatch.setattr(db, 'obtener_inscriptos_activos_de_cursada', lambda cid: [1, 2])
    monkeypatch.setattr(db, 'obtener_estudiante_ids_de_clase', lambda clase_id: [])
    monkeypatch.setattr(db, 'insertar_asistencias_bulk', lambda filas: filas)

    respuesta = client.post('/gradebook_api/cursadas/9/clases', headers=_auth(),
                            json={'fecha': '2026-09-01', 'titulo': 'Clase 1'})

    assert respuesta.status_code == 201
    datos = respuesta.get_json()
    assert datos['generados'] == 2 and datos['clase']['id'] == 5


def test_post_clase_fecha_fuera_400(client, permitir_todo, monkeypatch):
    monkeypatch.setattr(db, 'obtener_cursada_por_id',
                        lambda cid: {'id': 9, 'fecha_inicio': '2026-08-01', 'fecha_fin': '2026-12-15'})

    respuesta = client.post('/gradebook_api/cursadas/9/clases', headers=_auth(), json={'fecha': '2027-01-01'})

    assert respuesta.status_code == 400
    assert respuesta.get_json()['errors'][0]['code'] == 'clase.fecha.fuera.de.cursada'


def test_marcar_por_codigo_200(client, permitir_todo, monkeypatch):
    monkeypatch.setattr(db, 'obtener_clase_por_id', lambda cid: {'id': 5, 'estado': 'abierta'})
    monkeypatch.setattr(db, 'obtener_asistencia_por_codigo', lambda clase_id, codigo: {
        'id': 7, 'estudiantes': {'id': 3, 'padron': '116530', 'nombre': 'Ana', 'apellido': 'Perez'}})
    monkeypatch.setattr(db, 'marcar_asistencia', lambda *a: 1)

    respuesta = client.post('/gradebook_api/clases/5/marcar', headers=_auth(), json={'codigo': 'ABCD2345'})

    assert respuesta.status_code == 200
    datos = respuesta.get_json()
    assert datos['estado'] == 'presente' and datos['metodo'] == 'qr' and datos['padron'] == '116530'


def test_marcar_codigo_inexistente_404(client, permitir_todo, monkeypatch):
    monkeypatch.setattr(db, 'obtener_clase_por_id', lambda cid: {'id': 5, 'estado': 'abierta'})
    monkeypatch.setattr(db, 'obtener_asistencia_por_codigo', lambda clase_id, codigo: {})

    respuesta = client.post('/gradebook_api/clases/5/marcar', headers=_auth(), json={'codigo': 'NADA1234'})

    assert respuesta.status_code == 404
    assert respuesta.get_json()['errors'][0]['code'] == 'asistencia.not.found'


def test_get_envio_progreso(client, permitir_todo, monkeypatch):
    monkeypatch.setattr(db, 'obtener_clase_por_id', lambda cid: {'id': 5, 'estado': 'abierta'})
    monkeypatch.setattr(db, 'contar_asistencias',
                        lambda clase_id, estado=None, enviado=None, con_error=False, max_intentos=None:
                        2 if enviado is True else (0 if con_error else 5))

    respuesta = client.get('/gradebook_api/clases/5/envio', headers=_auth())

    assert respuesta.status_code == 200
    datos = respuesta.get_json()
    assert datos['total'] == 5 and datos['enviados'] == 2 and datos['quedan'] == 3 and datos['completo'] is False


def test_get_asistencias_vacio_204(client, permitir_todo, monkeypatch):
    monkeypatch.setattr(db, 'obtener_clase_por_id', lambda cid: {'id': 5, 'estado': 'abierta'})
    monkeypatch.setattr(db, 'buscar_asistencias_de_clase', lambda clase_id, estado, q: [])

    respuesta = client.get('/gradebook_api/clases/5/asistencias', headers=_auth())

    assert respuesta.status_code == 204
