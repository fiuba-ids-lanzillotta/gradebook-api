"""Tests de servicios con la capa de datos (db) mockeada; no tocan Supabase."""
import pytest

from gradebook_api import db, cache
from gradebook_api.services import auth, docentes, estudiantes, permisos


def _codigos(excepcion):
    return [error['code'] for error in excepcion.value.args[0]['errors']]


# ---------------------------------------------------------------
# auth: login y resolución de permisos
# ---------------------------------------------------------------

def test_autenticar_docente_ok(monkeypatch):
    from gradebook_api.utils import hashear_password
    docente = {'id': 1, 'email': 'p@fi.uba.ar', 'rol': 'Profesor', 'activo': True,
               'password_hash': hashear_password('secreto')}
    monkeypatch.setattr(db, 'obtener_docente_por_email', lambda email: docente)

    resultado = auth.autenticar({'email': 'p@fi.uba.ar', 'password': 'secreto'})

    assert resultado['usuario']['tipo'] == 'docente'
    assert resultado['usuario']['rol'] == 'super_admin'   # Profesor -> super_admin
    assert resultado['token']


def test_autenticar_estudiante_ok(monkeypatch):
    from gradebook_api.utils import hashear_password
    monkeypatch.setattr(db, 'obtener_docente_por_email', lambda email: {})
    estudiante = {'id': 9, 'email': 'a@fi.uba.ar', 'activo': True,
                  'password_hash': hashear_password('116530')}
    monkeypatch.setattr(db, 'obtener_estudiante_por_email', lambda email: estudiante)

    resultado = auth.autenticar({'email': 'a@fi.uba.ar', 'password': '116530'})

    assert resultado['usuario']['tipo'] == 'estudiante'
    assert resultado['usuario']['rol'] == 'usuario'


def test_autenticar_credenciales_invalidas(monkeypatch):
    monkeypatch.setattr(db, 'obtener_docente_por_email', lambda email: {})
    monkeypatch.setattr(db, 'obtener_estudiante_por_email', lambda email: {})

    with pytest.raises(ValueError) as excepcion:
        auth.autenticar({'email': 'x@fi.uba.ar', 'password': 'mal'})

    assert excepcion.value.args[1] == 401
    assert _codigos(excepcion) == ['invalid.credentials']


def test_permisos_efectivos_aplica_overrides(monkeypatch):
    monkeypatch.setattr(db, 'obtener_rol_por_codigo', lambda codigo: {'id': 10})
    monkeypatch.setattr(db, 'obtener_codigos_permisos_de_rol', lambda rol_id: ['docentes.leer'])
    monkeypatch.setattr(db, 'obtener_overrides_docente', lambda persona_id: [
        {'codigo': 'estudiantes.leer', 'concedido': True},   # otorga
        {'codigo': 'docentes.leer',    'concedido': False},  # revoca
    ])

    payload = {'sub': '1', 'tipo': 'docente', 'rol': 'super_admin'}

    assert auth.permisos_efectivos_de_payload(payload) == ['estudiantes.leer']


def test_tiene_permiso(monkeypatch):
    monkeypatch.setattr(auth, 'permisos_efectivos_de_payload', lambda payload: ['docentes.leer'])

    payload = {'sub': '1', 'tipo': 'estudiante', 'rol': 'usuario'}

    assert auth.tiene_permiso(payload, 'docentes.leer') is True
    assert auth.tiene_permiso(payload, 'docentes.gestionar') is False


# ---------------------------------------------------------------
# docentes / estudiantes
# ---------------------------------------------------------------

def test_crear_docente_email_duplicado(monkeypatch):
    monkeypatch.setattr(db, 'obtener_docente_por_email', lambda email: {'id': 2, 'email': email})

    with pytest.raises(ValueError) as excepcion:
        docentes.crear_docente({'nombre': 'A', 'apellido': 'B', 'email': 'a@fi.uba.ar',
                                'rol': 'Ayudante', 'password': 'x'})

    assert _codigos(excepcion) == ['email.duplicated']
    assert excepcion.value.args[1] == 409


def test_crear_docente_ok(monkeypatch):
    monkeypatch.setattr(db, 'obtener_docente_por_email', lambda email: {})
    monkeypatch.setattr(db, 'insertar_docente', lambda *args: 5)
    monkeypatch.setattr(db, 'obtener_docente_por_id',
                        lambda docente_id: {'id': docente_id, 'nombre': 'A', 'apellido': 'B',
                                            'email': 'a@fi.uba.ar', 'rol': 'Ayudante', 'foto': None,
                                            'activo': True, 'created_at': None, 'updated_at': None})

    resultado = docentes.crear_docente({'nombre': 'A', 'apellido': 'B', 'email': 'a@fi.uba.ar',
                                        'rol': 'Ayudante', 'password': 'x'})

    assert resultado['id'] == 5 and 'password_hash' not in resultado


def test_importar_estudiantes_csv_ok(monkeypatch):
    # Un estudiante ya existe (por padrón) → se omite; el otro se crea.
    monkeypatch.setattr(db, 'obtener_todos_los_estudiantes',
                        lambda: [{'padron': '111', 'email': 'ya@fi.uba.ar'}])
    capturado = {}
    monkeypatch.setattr(db, 'insertar_estudiantes_bulk',
                        lambda filas: capturado.setdefault('filas', filas) or filas)

    csv_texto = (
        ';Legajo;Alumno;Estado;Instancias;Email;Telefono\n'
        '1;111;ACOSTA, IAN;Pendiente;Regularidad;Email Principal: ya@fi.uba.ar;-\n'
        '2;222;PEREZ, ANA;Pendiente;Regularidad;Email Principal: ana@fi.uba.ar;-\n'
        '3;;SIN LEGAJO;Pendiente;Regularidad;Email Principal: x@fi.uba.ar;-\n'
    )

    resultado = estudiantes.importar_estudiantes_csv(csv_texto)

    assert resultado['creados'] == 1
    assert capturado['filas'][0]['padron'] == '222'
    assert 'password_hash' in capturado['filas'][0]
    assert [o['padron'] for o in resultado['omitidos']] == ['111']
    assert len(resultado['errores']) == 1   # la fila sin legajo


def test_importar_estudiantes_csv_vacio(monkeypatch):
    with pytest.raises(ValueError) as excepcion:
        estudiantes.importar_estudiantes_csv(';Legajo;Alumno;Estado;Instancias;Email;Telefono\n')

    assert _codigos(excepcion) == ['invalid.csv']


def test_crear_estudiante_padron_duplicado(monkeypatch):
    monkeypatch.setattr(db, 'obtener_estudiante_por_padron', lambda padron: {'id': 3, 'padron': padron})

    with pytest.raises(ValueError) as excepcion:
        estudiantes.crear_estudiante({'padron': '100', 'nombre': 'A', 'apellido': 'B',
                                      'email': 'a@fi.uba.ar', 'password': '100'})

    assert _codigos(excepcion) == ['padron.duplicated']
    assert excepcion.value.args[1] == 409


# ---------------------------------------------------------------
# permisos: asignación a rol
# ---------------------------------------------------------------

def test_asignar_permisos_a_rol_ok(monkeypatch):
    monkeypatch.setattr(db, 'obtener_rol_por_codigo', lambda codigo: {'id': 2, 'codigo': codigo})
    monkeypatch.setattr(db, 'obtener_permisos_por_codigos',
                        lambda codigos: [{'id': 1, 'codigo': 'docentes.leer'}, {'id': 2, 'codigo': 'estudiantes.leer'}])
    guardado = {}
    monkeypatch.setattr(db, 'reemplazar_permisos_de_rol',
                        lambda rol_id, ids: guardado.update(rol_id=rol_id, ids=ids))
    monkeypatch.setattr(db, 'obtener_codigos_permisos_de_rol', lambda rol_id: ['docentes.leer', 'estudiantes.leer'])

    resultado = permisos.asignar_permisos_a_rol('admin', {'permisos': ['docentes.leer', 'estudiantes.leer']})

    assert guardado['ids'] == [1, 2]
    assert resultado['permisos'] == ['docentes.leer', 'estudiantes.leer']


def test_asignar_permisos_rol_inexistente(monkeypatch):
    monkeypatch.setattr(db, 'obtener_rol_por_codigo', lambda codigo: {})

    with pytest.raises(ValueError) as excepcion:
        permisos.asignar_permisos_a_rol('fantasma', {'permisos': []})

    assert excepcion.value.args[1] == 404
    assert _codigos(excepcion) == ['rol.not.found']


def test_asignar_permisos_codigo_inexistente(monkeypatch):
    monkeypatch.setattr(db, 'obtener_rol_por_codigo', lambda codigo: {'id': 2, 'codigo': codigo})
    monkeypatch.setattr(db, 'obtener_permisos_por_codigos', lambda codigos: [])

    with pytest.raises(ValueError) as excepcion:
        permisos.asignar_permisos_a_rol('admin', {'permisos': ['recurso.inexistente']})

    assert excepcion.value.args[1] == 404
    assert _codigos(excepcion) == ['permiso.not.found']


# ---------------------------------------------------------------
# permisos: cache de roles (cache-aside con invalidación al escribir)
# ---------------------------------------------------------------

def test_listar_roles_usa_cache(monkeypatch):
    monkeypatch.setattr(cache, 'obtener', lambda clave: [{'codigo': 'admin', 'permisos': ['docentes.leer']}])

    assert permisos.listar_roles() == [{'codigo': 'admin', 'permisos': ['docentes.leer']}]


def test_codigos_permisos_de_rol_usa_cache(monkeypatch):
    monkeypatch.setattr(cache, 'obtener', lambda clave: ['docentes.leer', 'estudiantes.leer'])

    assert permisos.codigos_permisos_de_rol('admin') == ['docentes.leer', 'estudiantes.leer']


def test_asignar_permisos_invalida_cache(monkeypatch):
    monkeypatch.setattr(db, 'obtener_rol_por_codigo', lambda codigo: {'id': 2, 'codigo': codigo})
    monkeypatch.setattr(db, 'obtener_permisos_por_codigos', lambda codigos: [{'id': 1, 'codigo': 'docentes.leer'}])
    monkeypatch.setattr(db, 'reemplazar_permisos_de_rol', lambda rol_id, ids: None)
    monkeypatch.setattr(db, 'obtener_codigos_permisos_de_rol', lambda rol_id: ['docentes.leer'])
    invalidadas = []
    monkeypatch.setattr(cache, 'invalidar', lambda *claves: invalidadas.extend(claves))

    permisos.asignar_permisos_a_rol('admin', {'permisos': ['docentes.leer']})

    assert 'roles:lista' in invalidadas and 'roles:permisos:admin' in invalidadas
