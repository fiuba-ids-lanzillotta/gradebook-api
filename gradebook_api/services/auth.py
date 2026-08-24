import logging

from ..constants import (
    CARGO_A_ROL,
    ROL_ADMIN,
    ROL_USUARIO,
    TIPO_DOCENTE,
    TIPO_ESTUDIANTE,
    ERROR_CODE_CREDENCIALES,
)
from ..utils import (
    construir_error_api,
    verificar_password,
    generar_token,
    validar_recaptcha,
)
from ..validators.auth import validar_body_login
from .. import db

logger = logging.getLogger(__name__)


def rol_de_docente(cargo: str) -> str:
    """Deriva el rol RBAC del docente a partir de su cargo de cátedra."""
    return CARGO_A_ROL.get(cargo, ROL_ADMIN)


def autenticar(body: dict) -> dict:
    """
    Valida el body y autentica por email + password contra docentes y estudiantes.

    El "usuario" es el email. Retorna el token y la identidad. Lanza ValueError
    401 si las credenciales no son válidas.
    """
    datos = validar_body_login(body)

    # --- LOGS TEMPORALES DE DEBUG DEL LOGIN (quitar tras diagnosticar el 401) ---
    # No se loguea password/hash/token: sólo email, flags y booleanos.
    logger.info('[auth-debug] intento login email=%s recaptcha_token_presente=%s',
                datos['email'], bool(datos['recaptcha_token']))

    validar_recaptcha(datos['recaptcha_token'])
    logger.info('[auth-debug] recaptcha OK email=%s', datos['email'])

    docente = db.obtener_docente_por_email(datos['email'])
    logger.info('[auth-debug] docente encontrado=%s activo=%s',
                bool(docente), docente.get('activo') if docente else None)
    if docente and docente.get('activo', True):
        password_ok = verificar_password(datos['password'], docente.get('password_hash', ''))
        tiene_hash  = bool(docente.get('password_hash'))
        logger.info('[auth-debug] docente id=%s tiene_hash=%s password_ok=%s cargo/rol=%s',
                    docente.get('id'), tiene_hash, password_ok, docente.get('rol'))
        if password_ok:
            rol = rol_de_docente(docente['rol'])
            logger.info('[auth-debug] LOGIN OK como docente id=%s rol=%s', docente['id'], rol)

            return _resultado_login(docente['id'], TIPO_DOCENTE, rol, docente['email'])

    estudiante = db.obtener_estudiante_por_email(datos['email'])
    logger.info('[auth-debug] estudiante encontrado=%s activo=%s',
                bool(estudiante), estudiante.get('activo') if estudiante else None)
    if estudiante and estudiante.get('activo', True):
        password_ok = verificar_password(datos['password'], estudiante.get('password_hash', ''))
        tiene_hash  = bool(estudiante.get('password_hash'))
        logger.info('[auth-debug] estudiante id=%s tiene_hash=%s password_ok=%s',
                    estudiante.get('id'), tiene_hash, password_ok)
        if password_ok:
            logger.info('[auth-debug] LOGIN OK como estudiante id=%s', estudiante['id'])

            return _resultado_login(estudiante['id'], TIPO_ESTUDIANTE, ROL_USUARIO, estudiante['email'])

    logger.warning('[auth-debug] LOGIN 401: sin match (docente=%s / estudiante=%s) para email=%s',
                   bool(docente), bool(estudiante), datos['email'])
    raise ValueError(construir_error_api(
        code=ERROR_CODE_CREDENCIALES,
        message='Credenciales inválidas',
        description='El email o password son incorrectos'
    ), 401)


def _resultado_login(persona_id: int, tipo: str, rol: str, email: str) -> dict:
    token = generar_token(persona_id, tipo, rol, email)

    return {
        'token':   token,
        'usuario': {'id': persona_id, 'tipo': tipo, 'email': email, 'rol': rol},
    }


def identidad_actual(payload: dict) -> dict:
    """Construye la identidad (incluye permisos efectivos) a partir del payload del JWT."""
    return {
        'id':       int(payload['sub']),
        'tipo':     payload.get('tipo'),
        'email':    payload.get('email'),
        'rol':      payload.get('rol'),
        'permisos': permisos_efectivos_de_payload(payload),
    }


def permisos_efectivos_de_payload(payload: dict) -> list[str]:
    """
    Resuelve los permisos efectivos de la persona autenticada:
    permisos del rol ∪ overrides otorgados − overrides revocados.

    Los permisos del rol se leen del cache (ver services/permisos); los overrides
    (por persona) se leen de la base.
    """
    # Import perezoso para no acoplar el orden de importación de los servicios.
    from . import permisos as permisos_service
    efectivos = set(permisos_service.codigos_permisos_de_rol(payload.get('rol')))

    persona_id = int(payload['sub'])
    if payload.get('tipo') == TIPO_DOCENTE:
        overrides = db.obtener_overrides_docente(persona_id)
    elif payload.get('tipo') == TIPO_ESTUDIANTE:
        overrides = db.obtener_overrides_estudiante(persona_id)
    else:
        overrides = []

    for override in overrides:
        if override['concedido']:
            efectivos.add(override['codigo'])
        else:
            efectivos.discard(override['codigo'])

    return sorted(efectivos)


def tiene_permiso(payload: dict, codigo_permiso: str) -> bool:
    """Indica si la persona autenticada tiene el permiso dado (permisos efectivos)."""
    return codigo_permiso in permisos_efectivos_de_payload(payload)
