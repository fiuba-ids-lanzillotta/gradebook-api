"""Evaluaciones de una cursada."""
from ..constants import (
    ACCION_EVALUACION_CREAR,
    ACCION_EVALUACION_GRUPOS,
    ACCION_EVALUACION_VISIBILIDAD,
    ERROR_CODE_CURSADA_NOT_FOUND,
    ERROR_CODE_EVALUACION_NO_GRUPAL,
    ERROR_CODE_EVALUACION_NOT_FOUND,
    ERROR_CODE_INVALID_BODY,
)
from ..utils import (
    construir_error_api,
    validar_booleano,
    validar_entero,
    validar_largo_string,
    validar_minimo,
    validar_string_no_vacio,
)
from .. import db, registro

MODALIDAD_GRUPAL = 'grupal'
TIPOS = ('obligatorio', 'opcional')
CRITERIOS = ('nota', 'aprobado_desaprobado', 'entregado_no_entregado')
MODALIDADES = ('grupal', 'individual')
VISIBILIDAD_INICIAL = 'deshabilitado'
VISIBILIDADES = ('deshabilitado', 'habilitado')
PESO_MAXIMO = 10
CANTIDAD_MAXIMA_INSTANCIAS = 20


def habilitar_crear_grupos(evaluacion_id: int, habilitado) -> dict:
    """
    Abre o cierra la creación de equipos por los alumnos en una evaluación grupal.
    Solo una evaluación por cursada puede tenerla habilitada (índice parcial en
    la base): al abrir una estando otra abierta, la abierta se cierra y sus
    equipos se copian (snapshot) a la nueva; sin abierta, el origen es la última
    evaluación grupal de la cursada que tuvo equipos.
    """
    evaluacion = _evaluacion_o_404(evaluacion_id)
    habilitado = validar_booleano(habilitado, 'habilitado')

    if evaluacion.get('modalidad') != MODALIDAD_GRUPAL:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_EVALUACION_NO_GRUPAL,
            message='La evaluación no es grupal',
            description='Solo las evaluaciones de modalidad grupal pueden habilitar la creación de equipos.',
        ), 400)

    origen = None
    if habilitado:
        activa = db.buscar_evaluacion_con_creacion_grupos(evaluacion['cursada_id'])

        if activa and activa['id'] != evaluacion['id']:
            db.actualizar_evaluacion(activa['id'], {'permite_crear_grupos': False})
            origen = activa
        elif not activa:
            origen = _evaluacion_origen(evaluacion)

    fila = db.actualizar_evaluacion(evaluacion['id'], {'permite_crear_grupos': habilitado})
    transferidos = _transferir_equipos(origen, evaluacion) if origen else 0
    extra = f' (transfirió {transferidos} equipos desde "{origen.get("nombre")}")' if transferidos else ''

    registro.registrar(
        ACCION_EVALUACION_GRUPOS,
        f'{"Habilitó" if habilitado else "Deshabilitó"} la creación de equipos en la evaluación "{evaluacion.get("nombre")}"{extra}',
        detalle={'evaluacion_id': evaluacion['id'], 'habilitado': habilitado,
                 'origen_id': origen.get('id') if origen else None,
                 'equipos_transferidos': transferidos},
        cursada_id=evaluacion.get('cursada_id'),
    )

    return _dto(fila or evaluacion)


def _evaluacion_origen(evaluacion: dict) -> dict:
    """La evaluación grupal de la cursada que tuvo equipos más recientemente (sin la destino)."""
    candidatas = [
        fila for fila in db.listar_evaluaciones(evaluacion['cursada_id'])
        if fila['id'] != evaluacion['id'] and fila.get('modalidad') == MODALIDAD_GRUPAL
    ]
    con_equipos = {
        fila['evaluacion_id']
        for fila in db.listar_grupos_de_evaluaciones([fila['id'] for fila in candidatas])
    }
    elegibles = [fila for fila in candidatas if fila['id'] in con_equipos]

    return max(elegibles, key=lambda fila: fila.get('updated_at') or '', default=None)


def _transferir_equipos(origen: dict, destino: dict) -> int:
    """
    Copia a la evaluación destino los equipos del origen: mismo número, nombre,
    owner, tutor e integrantes. No copia nada si el destino ya tiene equipos.
    """
    if db.listar_grupos_de_evaluaciones([destino['id']]):
        return 0

    grupos_origen = db.listar_grupos_de_evaluaciones([origen['id']])
    miembros = db.miembros_de_grupos([grupo['id'] for grupo in grupos_origen])
    por_grupo = {}

    for fila in miembros:
        por_grupo.setdefault(fila['grupo_id'], []).append(fila['estudiante_id'])

    for grupo in grupos_origen:
        nuevo = db.insertar_grupo(destino['id'], grupo['numero'], grupo['nombre'],
                                  grupo['owner_id'], grupo.get('tutor_id'))

        for estudiante_id in por_grupo.get(grupo['id'], []):
            db.agregar_miembro(nuevo['id'], estudiante_id)

    return len(grupos_origen)


def cambiar_visibilidad(evaluacion_id: int, visibilidad) -> dict:
    """Pasa la categoría a habilitada o deshabilitada. Nace deshabilitada."""
    evaluacion = _evaluacion_o_404(evaluacion_id)
    visibilidad = _opcion(visibilidad, VISIBILIDADES, 'visibilidad')
    fila = db.actualizar_evaluacion(evaluacion['id'], {'visibilidad': visibilidad})
    conteo = db.contar_instancias([evaluacion['id']]).get(evaluacion['id'], 0)
    etiqueta = 'habilitada' if visibilidad == 'habilitado' else 'deshabilitada'

    registro.registrar(
        ACCION_EVALUACION_VISIBILIDAD,
        f'Marcó la categoría "{evaluacion.get("nombre")}" como {etiqueta}',
        detalle={'evaluacion_id': evaluacion['id'], 'visibilidad': visibilidad},
        cursada_id=evaluacion.get('cursada_id'),
    )

    return _dto_lista({**evaluacion, **(fila or {}), 'visibilidad': visibilidad}, conteo)


def listar_de_cursada(cursada_id: int) -> dict:
    """Evaluaciones de la cursada, con la cantidad de instancias de cada una."""
    cursada_id = validar_minimo(validar_entero(cursada_id, 'cursada_id'), 1, 'cursada_id')
    _cursada_o_404(cursada_id)
    filas = db.listar_evaluaciones(cursada_id)
    conteo = db.contar_instancias([fila['id'] for fila in filas])

    return {'evaluaciones': [_dto_lista(fila, conteo.get(fila['id'], 0)) for fila in filas]}


def crear(cursada_id: int, body: dict) -> dict:
    """Alta de una categoría. Arranca deshabilitada y sin creación de equipos."""
    cursada_id = validar_minimo(validar_entero(cursada_id, 'cursada_id'), 1, 'cursada_id')
    _cursada_o_404(cursada_id)
    nombre = validar_largo_string(
        validar_string_no_vacio((body or {}).get('nombre'), 'nombre').strip(), 1, 150, 'nombre',
    )
    tipo = _opcion((body or {}).get('tipo'), TIPOS, 'tipo')
    criterio = _opcion((body or {}).get('criterio'), CRITERIOS, 'criterio')
    modalidad = _opcion((body or {}).get('modalidad'), MODALIDADES, 'modalidad')
    peso = _peso((body or {}).get('peso'))
    cantidad = _cantidad_instancias((body or {}).get('instancias'))
    fila = db.insertar_evaluacion({
        'cursada_id': cursada_id,
        'nombre': nombre,
        'tipo': tipo,
        'criterio': criterio,
        'peso': peso,
        'modalidad': modalidad,
        'visibilidad': VISIBILIDAD_INICIAL,
        'requiere_corrector': _requiere_corrector((body or {}).get('requiere_corrector')),
        'permite_crear_grupos': False,
    })

    for numero in range(1, cantidad + 1):
        db.insertar_instancia(fila['id'], numero, f'Instancia {numero}', None)

    registro.registrar(
        ACCION_EVALUACION_CREAR,
        f'Creó la categoría "{nombre}"',
        detalle={'evaluacion_id': fila.get('id'), 'cursada_id': cursada_id, 'instancias': cantidad},
        cursada_id=cursada_id,
    )

    return _dto_lista(fila, cantidad)


def _cursada_o_404(cursada_id: int) -> dict:
    cursada = db.obtener_cursada_por_id(cursada_id)

    if not cursada:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_CURSADA_NOT_FOUND,
            message='Cursada no encontrada',
            description=f"No existe una cursada con id '{cursada_id}'.",
        ), 404)

    return cursada


def _opcion(valor, opciones: tuple, nombre: str) -> str:
    limpio = str(valor or '').strip()

    if limpio not in opciones:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_INVALID_BODY,
            message=f'{nombre} inválido',
            description=f'{nombre} tiene que ser uno de: {", ".join(opciones)}.',
        ), 400)

    return limpio


def _peso(valor) -> float:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        numero = None

    if numero is None or numero < 0 or numero > PESO_MAXIMO:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_INVALID_BODY,
            message='Peso inválido',
            description=f'El peso tiene que ser un número entre 0 y {PESO_MAXIMO}.',
        ), 400)

    return numero


def _cantidad_instancias(valor) -> int:
    try:
        numero = int(valor)
    except (TypeError, ValueError):
        numero = None

    if isinstance(valor, bool) or numero is None or numero < 0 or numero > CANTIDAD_MAXIMA_INSTANCIAS:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_INVALID_BODY,
            message='Cantidad de instancias inválida',
            description=f'Las instancias tienen que ser un entero entre 0 y {CANTIDAD_MAXIMA_INSTANCIAS}.',
        ), 400)

    return numero


def _requiere_corrector(valor) -> bool:
    if valor is None or valor == '':
        return True

    return validar_booleano(valor, 'requiere_corrector')


def _dto_lista(fila: dict, instancias: int) -> dict:
    return {
        'id': fila.get('id'),
        'cursada_id': fila.get('cursada_id'),
        'nombre': fila.get('nombre') or '',
        'tipo': fila.get('tipo') or '',
        'criterio': fila.get('criterio') or '',
        'peso': float(fila.get('peso') or 0),
        'modalidad': fila.get('modalidad') or '',
        'visibilidad': fila.get('visibilidad') or VISIBILIDAD_INICIAL,
        'permite_crear_grupos': bool(fila.get('permite_crear_grupos')),
        'requiere_corrector': fila.get('requiere_corrector') is not False,
        'instancias': instancias,
    }


def _evaluacion_o_404(evaluacion_id: int) -> dict:
    evaluacion_id = validar_minimo(validar_entero(evaluacion_id, 'id'), 1, 'id')
    evaluacion = db.obtener_evaluacion(evaluacion_id)

    if not evaluacion:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_EVALUACION_NOT_FOUND,
            message='Evaluación no encontrada',
            description=f"No existe una evaluación con id '{evaluacion_id}'.",
        ), 404)

    return evaluacion


def _dto(fila: dict) -> dict:
    return {
        'id': fila.get('id'),
        'cursada_id': fila.get('cursada_id'),
        'nombre': fila.get('nombre'),
        'modalidad': fila.get('modalidad'),
        'permite_crear_grupos': fila.get('permite_crear_grupos'),
    }
