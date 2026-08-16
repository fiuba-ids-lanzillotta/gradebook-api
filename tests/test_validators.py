import pytest

from gradebook_api.validators.auth import validar_body_login
from gradebook_api.validators.items import validar_body_item


def _codigos(excepcion):
    return [error['code'] for error in excepcion.value.args[0]['errors']]


# --- login ---

def test_login_ok():
    assert validar_body_login({'usuario': 'admin', 'password': 'x'}) == {
        'usuario': 'admin', 'password': 'x',
    }


def test_login_acumula_errores():
    with pytest.raises(ValueError) as excepcion:
        validar_body_login({})

    assert set(_codigos(excepcion)) == {'required.usuario', 'required.password'}


# --- item ---

def test_item_ok_defaults():
    datos = validar_body_item({'nombre': 'Primer item'})

    assert datos['nombre'] == 'Primer item'
    assert datos['descripcion'] is None
    assert datos['activo'] is True


def test_item_ok_completo():
    datos = validar_body_item({'nombre': 'X', 'descripcion': 'algo', 'activo': False})

    assert datos == {'nombre': 'X', 'descripcion': 'algo', 'activo': False}


def test_item_sin_nombre():
    with pytest.raises(ValueError) as excepcion:
        validar_body_item({'descripcion': 'algo'})

    assert 'required.nombre' in _codigos(excepcion)


def test_item_activo_invalido():
    with pytest.raises(ValueError) as excepcion:
        validar_body_item({'nombre': 'X', 'activo': 'quizas'})

    assert 'invalid.bool' in _codigos(excepcion)
