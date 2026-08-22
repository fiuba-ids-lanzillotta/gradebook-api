import pytest

from gradebook_api.validators.auth import validar_body_login
from gradebook_api.validators.docentes import validar_body_docente
from gradebook_api.validators.estudiantes import validar_body_estudiante, validar_body_estado_inscripcion
from gradebook_api.validators.permisos import validar_body_permisos_rol, validar_body_overrides


def _codigos(excepcion):
    return [error['code'] for error in excepcion.value.args[0]['errors']]


# --- login ---

def test_login_ok():
    assert validar_body_login({'email': 'Admin@Fi.uba.ar', 'password': 'x'}) == {
        'email': 'admin@fi.uba.ar', 'password': 'x', 'recaptcha_token': '',
    }


def test_login_acumula_errores():
    with pytest.raises(ValueError) as excepcion:
        validar_body_login({})

    assert set(_codigos(excepcion)) == {'required.email', 'required.password'}


# --- docente ---

def test_docente_ok():
    datos = validar_body_docente({
        'nombre': 'Ada', 'apellido': 'Lovelace', 'email': 'ada@fi.uba.ar',
        'rol': 'Profesor', 'password': 'secreto',
    })

    assert datos['rol'] == 'Profesor'
    assert datos['email'] == 'ada@fi.uba.ar'
    assert datos['password'] == 'secreto'


def test_docente_cargo_invalido():
    with pytest.raises(ValueError) as excepcion:
        validar_body_docente({
            'nombre': 'Ada', 'apellido': 'L', 'email': 'ada@fi.uba.ar',
            'rol': 'Jefe', 'password': 'x',
        })

    assert 'invalid.cargo.docente' in _codigos(excepcion)


def test_docente_password_requerido_al_crear():
    with pytest.raises(ValueError) as excepcion:
        validar_body_docente({'nombre': 'Ada', 'apellido': 'L', 'email': 'ada@fi.uba.ar', 'rol': 'Ayudante'})

    assert 'required.password' in _codigos(excepcion)


def test_docente_password_opcional_al_actualizar():
    datos = validar_body_docente(
        {'nombre': 'Ada', 'apellido': 'L', 'email': 'ada@fi.uba.ar', 'rol': 'Ayudante'},
        requiere_password=False,
    )

    assert datos['password'] is None


# --- estudiante ---

def test_estudiante_ok():
    datos = validar_body_estudiante({
        'padron': '116530', 'nombre': 'Ian', 'apellido': 'Acosta',
        'email': 'ian@fi.uba.ar', 'password': '116530',
    })

    assert datos['padron'] == '116530'
    assert datos['email'] == 'ian@fi.uba.ar'


def test_estudiante_sin_padron():
    with pytest.raises(ValueError) as excepcion:
        validar_body_estudiante({'nombre': 'Ian', 'apellido': 'Acosta', 'email': 'ian@fi.uba.ar', 'password': 'x'})

    assert 'required.padron' in _codigos(excepcion)


# --- estado de inscripción (baja lógica) ---

def test_estado_inscripcion_baja_ok():
    assert validar_body_estado_inscripcion({'estado': 'baja', 'motivo': 'x'}) == {'estado': 'baja', 'motivo': 'x'}


def test_estado_inscripcion_abandono_sin_motivo():
    assert validar_body_estado_inscripcion({'estado': 'abandono'}) == {'estado': 'abandono', 'motivo': None}


def test_estado_inscripcion_baja_requiere_motivo():
    with pytest.raises(ValueError) as excepcion:
        validar_body_estado_inscripcion({'estado': 'baja'})

    assert 'required.motivo' in _codigos(excepcion)


def test_estado_inscripcion_invalido():
    with pytest.raises(ValueError) as excepcion:
        validar_body_estado_inscripcion({'estado': 'egresado'})

    assert 'invalid.estado.inscripcion' in _codigos(excepcion)


# --- permisos ---

def test_permisos_rol_ok():
    assert validar_body_permisos_rol({'permisos': ['docentes.leer', 'estudiantes.leer']}) == ['docentes.leer', 'estudiantes.leer']


def test_permisos_rol_body_invalido():
    with pytest.raises(ValueError) as excepcion:
        validar_body_permisos_rol({'permisos': 'no-es-lista'})

    assert 'invalid.body' in _codigos(excepcion)


def test_overrides_ok():
    resultado = validar_body_overrides({'permisos': [
        {'permiso': 'docentes.gestionar', 'concedido': True},
        {'permiso': 'docentes.leer', 'concedido': False},
    ]})

    assert resultado == [
        {'codigo': 'docentes.gestionar', 'concedido': True},
        {'codigo': 'docentes.leer', 'concedido': False},
    ]


def test_overrides_concedido_invalido():
    with pytest.raises(ValueError) as excepcion:
        validar_body_overrides({'permisos': [{'permiso': 'docentes.gestionar', 'concedido': 'quizas'}]})

    assert 'invalid.bool' in _codigos(excepcion)
