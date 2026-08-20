import logging
import re
from datetime import datetime, timedelta, timezone
from functools import wraps
import requests
import bcrypt
import jwt
from flask import request, jsonify

from .config import (
    JWT_SECRET,
    JWT_ALGORITHM,
    JWT_EXPIRACION_HORAS,
)
from .constants import (
    FECHA_ISO_FORMATO,
    ERROR_CODE_INVALID_MIN_VALUE,
    ERROR_CODE_INVALID_MAX_VALUE,
    ERROR_CODE_INVALID_EMAIL,
    ERROR_CODE_INVALID_BOOL,
    ERROR_CODE_TOKEN_FALTANTE,
    ERROR_CODE_TOKEN_INVALIDO,
    ERROR_CODE_TOKEN_EXPIRADO,
    ERROR_CODE_SIN_PERMISO,
    RECAPTCHA_DISABLED, 
    RECAPTCHA_SECRET, 
    RECAPTCHA_VERIFY_URL, 
    ERROR_CODE_RECAPTCHA_FALTANTE, 
    ERROR_CODE_RECAPTCHA_INVALIDO,
)

logger = logging.getLogger(__name__)

# Expresión regular simple para validar emails
REGEX_EMAIL = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


# ---------------------------------------------------------------
# Errores
# ---------------------------------------------------------------

def construir_error_api(code: str, message: str, description: str, level: str = 'error') -> dict:
    """Construye un payload de error compatible con el resto de la API."""
    return {
        'errors': [{
            'code': code,
            'message': message,
            'level': level,
            'description': description
        }]
    }


# ---------------------------------------------------------------
# Cache HTTP (CDN)
# ---------------------------------------------------------------

def sin_cache(respuesta):
    """
    Marca la respuesta como no cacheable por el CDN. El cache lo maneja Redis
    (cache-aside con invalidación por escritura), así que evitamos que el edge
    sirva data vieja tras una modificación.
    """
    respuesta.headers['Cache-Control'] = 'no-store'

    return respuesta


# ---------------------------------------------------------------
# Validaciones genéricas
# ---------------------------------------------------------------

def validar_entero(numero, nombre: str = 'numero') -> int:
    try:
        return int(str(numero))
    except (ValueError, TypeError):
        logger.warning(f"Valor numérico inválido: '{numero}' no puede convertirse a entero")

        raise ValueError(construir_error_api(
            code=f'invalid.{nombre}.format',
            message=f"Formato de '{nombre}' inválido",
            description=f"El valor '{numero}' no puede convertirse a un número entero"
        ))


def validar_minimo(valor: int, minimo: int, nombre: str) -> int:
    if valor < minimo:
        logger.warning(f"Valor por debajo del mínimo: '{nombre}' es {valor}, mínimo esperado {minimo}")

        raise ValueError(construir_error_api(
            code=ERROR_CODE_INVALID_MIN_VALUE,
            message='Valor por debajo del mínimo permitido',
            description=f"El parámetro '{nombre}' debe ser mayor o igual a {minimo}. Se recibió: {valor}"
        ))

    return valor


def validar_maximo(valor: int, maximo: int, nombre: str) -> int:
    if valor > maximo:
        logger.warning(f"Valor por encima del máximo: '{nombre}' es {valor}, máximo esperado {maximo}")

        raise ValueError(construir_error_api(
            code=ERROR_CODE_INVALID_MAX_VALUE,
            message='Valor por encima del máximo permitido',
            description=f"El parámetro '{nombre}' debe ser menor o igual a {maximo}. Se recibió: {valor}"
        ))

    return valor


def validar_string_no_vacio(valor, nombre: str) -> str:
    if valor is None or not str(valor).strip():
        raise ValueError(construir_error_api(
            code=f'required.{nombre}',
            message=f"Campo requerido: '{nombre}'",
            description=f"El campo '{nombre}' es obligatorio y no puede estar vacío"
        ))

    return str(valor).strip()


def validar_largo_string(valor: str, minimo: int, maximo: int, nombre: str) -> str:
    if len(valor) < minimo:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_INVALID_MIN_VALUE,
            message=f"Longitud mínima no alcanzada en '{nombre}'",
            description=f"El campo '{nombre}' debe tener al menos {minimo} caracteres"
        ))

    if len(valor) > maximo:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_INVALID_MAX_VALUE,
            message=f"Longitud máxima superada en '{nombre}'",
            description=f"El campo '{nombre}' debe tener como máximo {maximo} caracteres"
        ))

    return valor


def validar_formato_email(email: str) -> str:
    if not REGEX_EMAIL.match(email):
        raise ValueError(construir_error_api(
            code=ERROR_CODE_INVALID_EMAIL,
            message="Formato de 'email' inválido",
            description=f"El valor '{email}' no es un email válido"
        ))

    return email.lower()


def validar_booleano(valor, nombre: str) -> bool:
    """Valida que el valor sea un booleano (o su representación string/int). Retorna un bool."""
    if isinstance(valor, bool):
        return valor

    normalizado = str(valor).strip().lower()

    if normalizado in ('true', '1'):
        return True

    if normalizado in ('false', '0'):
        return False

    raise ValueError(construir_error_api(
        code=ERROR_CODE_INVALID_BOOL,
        message=f"Formato de '{nombre}' inválido",
        description=f"El campo '{nombre}' debe ser un booleano (true/false)"
    ))


def validar_fecha(valor, nombre: str = 'fecha') -> str:
    """Valida que el valor sea una fecha en formato ISO (YYYY-MM-DD). Retorna el string normalizado."""
    valor = validar_string_no_vacio(valor, nombre)

    try:
        datetime.strptime(valor, FECHA_ISO_FORMATO)
    except ValueError:
        raise ValueError(construir_error_api(
            code=f'invalid.{nombre}.format',
            message=f"Formato de '{nombre}' inválido",
            description=f"El valor '{valor}' no es una fecha válida. Formato esperado: YYYY-MM-DD"
        ))

    return valor


# ---------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------

def verificar_password(password: str, password_hash: str) -> bool:
    """Compara un password en texto plano contra un hash bcrypt."""
    try:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except (ValueError, TypeError):
        return False


def hashear_password(password: str) -> str:
    """Genera el hash bcrypt de un password en texto plano."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


# ---------------------------------------------------------------
# JWT
# ---------------------------------------------------------------

def generar_token(subject, tipo: str, rol: str, email: str = None) -> str:
    """
    Genera un JWT firmado con la identidad de la persona.

    - `subject`: id de la persona (docente o estudiante).
    - `tipo`: 'docente' | 'estudiante' (para resolver overrides y permisos).
    - `rol`: rol RBAC derivado (super_admin | admin | usuario).
    """
    ahora = datetime.now(timezone.utc)
    payload = {
        'sub':   str(subject),
        'tipo':  tipo,
        'rol':   rol,
        'email': email,
        'iat':   ahora,
        'exp':   ahora + timedelta(hours=JWT_EXPIRACION_HORAS),
    }

    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decodificar_token(token: str) -> dict:
    """Decodifica un JWT y retorna su payload, o lanza ValueError con un error API."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_TOKEN_EXPIRADO,
            message='Token expirado',
            description='El token de autenticación expiró. Volvé a iniciar sesión.'
        ), 401)
    except jwt.InvalidTokenError:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_TOKEN_INVALIDO,
            message='Token inválido',
            description='El token de autenticación no es válido.'
        ), 401)


def extraer_token_del_header() -> str:
    """Extrae el token JWT del header Authorization: Bearer <token>."""
    header = request.headers.get('Authorization', '')

    if not header.startswith('Bearer '):
        raise ValueError(construir_error_api(
            code=ERROR_CODE_TOKEN_FALTANTE,
            message='Token de autenticación faltante',
            description='Debe enviarse el header Authorization con el formato "Bearer <token>"'
        ), 401)

    return header[len('Bearer '):].strip()


# ---------------------------------------------------------------
# Decorador de autenticación
# ---------------------------------------------------------------

def requiere_auth(rol: str = None):
    """
    Decorador que valida el JWT del header Authorization y, opcionalmente,
    exige un rol específico. Inyecta el payload en request.usuario_actual.
    """
    def decorador(funcion):
        @wraps(funcion)
        def wrapper(*args, **kwargs):
            try:
                token   = extraer_token_del_header()
                payload = decodificar_token(token)
            except ValueError as error:
                return jsonify(error.args[0]), error.args[1] if len(error.args) > 1 else 401

            if rol is not None and payload.get('rol') != rol:
                return jsonify(construir_error_api(
                    code=ERROR_CODE_SIN_PERMISO,
                    message='Permiso insuficiente',
                    description='No tenés permisos para realizar esta acción.'
                )), 403

            request.usuario_actual = payload

            return funcion(*args, **kwargs)

        return wrapper

    return decorador


def requiere_permiso(codigo_permiso: str):
    """
    Decorador que valida el JWT y exige que la persona tenga el permiso dado
    (según sus permisos efectivos: rol + overrides). Inyecta el payload en
    request.usuario_actual.
    """
    def decorador(funcion):
        @wraps(funcion)
        def wrapper(*args, **kwargs):
            try:
                token   = extraer_token_del_header()
                payload = decodificar_token(token)
            except ValueError as error:
                return jsonify(error.args[0]), error.args[1] if len(error.args) > 1 else 401

            # Import perezoso para evitar el ciclo utils -> services -> utils.
            from .services.auth import tiene_permiso

            if not tiene_permiso(payload, codigo_permiso):
                return jsonify(construir_error_api(
                    code=ERROR_CODE_SIN_PERMISO,
                    message='Permiso insuficiente',
                    description=f"No tenés el permiso '{codigo_permiso}' para realizar esta acción."
                )), 403

            request.usuario_actual = payload

            return funcion(*args, **kwargs)

        return wrapper

    return decorador

def validar_recaptcha(token: str) -> None:
    """
    Verifica el token contra Google. Si la verificacion falla, lanza
    ValueError con un error API listo para devolver al frontend.

    Si RECAPTCHA_DISABLED=true, se saltea la verificacion (solo para tests).
    """
    if RECAPTCHA_DISABLED:
        logger.warning('reCAPTCHA deshabilitado por configuracion (RECAPTCHA_DISABLED=true)')

        return

    if not token:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_RECAPTCHA_FALTANTE,
            message='reCAPTCHA faltante',
            description='Debe enviarse el campo "recaptcha_token" en el body con el valor del widget.'
        ), 400)

    if not RECAPTCHA_SECRET:
        logger.error('RECAPTCHA_SECRET no configurado en .env')

        raise ValueError(construir_error_api(
            code=ERROR_CODE_RECAPTCHA_INVALIDO,
            message='reCAPTCHA mal configurado en el servidor',
            description='Falta la variable RECAPTCHA_SECRET en el .env de la API.'
        ), 500)

    try:
        respuesta = requests.post(
            RECAPTCHA_VERIFY_URL,
            data={'secret': RECAPTCHA_SECRET, 'response': token},
            timeout=5,
        )
        cuerpo = respuesta.json()
        print('recaptcha:', cuerpo)
    except requests.RequestException as e:
        logger.error(f'Error contactando reCAPTCHA: {e}')

        raise ValueError(construir_error_api(
            code=ERROR_CODE_RECAPTCHA_INVALIDO,
            message='Error verificando reCAPTCHA',
            description='No se pudo contactar el servicio de verificacion de Google.'
        ), 502)

    if not cuerpo.get('success'):
        codigos = cuerpo.get('error-codes', [])

        raise ValueError(construir_error_api(
            code=ERROR_CODE_RECAPTCHA_INVALIDO,
            message='reCAPTCHA invalido',
            description=f"Google rechazo el token. error-codes: {codigos}"
        ), 400)