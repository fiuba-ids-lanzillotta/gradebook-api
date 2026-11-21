"""Tests del registro de auditoría (tabla `registros` y GET /registros)."""
import pytest
from flask import request

import app as app_module
from gradebook_api import db, cache, registro
from gradebook_api.services import registros as service
from gradebook_api.services import auth as auth_service
from gradebook_api.services import grupos, asistencias
from gradebook_api.utils import generar_token


@pytest.fixture
def client():
    app_module.app.config['TESTING'] = True
    return app_module.app.test_client()


@pytest.fixture(autouse=True)
def _cache_desactivado(monkeypatch):
    """Neutraliza el cache (evita depender de Redis)."""
    monkeypatch.setattr(cache, 'obtener', lambda clave: None)
    monkeypatch.setattr(cache, 'guardar', lambda clave, valor, ttl: None)
    monkeypatch.setattr(cache, 'invalidar', lambda *claves: None)


@pytest.fixture
def permitir_todo(monkeypatch):
    """Hace que el chequeo de permisos pase siempre."""
    monkeypatch.setattr(auth_service, 'tiene_permiso', lambda payload, codigo: True)


@pytest.fixture
def espiar_registro(monkeypatch):
    """Espía registro.registrar sin escribir en la base."""
    llamadas = []
    monkeypatch.setattr(registro, 'registrar', lambda *args, **kwargs: llamadas.append((args, kwargs)) or True)
    return llamadas


def _auth(tipo='docente', rol='super_admin'):
    return {'Authorization': f'Bearer {generar_token(1, tipo, rol, "p@fi.uba.ar")}'}


def test_alumno_con_accion_ajena_no_entra():
    assert db._modo_auditoria('estudiantes.baja', 'estudiante') == 'vacio'
    assert db._modo_auditoria(None, 'estudiante') == 'alumno'
    assert db._modo_auditoria('grupos.crear', None) == 'accion'
    assert db._modo_auditoria('estudiantes.baja', None) == 'docente'
    assert db._modo_auditoria(None, None) == 'mixto'


# --- service: listar ---

def test_listar_pasa_filtros_a_la_db(monkeypatch):
    capturado = {}
    monkeypatch.setattr(db, 'buscar_registros', lambda **kw: capturado.update(kw) or ([], 0))

    pagina, total = service.listar(email='jp', accion='grupos.renombrar', tipo='docente',
                                   cursada_id='3', orden='asc', offset=10, limit=5)

    assert capturado == {
        'email': 'jp', 'accion': 'grupos.renombrar', 'actor_tipo': 'docente',
        'cursada_id': 3, 'ascendente': True, 'offset': 10, 'limit': 5,
    }
    assert pagina == [] and total == 0


def test_listar_agrega_el_rol_del_actor(monkeypatch):
    filas = [
        {'actor_tipo': 'docente', 'actor_id': 7},
        {'actor_tipo': 'estudiante', 'actor_id': 11},
        {'actor_tipo': 'docente', 'actor_id': 99},
    ]
    monkeypatch.setattr(db, 'buscar_registros', lambda **kw: ([dict(fila) for fila in filas], 3))
    monkeypatch.setattr(db, 'cargos_de_docentes', lambda ids: {7: 'Ayudante'})

    pagina, total = service.listar(offset=0, limit=10)

    assert [fila['rol'] for fila in pagina] == ['Ayudante', 'Alumno', 'Docente']
    assert total == 3


def test_listar_default_desc_sin_filtros(monkeypatch):
    capturado = {}
    monkeypatch.setattr(db, 'buscar_registros', lambda **kw: capturado.update(kw) or ([], 0))

    service.listar(offset=0, limit=50)

    assert capturado['email'] is None and capturado['accion'] is None
    assert capturado['actor_tipo'] is None and capturado['cursada_id'] is None
    assert capturado['ascendente'] is False


def test_listar_tipo_invalido_400():
    with pytest.raises(ValueError) as error:
        service.listar(tipo='admin')

    assert error.value.args[1] == 400
    assert error.value.args[0]['errors'][0]['code'] == 'invalid.body'


def test_listar_orden_invalido_400():
    with pytest.raises(ValueError) as error:
        service.listar(orden='descendente')

    assert error.value.args[1] == 400


# --- helper: registrar ---

def _contexto_con_actor(tipo='docente', sub='7', email='d@fi.uba.ar'):
    contexto = app_module.app.test_request_context('/gradebook_api/registros')
    contexto.push()
    request.usuario_actual = {'sub': sub, 'tipo': tipo, 'email': email}
    return contexto


def test_registrar_usa_actor_del_request(monkeypatch):
    capturado = []
    monkeypatch.setattr(db, 'insertar_registro', capturado.append)

    contexto = _contexto_con_actor()
    try:
        resultado = registro.registrar('grupos.renombrar', 'Renombró el equipo "A" a "B"',
                                       detalle={'grupo_id': 3}, cursada_id=4)
    finally:
        contexto.pop()

    assert resultado is True
    fila = capturado[0]
    assert fila['actor_tipo'] == 'docente' and fila['actor_id'] == 7
    assert fila['actor_email'] == 'd@fi.uba.ar'
    assert fila['accion'] == 'grupos.renombrar'
    assert fila['descripcion'] == 'Renombró el equipo "A" a "B"'
    assert fila['detalle'] == {'grupo_id': 3} and fila['cursada_id'] == 4


def test_registrar_actor_estudiante(monkeypatch):
    capturado = []
    monkeypatch.setattr(db, 'insertar_registro', capturado.append)

    contexto = _contexto_con_actor(tipo='estudiante', sub='11', email='a@fi.uba.ar')
    try:
        registro.registrar('grupos.crear', 'Creó el equipo "Alfa"')
    finally:
        contexto.pop()

    assert capturado[0]['actor_tipo'] == 'estudiante' and capturado[0]['actor_id'] == 11


def test_registrar_falla_abierto_si_db_falla(monkeypatch):
    def _fallar(fila):
        raise RuntimeError('db caída')

    monkeypatch.setattr(db, 'insertar_registro', _fallar)

    contexto = _contexto_con_actor()
    try:
        resultado = registro.registrar('x.y', 'desc')
    finally:
        contexto.pop()

    assert resultado is False


def test_registrar_sin_actor_no_escribe(monkeypatch):
    capturado = []
    monkeypatch.setattr(db, 'insertar_registro', capturado.append)

    contexto = app_module.app.test_request_context('/gradebook_api/registros')
    contexto.push()
    try:
        resultado = registro.registrar('x.y', 'desc')
    finally:
        contexto.pop()

    assert resultado is False and capturado == []


# --- ruta: GET /registros ---

def test_get_registros_200_con_filtros(client, permitir_todo, monkeypatch):
    fila = {'id': 1, 'actor_tipo': 'docente', 'actor_id': 1, 'actor_email': 'd@fi.uba.ar',
            'accion': 'grupos.renombrar', 'descripcion': 'Renombró el equipo "A" a "B"',
            'cursada_id': 4, 'detalle': {'grupo_id': 3}, 'created_at': '2026-09-01T10:00:00Z'}
    capturado = {}
    monkeypatch.setattr(db, 'buscar_registros', lambda **kw: capturado.update(kw) or ([fila], 1))
    monkeypatch.setattr(db, 'cargos_de_docentes', lambda ids: {1: 'Profesor'})

    respuesta = client.get('/gradebook_api/registros?email=jp&accion=grupos.renombrar&tipo=docente&cursada=4&_orden=asc',
                           headers=_auth())

    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert cuerpo['registros'] == [fila]
    assert capturado['email'] == 'jp' and capturado['accion'] == 'grupos.renombrar'
    assert capturado['actor_tipo'] == 'docente' and capturado['cursada_id'] == 4
    assert capturado['ascendente'] is True


def test_get_registros_vacio_204(client, permitir_todo, monkeypatch):
    monkeypatch.setattr(db, 'buscar_registros', lambda **kw: ([], 0))

    respuesta = client.get('/gradebook_api/registros', headers=_auth())

    assert respuesta.status_code == 204


def test_get_registros_sin_token_401(client):
    respuesta = client.get('/gradebook_api/registros')

    assert respuesta.status_code == 401


def test_get_registros_sin_permiso_403(client, monkeypatch):
    monkeypatch.setattr(auth_service, 'tiene_permiso', lambda payload, codigo: False)

    respuesta = client.get('/gradebook_api/registros', headers=_auth(tipo='estudiante', rol='usuario'))

    assert respuesta.status_code == 403
    assert respuesta.get_json()['errors'][0]['code'] == 'auth.forbidden'


def test_get_registros_tipo_invalido_400(client, permitir_todo):
    respuesta = client.get('/gradebook_api/registros?tipo=admin', headers=_auth())

    assert respuesta.status_code == 400
    assert respuesta.get_json()['errors'][0]['code'] == 'invalid.body'


# --- instrumentación representativa ---

def _mocks_detalle_grupo(monkeypatch):
    """Mocks de db que necesita grupos.detalle() al final de cada mutación."""
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: {'id': 8, 'cursada_id': 4, 'nombre': 'TP'})
    monkeypatch.setattr(db, 'obtener_cursada_por_id', lambda cursada_id: {'id': 4, 'anio': 2026, 'cuatrimestre': 1})
    monkeypatch.setattr(db, 'listar_grupos_de_evaluaciones', lambda ids: [{'id': 3, 'nombre': 'Alfa'}])
    monkeypatch.setattr(db, 'miembros_de_grupos', lambda ids: [])
    monkeypatch.setattr(db, 'inscriptos_cursando', lambda cursada_id: [])
    monkeypatch.setattr(db, 'obtener_docente_por_id', lambda docente_id: {})


def test_renombrar_grupo_registra(espiar_registro, monkeypatch):
    monkeypatch.setattr(db, 'obtener_grupo', lambda grupo_id: {
        'id': 3, 'owner_id': 2, 'evaluacion_id': 8, 'tutor_id': None, 'nombre': 'Alfa', 'numero': 1,
    })
    monkeypatch.setattr(db, 'actualizar_grupo', lambda grupo_id, datos: datos)
    _mocks_detalle_grupo(monkeypatch)

    grupos.renombrar(3, 'Beta')

    args, kwargs = espiar_registro[0]
    assert args[0] == 'grupos.renombrar'
    assert 'Renombró el equipo "Alfa" a "Beta"' in args[1]
    assert kwargs['cursada_id'] == 4


def test_cerrar_clase_registra(espiar_registro, monkeypatch):
    monkeypatch.setattr(db, 'obtener_clase_por_id',
                        lambda cid: {'id': 5, 'cursada_id': 9, 'fecha': '2026-09-01', 'estado': 'abierta'})
    monkeypatch.setattr(db, 'cerrar_asistencias_pendientes', lambda clase_id: 3)
    monkeypatch.setattr(db, 'actualizar_estado_clase', lambda clase_id, estado: 1)

    asistencias.cerrar_clase(5)

    args, kwargs = espiar_registro[0]
    assert args[0] == 'asistencia.cerrar'
    assert 'Cerró la toma de asistencia del 2026-09-01' in args[1]
    assert kwargs['cursada_id'] == 9


def test_enviar_qrs_registra_cuando_encola(espiar_registro, monkeypatch):
    monkeypatch.setattr(db, 'obtener_clase_por_id',
                        lambda cid: {'id': 5, 'cursada_id': 9, 'fecha': '2026-09-01', 'estado': 'abierta'})
    monkeypatch.setattr(cache, 'adquirir_lock', lambda clave, ttl: True)
    monkeypatch.setattr(cache, 'liberar_lock', lambda clave: None)
    monkeypatch.setattr(db, 'buscar_asistencias_a_enviar', lambda *a: [
        {'id': 1, 'codigo': 'AAAA2345', 'envio_intentos': 0, 'estudiantes': {'nombre': 'Ana', 'email': 'a@fi.uba.ar'}},
    ])
    monkeypatch.setattr(db, 'registrar_envio_asistencia', lambda *a: 1)
    monkeypatch.setattr(db, 'contar_asistencias', lambda *a, **k: 1)

    asistencias.enviar_qrs(5)

    args, kwargs = espiar_registro[0]
    assert args[0] == 'asistencia.enviar_qrs'
    assert 'Envió los QRs de la clase del 2026-09-01' in args[1]
    assert kwargs['cursada_id'] == 9


def test_enviar_qrs_no_registra_si_no_hizo_nada(espiar_registro, monkeypatch):
    monkeypatch.setattr(db, 'obtener_clase_por_id',
                        lambda cid: {'id': 5, 'cursada_id': 9, 'fecha': '2026-09-01', 'estado': 'abierta'})
    monkeypatch.setattr(cache, 'adquirir_lock', lambda clave, ttl: True)
    monkeypatch.setattr(cache, 'liberar_lock', lambda clave: None)
    monkeypatch.setattr(db, 'buscar_asistencias_a_enviar', lambda *a: [])
    monkeypatch.setattr(db, 'contar_asistencias', lambda *a, **k: 0)

    asistencias.enviar_qrs(5)

    assert espiar_registro == []
