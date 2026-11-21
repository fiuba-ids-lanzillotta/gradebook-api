"""Evaluaciones de una cursada."""
from ..constants import (
    ACCION_EVALUACION_CREAR,
    ACCION_EVALUACION_GRUPOS,
    ERROR_CODE_CURSADA_NOT_FOUND,
    ERROR_CODE_EVALUACION_NO_GRUPAL,
    ERROR_CODE_EVALUACION_NOT_FOUND,
    ERROR_CODE_GRUPOS_OCUPADA,
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
PESO_MAXIMO = 10
CANTIDAD_MAXIMA_INSTANCIAS = 20


def habilitar_crear_grupos(evaluacion_id: int, habilitado) -> dict:
    """
    Abre o cierra la creación de equipos por los alumnos en una evaluación grupal.
    Solo una evaluación por cursada puede tenerla habilitada (índice parcial en la
    base + chequeo acá para devolver el error con nombre).
    """
    evaluacion = _evaluacion_o_404(evaluacion_id)
    habilitado = validar_booleano(habilitado, 'habilitado')

    if evaluacion.get('modalidad') != MODALIDAD_GRUPAL:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_EVALUACION_NO_GRUPAL,
            message='La evaluación no es grupal',
            description='Solo las evaluaciones de modalidad grupal pueden habilitar la creación de equipos.',
        ), 400)

    if habilitado:
        activa = db.buscar_evaluacion_con_creacion_grupos(evaluacion['cursada_id'])

        if activa and activa['id'] != evaluacion['id']:
            raise ValueError(construir_error_api(
                code=ERROR_CODE_GRUPOS_OCUPADA,
                message='Ya hay una evaluación con creación de equipos abierta',
                description=f'La creación de equipos está habilitada en "{activa.get("nombre")}". Cerrala ahí primero.',
            ), 409)

    fila = db.actualizar_evaluacion(evaluacion['id'], {'permite_crear_grupos': habilitado})
    registro.registrar(
        ACCION_EVALUACION_GRUPOS,
        f'{"Habilitó" if habilitado else "Deshabilitó"} la creación de equipos en la evaluación "{evaluacion.get("nombre")}"',
        detalle={'evaluacion_id': evaluacion['id'], 'habilitado': habilitado},
        cursada_id=evaluacion.get('cursada_id'),
    )

    return _dto(fila or evaluacion)


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
