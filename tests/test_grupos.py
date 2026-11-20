import pytest

import app as app_module
from gradebook_api import db, cache
from gradebook_api.services import grupos
from gradebook_api.services import auth as auth_service
from gradebook_api.utils import construir_error_api, generar_token


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


def _auth(tipo='docente', rol='super_admin'):
    return {'Authorization': f'Bearer {generar_token(1, tipo, rol, "p@fi.uba.ar")}'}


def test_listar_de_cursada_cuenta_integrantes(monkeypatch):
    monkeypatch.setattr(db, 'obtener_cursada_por_id', lambda cursada_id: {'id': cursada_id})
    monkeypatch.setattr(db, 'listar_evaluaciones_grupales', lambda cursada_id: [{'id': 8, 'nombre': 'TP'}])
    monkeypatch.setattr(db, 'listar_grupos_de_evaluaciones', lambda ids: [{
        'id': 3, 'evaluacion_id': 8, 'numero': 1, 'nombre': 'Equipo1', 'owner_id': 2, 'tutor_id': None,
    }])
    monkeypatch.setattr(db, 'miembros_de_grupos', lambda ids: [
        {'grupo_id': 3, 'estudiante_id': 2, 'estudiantes': {'id': 2, 'nombre': 'Ana', 'apellido': 'Paz', 'padron': '1'}},
    ])
    monkeypatch.setattr(db, 'obtener_docente_por_id', lambda docente_id: {})

    resultado = grupos.listar_de_cursada(1)

    assert resultado['grupos'][0]['nombre'] == 'Equipo1'
    assert resultado['grupos'][0]['integrantes'] == 1
    assert resultado['grupos'][0]['evaluacion_nombre'] == 'TP'


def test_detalle_no_ofrece_el_mismo_equipo(monkeypatch):
    monkeypatch.setattr(db, 'obtener_grupo', lambda grupo_id: {
        'id': 3, 'owner_id': 2, 'evaluacion_id': 8, 'tutor_id': None, 'nombre': 'Alfa', 'numero': 1,
    })
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: {'id': 8, 'cursada_id': 1, 'nombre': 'TP'})
    monkeypatch.setattr(db, 'obtener_cursada_por_id', lambda cursada_id: {'id': 1, 'anio': 2026, 'cuatrimestre': 2})
    monkeypatch.setattr(db, 'listar_grupos_de_evaluaciones', lambda ids: [
        {'id': 3, 'nombre': 'Alfa'},
        {'id': 4, 'nombre': 'Beta'},
    ])
    monkeypatch.setattr(db, 'miembros_de_grupos', lambda ids: [])
    monkeypatch.setattr(db, 'inscriptos_cursando', lambda cursada_id: [])
    monkeypatch.setattr(db, 'obtener_docente_por_id', lambda docente_id: {})

    resultado = grupos.detalle('3')

    assert [fila['nombre'] for fila in resultado['otros_grupos']] == ['Beta']


def test_echar_al_unico_owner_no_deja_el_equipo_vacio(monkeypatch):
    monkeypatch.setattr(db, 'obtener_grupo', lambda grupo_id: {
        'id': 3, 'owner_id': 2, 'evaluacion_id': 8, 'tutor_id': None, 'nombre': 'Equipo1', 'numero': 1,
    })
    monkeypatch.setattr(db, 'miembros_de_grupos', lambda ids: [{'grupo_id': 3, 'estudiante_id': 2}])

    with pytest.raises(ValueError) as error:
        grupos.echar_integrante(3, 2)

    assert error.value.args[1] == 409


def test_agregar_integrante_ya_en_otro_equipo_409(monkeypatch):
    monkeypatch.setattr(db, 'obtener_grupo', lambda grupo_id: {
        'id': 3, 'evaluacion_id': 8, 'owner_id': 2, 'tutor_id': None, 'nombre': 'Alfa', 'numero': 1,
    })
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: {'id': 8, 'cursada_id': 1})
    monkeypatch.setattr(db, 'obtener_inscripcion', lambda cursada_id, estudiante_id: {'estado': 'cursando'})
    monkeypatch.setattr(db, 'listar_grupos_de_evaluaciones', lambda ids: [{'id': 3}, {'id': 4}])
    monkeypatch.setattr(db, 'miembros_de_grupos', lambda ids: [{'grupo_id': 4, 'estudiante_id': 7}])

    with pytest.raises(ValueError) as error:
        grupos.agregar_integrante(3, 7)

    assert error.value.args[1] == 409


def test_asignar_tutores_item_invalido_400():
    with pytest.raises(ValueError) as error:
        grupos.asignar_tutores(['no-es-un-dict'])

    assert error.value.args[1] == 400


# --- rutas ---

def test_get_grupos_de_cursada_ok(client, permitir_todo, monkeypatch):
    monkeypatch.setattr('gradebook_api.routes.grupos.listar_de_cursada',
                        lambda cursada_id: {'grupos': [{'id': 3, 'nombre': 'Alfa'}]})

    respuesta = client.get('/gradebook_api/cursadas/9/grupos', headers=_auth())

    assert respuesta.status_code == 200
    assert respuesta.get_json()['grupos'][0]['nombre'] == 'Alfa'


def test_get_grupo_no_existe_404(client, permitir_todo, monkeypatch):
    def _detalle(grupo_id):
        raise ValueError(construir_error_api(
            code='grupo.not.found', message='Equipo no encontrado', description='x',
        ), 404)

    monkeypatch.setattr('gradebook_api.routes.grupos.detalle', _detalle)

    respuesta = client.get('/gradebook_api/grupos/99', headers=_auth())

    assert respuesta.status_code == 404
    assert respuesta.get_json()['errors'][0]['code'] == 'grupo.not.found'


def test_put_grupo_sin_permiso_403(client, monkeypatch):
    monkeypatch.setattr(auth_service, 'tiene_permiso', lambda payload, codigo: False)

    respuesta = client.put('/gradebook_api/grupos/3', headers=_auth(), json={'nombre': 'X'})

    assert respuesta.status_code == 403
    assert respuesta.get_json()['errors'][0]['code'] == 'auth.forbidden'


def test_put_tutores_ok(client, permitir_todo, monkeypatch):
    monkeypatch.setattr('gradebook_api.routes.grupos.asignar_tutores',
                        lambda asignaciones: {'actualizados': len(asignaciones), 'sin_tutor': 0})

    respuesta = client.put('/gradebook_api/grupos/tutores', headers=_auth(),
                           json={'asignaciones': [{'grupo_id': 3, 'tutor_id': 2}]})

    assert respuesta.status_code == 200
    assert respuesta.get_json()['actualizados'] == 1


def test_post_integrante_201(client, permitir_todo, monkeypatch):
    monkeypatch.setattr('gradebook_api.routes.grupos.agregar_integrante',
                        lambda grupo_id, estudiante_id: {'id': grupo_id})

    respuesta = client.post('/gradebook_api/grupos/3/integrantes',
                            headers=_auth(), json={'estudiante_id': 7})

    assert respuesta.status_code == 201


def test_delete_integrante_ok(client, permitir_todo, monkeypatch):
    monkeypatch.setattr('gradebook_api.routes.grupos.echar_integrante',
                        lambda grupo_id, estudiante_id: {'id': grupo_id})

    respuesta = client.delete('/gradebook_api/grupos/3/integrantes/7', headers=_auth())

    assert respuesta.status_code == 200


def test_post_transferir_ok(client, permitir_todo, monkeypatch):
    capturado = {}

    def _transferir(grupo_id, estudiante_id, destino):
        capturado['destino'] = destino
        return {'id': grupo_id}

    monkeypatch.setattr('gradebook_api.routes.grupos.transferir_integrante', _transferir)

    respuesta = client.post('/gradebook_api/grupos/3/integrantes/7/transferir',
                            headers=_auth(), json={'grupo_destino_id': 4})

    assert respuesta.status_code == 200
    assert capturado['destino'] == 4
