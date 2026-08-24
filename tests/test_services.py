"""Tests de servicios con la capa de datos (db) mockeada; no tocan Supabase."""
import pytest

from gradebook_api import db, cache, reset_tokens, mailer
from gradebook_api.services import auth, docentes, estudiantes, permisos, password_reset, cursadas


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


def test_listar_estudiantes_de_cursada_con_historico(monkeypatch):
    monkeypatch.setattr(db, 'buscar_inscripciones_de_cursada', lambda *a, **k: [
        {'recursa': True, 'estado': 'cursando', 'motivo_baja': None,
         'estudiantes': {'id': 1, 'padron': '100', 'nombre': 'Ana', 'apellido': 'Perez',
                         'email': 'a@fi.uba.ar'}},
    ])
    monkeypatch.setattr(db, 'buscar_bajas_de_estudiantes', lambda ids: [
        {'estudiante_id': 1, 'motivo_baja': 'no rindió', 'cursadas': {'anio': 2025, 'cuatrimestre': 1}},
    ])

    resultado = estudiantes.listar_estudiantes_de_cursada('2026', '2')

    assert len(resultado) == 1
    dto = resultado[0]
    assert dto['recursa'] is True and dto['estado'] == 'cursando'
    assert dto['motivos_baja'] == [{'anio': 2025, 'cuatrimestre': 1, 'motivo': 'no rindió'}]
    assert 'password_hash' not in dto


def test_listar_estudiantes_cuatrimestre_invalido():
    with pytest.raises(ValueError) as excepcion:
        estudiantes.listar_estudiantes_de_cursada('2026', '3')

    assert _codigos(excepcion) == ['invalid.cuatrimestre']


def test_listar_estudiantes_anio_faltante():
    with pytest.raises(ValueError) as excepcion:
        estudiantes.listar_estudiantes_de_cursada(None, '2')

    assert _codigos(excepcion) == ['invalid.anio.format']


def test_cambiar_estado_inscripcion_baja(monkeypatch):
    monkeypatch.setattr(db, 'obtener_cursada_vigente', lambda fecha: {'id': 9})
    monkeypatch.setattr(db, 'obtener_inscripcion', lambda cursada_id, est_id: {'id': 55})
    guardado = {}
    monkeypatch.setattr(db, 'actualizar_estado_inscripcion',
                        lambda insc_id, estado, motivo: guardado.update(insc_id=insc_id, estado=estado, motivo=motivo) or 1)

    resultado = estudiantes.cambiar_estado_inscripcion(7, {'estado': 'baja', 'motivo': 'no cumplió'})

    assert guardado == {'insc_id': 55, 'estado': 'baja', 'motivo': 'no cumplió'}
    assert resultado['estado'] == 'baja' and resultado['motivo_baja'] == 'no cumplió'


def test_cambiar_estado_inscripcion_abandono_sin_motivo(monkeypatch):
    monkeypatch.setattr(db, 'obtener_cursada_vigente', lambda fecha: {'id': 9})
    monkeypatch.setattr(db, 'obtener_inscripcion', lambda cursada_id, est_id: {'id': 55})
    guardado = {}
    monkeypatch.setattr(db, 'actualizar_estado_inscripcion',
                        lambda insc_id, estado, motivo: guardado.update(estado=estado, motivo=motivo) or 1)

    resultado = estudiantes.cambiar_estado_inscripcion(7, {'estado': 'abandono'})

    assert guardado == {'estado': 'abandono', 'motivo': None}
    assert resultado['motivo_baja'] is None


def test_cambiar_estado_baja_sin_motivo_400(monkeypatch):
    monkeypatch.setattr(db, 'obtener_cursada_vigente', lambda fecha: {'id': 9})

    with pytest.raises(ValueError) as excepcion:
        estudiantes.cambiar_estado_inscripcion(7, {'estado': 'baja'})

    assert 'required.motivo' in _codigos(excepcion)


def test_cambiar_estado_invalido_400(monkeypatch):
    monkeypatch.setattr(db, 'obtener_cursada_vigente', lambda fecha: {'id': 9})

    with pytest.raises(ValueError) as excepcion:
        estudiantes.cambiar_estado_inscripcion(7, {'estado': 'egresado'})

    assert _codigos(excepcion) == ['invalid.estado.inscripcion']


def test_cambiar_estado_sin_inscripcion_404(monkeypatch):
    monkeypatch.setattr(db, 'obtener_cursada_vigente', lambda fecha: {'id': 9})
    monkeypatch.setattr(db, 'obtener_inscripcion', lambda cursada_id, est_id: {})

    with pytest.raises(ValueError) as excepcion:
        estudiantes.cambiar_estado_inscripcion(7, {'estado': 'baja', 'motivo': 'x'})

    assert excepcion.value.args[1] == 404
    assert _codigos(excepcion) == ['inscripcion.not.found']


def test_importar_estudiantes_csv_crea_e_inscribe(monkeypatch):
    # 111 ya existe (id 5) con inscripción en otra cursada → recursa; 222 es nuevo.
    monkeypatch.setattr(db, 'obtener_cursada_vigente', lambda fecha: {'id': 9})
    monkeypatch.setattr(db, 'obtener_todos_los_estudiantes',
                        lambda: [{'id': 5, 'padron': '111', 'email': 'ya@fi.uba.ar'}])
    monkeypatch.setattr(db, 'insertar_estudiantes_bulk',
                        lambda filas: [{'id': 6, 'padron': fila['padron']} for fila in filas])
    monkeypatch.setattr(db, 'obtener_inscripciones_de_estudiantes',
                        lambda ids: [{'estudiante_id': 5, 'cursada_id': 1}])   # 111 en otra cursada
    capturado = {}
    monkeypatch.setattr(db, 'insertar_inscripciones_bulk',
                        lambda filas: capturado.setdefault('filas', filas) or filas)

    csv_texto = (
        ';Legajo;Alumno;Estado;Instancias;Email;Telefono\n'
        '1;111;ACOSTA, IAN;Pendiente;Regularidad;Email Principal: ya@fi.uba.ar;-\n'
        '2;222;PEREZ, ANA;Pendiente;Regularidad;Email Principal: ana@fi.uba.ar;-\n'
        '3;;SIN LEGAJO;Pendiente;Regularidad;Email Principal: x@fi.uba.ar;-\n'
    )

    resultado = estudiantes.importar_estudiantes_csv(csv_texto)

    assert resultado['estudiantes_creados'] == 1   # 222
    assert resultado['inscriptos'] == 2            # 111 (recursa) + 222
    assert len(resultado['errores']) == 1          # la fila sin legajo
    recursa_por_est = {f['estudiante_id']: f['recursa'] for f in capturado['filas']}
    assert recursa_por_est == {5: True, 6: False}


def test_importar_estudiantes_csv_sin_cursada_vigente(monkeypatch):
    monkeypatch.setattr(db, 'obtener_cursada_vigente', lambda fecha: {})

    csv_texto = (
        ';Legajo;Alumno;Estado;Instancias;Email;Telefono\n'
        '2;222;PEREZ, ANA;Pendiente;Regularidad;Email Principal: ana@fi.uba.ar;-\n'
    )

    with pytest.raises(ValueError) as excepcion:
        estudiantes.importar_estudiantes_csv(csv_texto)

    assert excepcion.value.args[1] == 409
    assert _codigos(excepcion) == ['cursada.vigente.not.found']


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


def test_crear_estudiante_inscribe_en_cursada_vigente(monkeypatch):
    monkeypatch.setattr(db, 'obtener_estudiante_por_padron', lambda padron: {})
    monkeypatch.setattr(db, 'obtener_estudiante_por_email', lambda email: {})
    monkeypatch.setattr(db, 'obtener_cursada_vigente', lambda fecha: {'id': 9})
    monkeypatch.setattr(db, 'insertar_estudiante', lambda *args: 7)
    inscripcion = {}
    monkeypatch.setattr(db, 'insertar_inscripcion',
                        lambda cursada_id, estudiante_id, recursa, estado:
                        inscripcion.update(cursada_id=cursada_id, estudiante_id=estudiante_id,
                                           recursa=recursa, estado=estado) or 1)
    monkeypatch.setattr(db, 'obtener_estudiante_por_id',
                        lambda estudiante_id: {'id': estudiante_id, 'padron': '100', 'nombre': 'A',
                                               'apellido': 'B', 'email': 'a@fi.uba.ar', 'activo': True,
                                               'created_at': None, 'updated_at': None})

    resultado = estudiantes.crear_estudiante({'padron': '100', 'nombre': 'A', 'apellido': 'B',
                                              'email': 'a@fi.uba.ar', 'password': '100'})

    assert resultado['id'] == 7
    assert inscripcion == {'cursada_id': 9, 'estudiante_id': 7, 'recursa': False, 'estado': 'cursando'}


def test_crear_estudiante_sin_cursada_vigente(monkeypatch):
    monkeypatch.setattr(db, 'obtener_estudiante_por_padron', lambda padron: {})
    monkeypatch.setattr(db, 'obtener_estudiante_por_email', lambda email: {})
    monkeypatch.setattr(db, 'obtener_cursada_vigente', lambda fecha: {})

    with pytest.raises(ValueError) as excepcion:
        estudiantes.crear_estudiante({'padron': '100', 'nombre': 'A', 'apellido': 'B',
                                      'email': 'a@fi.uba.ar', 'password': '100'})

    assert excepcion.value.args[1] == 409
    assert _codigos(excepcion) == ['cursada.vigente.not.found']


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

# ---------------------------------------------------------------
# password_reset: recuperacion de contrasena
# ---------------------------------------------------------------

def test_solicitar_reset_email_existe(monkeypatch):
    monkeypatch.setattr(db, 'obtener_docente_por_email', lambda email: {'id': 3})
    guardado = {}
    monkeypatch.setattr(reset_tokens, 'guardar_token',
                        lambda token, tipo, pid, ttl: guardado.update(tipo=tipo, id=pid, token=token) or True)
    enviados = {}
    monkeypatch.setattr(mailer, 'enviar_email_recuperacion',
                        lambda dest, link: enviados.update(dest=dest, link=link))

    resultado = password_reset.solicitar_recuperacion({'email': 'p@fi.uba.ar'})

    assert 'mensaje' in resultado
    assert guardado['tipo'] == 'docente' and guardado['id'] == 3
    assert enviados['dest'] == 'p@fi.uba.ar' and 'token=' in enviados['link']


def test_solicitar_reset_email_no_existe(monkeypatch):
    monkeypatch.setattr(db, 'obtener_docente_por_email', lambda email: {})
    monkeypatch.setattr(db, 'obtener_estudiante_por_email', lambda email: {})
    llamado = {'guardar': False, 'mail': False}
    monkeypatch.setattr(reset_tokens, 'guardar_token', lambda *a: llamado.update(guardar=True) or True)
    monkeypatch.setattr(mailer, 'enviar_email_recuperacion', lambda *a: llamado.update(mail=True))

    resultado = password_reset.solicitar_recuperacion({'email': 'nadie@fi.uba.ar'})

    assert 'mensaje' in resultado
    assert llamado == {'guardar': False, 'mail': False}


def test_confirmar_reset_ok_estudiante(monkeypatch):
    monkeypatch.setattr(reset_tokens, 'consumir_token', lambda token: {'tipo': 'estudiante', 'id': 5})
    guardado = {}
    monkeypatch.setattr(db, 'actualizar_password_estudiante',
                        lambda pid, password_hash: guardado.update(id=pid, hash=password_hash) or 1)

    resultado = password_reset.confirmar_recuperacion({'token': 'abc', 'password': 'nuevaClave1'})

    assert guardado['id'] == 5 and guardado['hash']
    assert 'mensaje' in resultado


def test_confirmar_reset_token_invalido(monkeypatch):
    monkeypatch.setattr(reset_tokens, 'consumir_token', lambda token: {})

    with pytest.raises(ValueError) as excepcion:
        password_reset.confirmar_recuperacion({'token': 'malo', 'password': 'x'})

    assert excepcion.value.args[1] == 400
    assert _codigos(excepcion) == ['reset.token.invalido']

# ---------------------------------------------------------------
# busqueda por q (OR sobre el estudiante)
# ---------------------------------------------------------------

def test_cadena_or_busqueda_numerica():
    assert db._cadena_or_busqueda('116530') == 'padron.ilike.*116530*,email.ilike.*116530*'


def test_cadena_or_busqueda_alfabetica():
    assert db._cadena_or_busqueda('ian') == 'nombre.ilike.*ian*,apellido.ilike.*ian*,email.ilike.*ian*'


def test_listar_estudiantes_pasa_q_a_db(monkeypatch):
    capturado = {}

    def fake(anio, cuatri, nombre, apellido, padron, email, q):
        capturado['q'] = q
        return [{'recursa': False, 'estado': 'cursando', 'motivo_baja': None,
                 'estudiantes': {'id': 1, 'padron': '100', 'nombre': 'Ana', 'apellido': 'Perez',
                                 'email': 'a@fi.uba.ar'}}]

    monkeypatch.setattr(db, 'buscar_inscripciones_de_cursada', fake)
    monkeypatch.setattr(db, 'buscar_bajas_de_estudiantes', lambda ids: [])

    resultado = estudiantes.listar_estudiantes_de_cursada('2026', '2', q='ana')

    assert capturado['q'] == 'ana'
    assert len(resultado) == 1

# ---------------------------------------------------------------
# cursadas: listado de cursos con filtros
# ---------------------------------------------------------------

def test_listar_cursadas_ok(monkeypatch):
    capturado = {}

    def fake(codigo, anio, cuatrimestre):
        capturado.update(codigo=codigo, anio=anio, cuatrimestre=cuatrimestre)
        return [{'anio': 2026, 'cuatrimestre': 2, 'fecha_inicio': '2026-08-01', 'fecha_fin': '2026-12-15',
                 'materias': {'codigo': 'TB022', 'nombre': 'Introducción al Desarrollo de Software'}}]

    monkeypatch.setattr(db, 'buscar_cursadas', fake)

    resultado = cursadas.listar_cursadas(codigo='TB', anio='2026', cuatrimestre='2')

    assert capturado == {'codigo': 'TB', 'anio': 2026, 'cuatrimestre': 2}
    dto = resultado[0]
    assert dto['codigo'] == 'TB022' and dto['nombre'] == 'Introducción al Desarrollo de Software'
    assert dto['anio'] == 2026 and dto['cuatrimestre'] == 2
    assert dto['fecha_inicio'] == '2026-08-01' and dto['fecha_fin'] == '2026-12-15'
    assert isinstance(dto['vigente'], bool)


def test_curso_vigente_segun_fecha():
    fila = {'anio': 2026, 'cuatrimestre': 2, 'fecha_inicio': '2026-08-01', 'fecha_fin': '2026-12-15',
            'materias': {'codigo': 'TB022', 'nombre': 'X'}}

    assert cursadas._construir_curso_dto(fila, '2026-09-01')['vigente'] is True
    assert cursadas._construir_curso_dto(fila, '2027-01-01')['vigente'] is False
    assert cursadas._construir_curso_dto(fila, '2026-08-01')['vigente'] is True   # borde inicio
    assert cursadas._construir_curso_dto(fila, '2026-12-15')['vigente'] is True   # borde fin


def test_listar_cursadas_sin_filtros(monkeypatch):
    capturado = {}
    monkeypatch.setattr(db, 'buscar_cursadas',
                        lambda codigo, anio, cuatrimestre: capturado.update(
                            codigo=codigo, anio=anio, cuatrimestre=cuatrimestre) or [])

    cursadas.listar_cursadas()

    assert capturado == {'codigo': None, 'anio': None, 'cuatrimestre': None}


def test_listar_cursadas_cuatrimestre_invalido():
    with pytest.raises(ValueError) as excepcion:
        cursadas.listar_cursadas(cuatrimestre='3')

    assert _codigos(excepcion) == ['invalid.cuatrimestre']


def test_listar_cursadas_anio_invalido():
    with pytest.raises(ValueError) as excepcion:
        cursadas.listar_cursadas(anio='dosmil')

    assert _codigos(excepcion) == ['invalid.anio.format']


# ---------------------------------------------------------------
# cache: cursos y estudiantes
# ---------------------------------------------------------------

def test_listar_cursadas_usa_cache(monkeypatch):
    monkeypatch.setattr(cache, 'obtener', lambda clave: [
        {'anio': 2026, 'cuatrimestre': 2, 'fecha_inicio': '2026-08-01', 'fecha_fin': '2026-12-15',
         'materias': {'codigo': 'TB022', 'nombre': 'X'}}])
    monkeypatch.setattr(cache, 'guardar', lambda *a, **k: None)

    def no_pegar_db(*a, **k):
        raise AssertionError('con cache hit no debería consultar la db')

    monkeypatch.setattr(db, 'buscar_cursadas', no_pegar_db)

    resultado = cursadas.listar_cursadas()

    assert resultado[0]['codigo'] == 'TB022' and 'vigente' in resultado[0]


def test_listar_estudiantes_usa_cache(monkeypatch):
    def fake_obtener(clave):
        if clave == 'estudiantes:version':
            return 1
        return [{'id': 1, 'padron': '100'}]

    monkeypatch.setattr(cache, 'obtener', fake_obtener)

    def no_pegar_db(*a, **k):
        raise AssertionError('con cache hit no debería consultar la db')

    monkeypatch.setattr(db, 'buscar_inscripciones_de_cursada', no_pegar_db)

    assert estudiantes.listar_estudiantes_de_cursada('2026', '2') == [{'id': 1, 'padron': '100'}]


def test_invalidar_cache_estudiantes_incrementa_version(monkeypatch):
    guardado = {}
    monkeypatch.setattr(cache, 'obtener', lambda clave: 3)
    monkeypatch.setattr(cache, 'guardar', lambda clave, valor, ttl: guardado.update(clave=clave, valor=valor))

    estudiantes._invalidar_cache_estudiantes()

    assert guardado == {'clave': 'estudiantes:version', 'valor': 4}
