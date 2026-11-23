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


def test_habilitar_cierra_la_activa_y_transfiere_equipos(monkeypatch, espiar_registro):
    """Abrir B estando A abierta: cierra A y copia sus equipos a B."""
    activa = {**EVAL_GRUPAL, 'id': 8, 'nombre': 'TP Redes', 'permite_crear_grupos': True}
    escritos = []
    insertados = []
    miembros_agregados = []
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: EVAL_GRUPAL)
    monkeypatch.setattr(db, 'buscar_evaluacion_con_creacion_grupos', lambda cursada_id: activa)
    monkeypatch.setattr(db, 'actualizar_evaluacion',
                        lambda eid, datos: escritos.append((eid, datos)) or {**EVAL_GRUPAL, **datos})
    monkeypatch.setattr(db, 'listar_grupos_de_evaluaciones', lambda ids: [
        {'id': 40, 'evaluacion_id': 8, 'numero': 1, 'nombre': 'Halcones', 'owner_id': 2, 'tutor_id': 9},
    ] if ids == [8] else [])
    monkeypatch.setattr(db, 'miembros_de_grupos', lambda ids: [
        {'grupo_id': 40, 'estudiante_id': 2},
        {'grupo_id': 40, 'estudiante_id': 5},
    ] if 40 in ids else [])
    monkeypatch.setattr(db, 'insertar_grupo',
                        lambda evaluacion_id, numero, nombre, owner_id, tutor_id=None:
                        insertados.append((evaluacion_id, numero, nombre, owner_id, tutor_id)) or {'id': 50})
    monkeypatch.setattr(db, 'agregar_miembro', lambda grupo_id, estudiante_id: miembros_agregados.append((grupo_id, estudiante_id)))

    resultado = service.habilitar_crear_grupos(7, True)

    assert (8, {'permite_crear_grupos': False}) in escritos
    assert (7, {'permite_crear_grupos': True}) in escritos
    assert insertados == [(7, 1, 'Halcones', 2, 9)]
    assert miembros_agregados == [(50, 2), (50, 5)]
    assert resultado['permite_crear_grupos'] is True
    assert 'transfirió 1 equipos desde "TP Redes"' in espiar_registro[0][0][1]


def test_habilitar_sin_activa_copia_desde_la_ultima_con_equipos(monkeypatch, espiar_registro):
    """Cerrada A y abierta B después: el origen es la evaluación con equipos más reciente."""
    insertados = []
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: EVAL_GRUPAL)
    monkeypatch.setattr(db, 'buscar_evaluacion_con_creacion_grupos', lambda cursada_id: {})
    monkeypatch.setattr(db, 'listar_evaluaciones', lambda cursada_id: [
        {**EVAL_GRUPAL, 'id': 8, 'nombre': 'TP viejo', 'updated_at': '2026-01-01'},
        {**EVAL_GRUPAL, 'id': 9, 'nombre': 'TP reciente', 'updated_at': '2026-03-01'},
        {**EVAL_GRUPAL, 'id': 10, 'nombre': 'TP sin equipos', 'updated_at': '2026-05-01'},
    ])
    equipos = {
        8: [{'id': 41, 'evaluacion_id': 8, 'numero': 1, 'nombre': 'Viejos', 'owner_id': 5, 'tutor_id': None}],
        9: [{'id': 40, 'evaluacion_id': 9, 'numero': 3, 'nombre': 'Dinamita', 'owner_id': 2, 'tutor_id': None}],
    }
    monkeypatch.setattr(db, 'listar_grupos_de_evaluaciones',
                        lambda ids: [g for eid in ids for g in equipos.get(eid, [])])
    monkeypatch.setattr(db, 'miembros_de_grupos', lambda ids: [])
    monkeypatch.setattr(db, 'insertar_grupo',
                        lambda evaluacion_id, numero, nombre, owner_id, tutor_id=None:
                        insertados.append((evaluacion_id, numero, nombre)) or {'id': 50})
    monkeypatch.setattr(db, 'agregar_miembro', lambda grupo_id, estudiante_id: None)
    monkeypatch.setattr(db, 'actualizar_evaluacion',
                        lambda eid, datos: {**EVAL_GRUPAL, **datos})

    service.habilitar_crear_grupos(7, True)

    assert insertados == [(7, 3, 'Dinamita')]


def test_habilitar_no_copia_si_el_destino_ya_tiene_equipos(monkeypatch, espiar_registro):
    """El snapshot no pisa equipos existentes del destino."""
    insertados = []
    activa = {**EVAL_GRUPAL, 'id': 8, 'permite_crear_grupos': True}
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: EVAL_GRUPAL)
    monkeypatch.setattr(db, 'buscar_evaluacion_con_creacion_grupos', lambda cursada_id: activa)
    monkeypatch.setattr(db, 'actualizar_evaluacion',
                        lambda eid, datos: {**EVAL_GRUPAL, **datos})
    monkeypatch.setattr(db, 'listar_grupos_de_evaluaciones', lambda ids: [
        {'id': 40, 'evaluacion_id': ids[0], 'numero': 1, 'nombre': 'X', 'owner_id': 2, 'tutor_id': None},
    ])
    monkeypatch.setattr(db, 'miembros_de_grupos', lambda ids: [])
    monkeypatch.setattr(db, 'insertar_grupo',
                        lambda evaluacion_id, numero, nombre, owner_id, tutor_id=None:
                        insertados.append(nombre) or {'id': 50})
    monkeypatch.setattr(db, 'agregar_miembro', lambda grupo_id, estudiante_id: None)

    service.habilitar_crear_grupos(7, True)

    assert insertados == []


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
    monkeypatch.setattr(db, 'listar_evaluaciones', lambda cursada_id: [EVAL_GRUPAL])
    monkeypatch.setattr(db, 'listar_grupos_de_evaluaciones', lambda ids: [])
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
    monkeypatch.setattr(db, 'listar_evaluaciones', lambda cursada_id: [EVAL_GRUPAL])
    monkeypatch.setattr(db, 'listar_grupos_de_evaluaciones', lambda ids: [])
    monkeypatch.setattr(db, 'actualizar_evaluacion',
                        lambda eid, datos: {**EVAL_GRUPAL, **datos})

    respuesta = client.put('/gradebook_api/evaluaciones/7/crear-grupos',
                           json={'habilitado': True}, headers=_auth())

    assert respuesta.status_code == 200
    assert respuesta.get_json()['permite_crear_grupos'] is True


def test_put_crear_grupos_transicion_200(client, monkeypatch, permitir_todo):
    """Abrir B estando A abierta transiciona: responde 200 con B habilitada."""
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: EVAL_GRUPAL)
    monkeypatch.setattr(db, 'buscar_evaluacion_con_creacion_grupos',
                        lambda cursada_id: {**EVAL_GRUPAL, 'id': 8})
    monkeypatch.setattr(db, 'actualizar_evaluacion',
                        lambda eid, datos: {**EVAL_GRUPAL, **datos})
    monkeypatch.setattr(db, 'listar_grupos_de_evaluaciones', lambda ids: [])
    monkeypatch.setattr(db, 'miembros_de_grupos', lambda ids: [])
    monkeypatch.setattr(registro, 'registrar', lambda *args, **kwargs: True)

    respuesta = client.put('/gradebook_api/evaluaciones/7/crear-grupos',
                           json={'habilitado': True}, headers=_auth())

    assert respuesta.status_code == 200
    assert respuesta.get_json()['permite_crear_grupos'] is True


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


def test_listar_cuenta_las_instancias_de_cada_evaluacion(monkeypatch):
    monkeypatch.setattr(db, 'obtener_cursada_por_id', lambda cursada_id: {'id': cursada_id})
    monkeypatch.setattr(db, 'listar_evaluaciones', lambda cursada_id: [{
        'id': 7, 'cursada_id': 3, 'nombre': 'TP Bash', 'tipo': 'opcional',
        'criterio': 'entregado_no_entregado', 'peso': 0.5, 'modalidad': 'grupal',
        'visibilidad': 'deshabilitado', 'permite_crear_grupos': False,
    }])
    monkeypatch.setattr(db, 'contar_instancias', lambda ids: {7: 2} if ids == [7] else {})

    resultado = service.listar_de_cursada(3)

    assert resultado['evaluaciones'][0]['instancias'] == 2
    assert resultado['evaluaciones'][0]['nombre'] == 'TP Bash'


def test_crear_arranca_deshabilitada_y_sin_grupos(monkeypatch, espiar_registro):
    monkeypatch.setattr(db, 'obtener_cursada_por_id', lambda cursada_id: {'id': cursada_id})
    capturado = {}
    creadas = []
    monkeypatch.setattr(
        db, 'insertar_evaluacion',
        lambda datos: capturado.update(datos) or {'id': 9, **datos},
    )
    monkeypatch.setattr(
        db, 'insertar_instancia',
        lambda evaluacion_id, numero, nombre, fecha: creadas.append((evaluacion_id, numero, nombre)) or {'id': numero},
    )

    resultado = service.crear(3, {
        'nombre': 'TP Prode', 'tipo': 'opcional', 'criterio': 'nota',
        'peso': 0.5, 'modalidad': 'grupal', 'instancias': 2,
    })

    assert capturado['visibilidad'] == 'deshabilitado'
    assert capturado['permite_crear_grupos'] is False
    assert creadas == [(9, 1, 'Instancia 1'), (9, 2, 'Instancia 2')]
    assert resultado['instancias'] == 2
    assert espiar_registro[0][0][0] == 'evaluaciones.crear'


def test_cambiar_visibilidad_habilita(monkeypatch, espiar_registro):
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: {
        'id': 7, 'cursada_id': 3, 'nombre': 'Parcial', 'visibilidad': 'deshabilitado',
    })
    monkeypatch.setattr(db, 'actualizar_evaluacion', lambda evaluacion_id, datos: datos)
    monkeypatch.setattr(db, 'contar_instancias', lambda ids: {7: 2})

    resultado = service.cambiar_visibilidad(7, 'habilitado')

    assert resultado['visibilidad'] == 'habilitado'
    assert espiar_registro[0][0][0] == 'evaluaciones.visibilidad'


def test_cambiar_visibilidad_rechaza_sin_entrega(monkeypatch):
    monkeypatch.setattr(db, 'obtener_evaluacion', lambda evaluacion_id: {
        'id': 7, 'cursada_id': 3, 'nombre': 'Parcial',
    })

    with pytest.raises(ValueError) as error:
        service.cambiar_visibilidad(7, 'sin_entrega')

    assert error.value.args[1] == 400


def test_crear_rechaza_peso_fuera_de_rango(monkeypatch):
    monkeypatch.setattr(db, 'obtener_cursada_por_id', lambda cursada_id: {'id': cursada_id})

    with pytest.raises(ValueError) as error:
        service.crear(3, {
            'nombre': 'Parcial', 'tipo': 'obligatorio', 'criterio': 'nota',
            'peso': 11, 'modalidad': 'individual',
        })

    assert error.value.args[1] == 400
