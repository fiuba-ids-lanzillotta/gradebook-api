import pytest

from gradebook_api import db
from gradebook_api.services import grupos


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
