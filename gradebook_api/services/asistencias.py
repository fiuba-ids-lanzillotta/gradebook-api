"""
Asistencia por QR.

Flujo (ver también la guía de frontend): el docente **dispara** la toma de una
fecha (`crear_clase`) → se genera un `codigo` corto por estudiante inscripto y
activo y se persisten las asistencias en 'pendiente'. Luego los QRs se **envían**
por email en lotes (`enviar_qrs`, empujado por el polling del front; reanudable e
idempotente). El docente **marca** presente escaneando el QR, tipeando el código
o por padrón (`marcar_asistencia`). Se puede **cerrar** la clase (`cerrar_clase`):
los 'pendiente' pasan a 'ausente'.
"""
import io
import logging
import secrets

import qrcode

from ..config import ASISTENCIA_LOTE_EMAILS, ASISTENCIA_MAX_INTENTOS_ENVIO
from ..constants import (
    ASISTENCIA_CODIGO_ALFABETO,
    ASISTENCIA_CODIGO_LARGO,
    ESTADO_CLASE_ABIERTA,
    ESTADO_CLASE_CERRADA,
    ESTADO_ASISTENCIA_PENDIENTE,
    ESTADO_ASISTENCIA_PRESENTE,
    METODO_ASISTENCIA_QR,
    METODO_ASISTENCIA_MANUAL,
    METODO_ASISTENCIA_PADRON,
    ERROR_CODE_CURSADA_NOT_FOUND,
    ERROR_CODE_CLASE_NOT_FOUND,
    ERROR_CODE_CLASE_FECHA_INVALIDA,
    ERROR_CODE_CLASE_CERRADA,
    ERROR_CODE_ASISTENCIA_NOT_FOUND,
)
from ..utils import construir_error_api
from ..validators.asistencias import validar_body_clase, validar_body_marcar
from .. import db, cache, mailer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------
# Disparar la toma: crear la clase + generar los códigos
# ---------------------------------------------------------------

def crear_clase(cursada_id: int, body: dict) -> dict:
    """
    Dispara la toma de asistencia de una fecha: crea (o reusa) la clase y genera
    un código por cada estudiante inscripto y activo que aún no tenga asistencia
    en esa clase. Idempotente: reintentar no duplica clase ni códigos.

    Lanza 404 (cursada inexistente) o 400 (fecha fuera del período de la cursada).
    """
    datos   = validar_body_clase(body)
    cursada = _obtener_cursada_o_404(cursada_id)
    _validar_fecha_en_cursada(datos['fecha'], cursada)

    clase = db.obtener_clase_por_fecha(cursada_id, datos['fecha'])
    if not clase:
        clase = db.insertar_clase(cursada_id, datos['fecha'], datos['titulo'])

    inscriptos   = db.obtener_inscriptos_activos_de_cursada(cursada_id)
    ya_generados = set(db.obtener_estudiante_ids_de_clase(clase['id']))
    faltantes    = [estudiante_id for estudiante_id in inscriptos if estudiante_id not in ya_generados]

    nuevas = _generar_asistencias(clase['id'], faltantes)
    if nuevas:
        db.insertar_asistencias_bulk(nuevas)

    return {
        'clase':             _clase_dto(clase),
        'total_estudiantes': len(inscriptos),
        'generados':         len(nuevas),
    }


def _generar_asistencias(clase_id: int, estudiante_ids: list[int]) -> list[dict]:
    """Arma las filas de asistencia con un código único (dentro del lote) por estudiante."""
    codigos = set()

    while len(codigos) < len(estudiante_ids):
        codigos.add(_generar_codigo())

    return [{'clase_id': clase_id, 'estudiante_id': estudiante_id, 'codigo': codigo}
            for estudiante_id, codigo in zip(estudiante_ids, codigos)]


def _generar_codigo() -> str:
    """Genera un código corto y legible (alfabeto sin caracteres ambiguos)."""
    return ''.join(secrets.choice(ASISTENCIA_CODIGO_ALFABETO) for _ in range(ASISTENCIA_CODIGO_LARGO))


# ---------------------------------------------------------------
# Envío de los QRs por email (por lotes, reanudable)
# ---------------------------------------------------------------

def enviar_qrs(clase_id: int, limite: int = None) -> dict:
    """
    Envía el próximo lote de QRs pendientes (no enviados, con < max intentos) por
    email. Reanudable e idempotente: el estado de envío vive en la base. Usa un
    lock corto en Redis para evitar envíos concurrentes de la misma clase.

    Retorna el resumen del envío (total, enviados, con_error, quedan, completo) +
    `enviados_en_lote`.
    """
    clase  = _obtener_clase_o_404(clase_id)
    limite = limite or ASISTENCIA_LOTE_EMAILS

    enviados_en_lote = 0
    lock = f'asistencia:envio:{clase_id}'

    if cache.adquirir_lock(lock, 30):
        try:
            pendientes = db.buscar_asistencias_a_enviar(clase_id, ASISTENCIA_MAX_INTENTOS_ENVIO, limite)
            enviados_en_lote = _enviar_lote(clase, pendientes)
        finally:
            cache.liberar_lock(lock)

    resumen = _resumen_envio(clase_id)
    resumen['enviados_en_lote'] = enviados_en_lote

    return resumen


def _enviar_lote(clase: dict, pendientes: list[dict]) -> int:
    """Envía cada asistencia del lote y registra el resultado. Retorna cuántas se enviaron ok."""
    enviados = 0

    for asistencia in pendientes:
        estudiante = asistencia['estudiantes']
        intentos   = asistencia['envio_intentos'] + 1

        try:
            png = _generar_qr_png(asistencia['codigo'])
            mailer.enviar_email_qr_asistencia(
                estudiante['email'],
                estudiante['nombre'],
                _clase_dto(clase),
                asistencia['codigo'],
                png,
                estudiante.get('apellido') or '',
            )
            db.registrar_envio_asistencia(asistencia['id'], True, intentos, None)
            enviados += 1
        except Exception as error:
            logger.error(f"[asistencia] Falló el envío del QR a {estudiante.get('email')}: {error}")
            db.registrar_envio_asistencia(asistencia['id'], False, intentos, str(error)[:300])

    return enviados


def _generar_qr_png(dato: str) -> bytes:
    """Genera el PNG de un QR que codifica `dato` (el código de asistencia)."""
    imagen  = qrcode.make(dato)
    buffer  = io.BytesIO()
    imagen.save(buffer, format='PNG')

    return buffer.getvalue()


def resumen_envio(clase_id: int) -> dict:
    """Retorna el estado del envío de una clase (para el polling de progreso del front)."""
    _obtener_clase_o_404(clase_id)

    return _resumen_envio(clase_id)


def _resumen_envio(clase_id: int) -> dict:
    total     = db.contar_asistencias(clase_id)
    enviados  = db.contar_asistencias(clase_id, enviado=True)
    con_error = db.contar_asistencias(clase_id, con_error=True, max_intentos=ASISTENCIA_MAX_INTENTOS_ENVIO)
    quedan    = max(total - enviados - con_error, 0)

    return {
        'clase_id':  clase_id,
        'total':     total,
        'enviados':  enviados,
        'con_error': con_error,
        'quedan':    quedan,
        'completo':  quedan == 0,
    }


# ---------------------------------------------------------------
# Marcar / listar / cerrar
# ---------------------------------------------------------------

def marcar_asistencia(clase_id: int, body: dict, docente_id: int) -> dict:
    """
    Marca 'presente' una asistencia por código (QR o tipeado) o por padrón.
    Lanza 404 (clase o asistencia inexistente) o 409 (clase cerrada).
    """
    datos = validar_body_marcar(body)
    clase = _obtener_clase_o_404(clase_id)

    if clase['estado'] == ESTADO_CLASE_CERRADA:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_CLASE_CERRADA,
            message='La clase está cerrada',
            description='No se puede marcar asistencia en una clase cerrada.'
        ), 409)

    if datos['codigo']:
        asistencia = db.obtener_asistencia_por_codigo(clase_id, datos['codigo'])
        metodo     = METODO_ASISTENCIA_MANUAL if datos['manual'] else METODO_ASISTENCIA_QR
    else:
        asistencia = db.obtener_asistencia_por_padron(clase_id, datos['padron'])
        metodo     = METODO_ASISTENCIA_PADRON

    if not asistencia:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_ASISTENCIA_NOT_FOUND,
            message='Asistencia no encontrada',
            description='No hay una asistencia en esta clase con ese código o padrón.'
        ), 404)

    db.marcar_asistencia(asistencia['id'], ESTADO_ASISTENCIA_PRESENTE, metodo, docente_id)

    estudiante = asistencia['estudiantes']

    return {
        'clase_id':      clase_id,
        'estudiante_id': estudiante['id'],
        'padron':        estudiante['padron'],
        'nombre':        estudiante['nombre'],
        'apellido':      estudiante['apellido'],
        'estado':        ESTADO_ASISTENCIA_PRESENTE,
        'metodo':        metodo,
    }


def listar_asistencias_de_clase(clase_id: int, estado: str = None, q: str = None) -> list[dict]:
    """Lista las asistencias de una clase (con datos del estudiante), ordenadas por apellido."""
    _obtener_clase_o_404(clase_id)

    filas = db.buscar_asistencias_de_clase(clase_id, estado, q)
    dtos  = [_asistencia_dto(fila) for fila in filas if fila.get('estudiantes')]

    return sorted(dtos, key=lambda a: (a['apellido'] or '', a['nombre'] or ''))


def listar_clases_de_cursada(cursada_id: int) -> list[dict]:
    """Lista las clases con toma de asistencia de una cursada (más recientes primero)."""
    _obtener_cursada_o_404(cursada_id)

    return [_clase_dto(fila) for fila in db.buscar_clases_de_cursada(cursada_id)]


def cerrar_clase(clase_id: int) -> dict:
    """Cierra la clase: los 'pendiente' pasan a 'ausente'. Retorna el resumen de asistencia."""
    _obtener_clase_o_404(clase_id)

    ausentes = db.cerrar_asistencias_pendientes(clase_id)
    db.actualizar_estado_clase(clase_id, ESTADO_CLASE_CERRADA)

    return {'clase_id': clase_id, 'estado': ESTADO_CLASE_CERRADA, 'marcados_ausentes': ausentes}


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

def _obtener_cursada_o_404(cursada_id: int) -> dict:
    cursada = db.obtener_cursada_por_id(cursada_id)

    if not cursada:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_CURSADA_NOT_FOUND,
            message='Cursada no encontrada',
            description=f"No existe una cursada con id '{cursada_id}'."
        ), 404)

    return cursada


def _obtener_clase_o_404(clase_id: int) -> dict:
    clase = db.obtener_clase_por_id(clase_id)

    if not clase:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_CLASE_NOT_FOUND,
            message='Clase no encontrada',
            description=f"No existe una clase con id '{clase_id}'."
        ), 404)

    return clase


def _validar_fecha_en_cursada(fecha: str, cursada: dict) -> None:
    """La fecha de la clase debe caer dentro de fecha_inicio..fecha_fin de la cursada (ISO comparables)."""
    if not (cursada['fecha_inicio'] <= fecha <= cursada['fecha_fin']):
        raise ValueError(construir_error_api(
            code=ERROR_CODE_CLASE_FECHA_INVALIDA,
            message='Fecha fuera del período de la cursada',
            description=f"La fecha '{fecha}' debe estar entre {cursada['fecha_inicio']} y {cursada['fecha_fin']}."
        ))


def _clase_dto(fila: dict) -> dict:
    return {
        'id':         fila['id'],
        'cursada_id': fila['cursada_id'],
        'fecha':      fila['fecha'],
        'titulo':     fila.get('titulo'),
        'estado':     fila['estado'],
        'created_at': fila.get('created_at'),
        'updated_at': fila.get('updated_at'),
    }


def _asistencia_dto(fila: dict) -> dict:
    estudiante = fila['estudiantes']

    return {
        'estudiante_id': estudiante['id'],
        'padron':        estudiante['padron'],
        'nombre':        estudiante['nombre'],
        'apellido':      estudiante['apellido'],
        'email':         estudiante['email'],
        'codigo':        fila['codigo'],
        'estado':        fila['estado'],
        'metodo':        fila.get('metodo'),
        'marcado_at':    fila.get('marcado_at'),
        'enviado':       fila.get('enviado', False),
    }
