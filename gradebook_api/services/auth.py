import hmac

from ..config import (
    ADMIN_USER,
    ADMIN_PASSWORD,
)
from ..constants import (
    ROL_ADMIN,
    ERROR_CODE_CREDENCIALES,
)
from ..utils import (
    construir_error_api,
    verificar_password,
    generar_token,
)
from ..validators.auth import validar_body_login


def autenticar_admin(body: dict) -> dict:
    """
    Valida el body y verifica las credenciales contra las variables de entorno
    (ADMIN_USER y ADMIN_PASSWORD, este último un hash bcrypt). Retorna el token
    y la identidad del admin.
    """
    datos = validar_body_login(body)

    usuario_ok  = hmac.compare_digest(datos['usuario'], ADMIN_USER)
    password_ok = verificar_password(datos['password'], ADMIN_PASSWORD)

    if not (usuario_ok and password_ok):
        raise ValueError(construir_error_api(
            code=ERROR_CODE_CREDENCIALES,
            message='Credenciales inválidas',
            description='El usuario o password son incorrectos'
        ), 401)

    token = generar_token(subject=ADMIN_USER, rol=ROL_ADMIN)

    return {
        'token':   token,
        'usuario': {'usuario': ADMIN_USER, 'rol': ROL_ADMIN},
    }


def identidad_actual(payload: dict) -> dict:
    """Construye la identidad del admin a partir del payload del JWT."""
    return {'usuario': payload.get('sub'), 'rol': payload.get('rol')}
