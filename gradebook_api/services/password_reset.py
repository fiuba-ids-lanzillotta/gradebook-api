"""
Recuperación de contraseña (flujo público, sin autenticación).

`solicitar`: si el email existe (docente o estudiante), emite un token opaco de
un solo uso (Redis, TTL) y envía el link por email. **Siempre** responde el mismo
mensaje, exista o no el email (evita enumerar padrones/emails de la cátedra).

`confirmar`: valida el token (existe, no expiró, no usado), lo consume y actualiza
el password (bcrypt).
"""
import secrets

from ..config import FRONTEND_URL, PASSWORD_RESET_TTL_SEGUNDOS
from ..constants import (
    TIPO_DOCENTE,
    TIPO_ESTUDIANTE,
    ERROR_CODE_TOKEN_RESET_INVALIDO,
    MENSAJE_RESET_SOLICITADO,
)
from ..utils import construir_error_api, hashear_password
from ..validators.auth import validar_body_solicitar_reset, validar_body_confirmar_reset
from .. import db, reset_tokens, mailer


def solicitar_recuperacion(body: dict) -> dict:
    """Emite el token y manda el email si el email existe. Respuesta uniforme."""
    datos   = validar_body_solicitar_reset(body)
    persona = _buscar_persona_por_email(datos['email'])

    if persona:
        token = secrets.token_urlsafe(32)

        if reset_tokens.guardar_token(token, persona['tipo'], persona['id'], PASSWORD_RESET_TTL_SEGUNDOS):
            enlace = f'{FRONTEND_URL}/admin/cambiar-contrasena?token={token}'
            mailer.enviar_email_recuperacion(datos['email'], enlace)

    return {'mensaje': MENSAJE_RESET_SOLICITADO}


def confirmar_recuperacion(body: dict) -> dict:
    """Consume el token (un solo uso) y actualiza el password. 400 si es inválido."""
    datos   = validar_body_confirmar_reset(body)
    persona = reset_tokens.consumir_token(datos['token'])

    if not persona:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_TOKEN_RESET_INVALIDO,
            message='Token inválido o expirado',
            description='El enlace de recuperación no es válido, ya se usó o expiró. Solicitá uno nuevo.'
        ), 400)

    password_hash = hashear_password(datos['password'])

    if persona['tipo'] == TIPO_DOCENTE:
        db.actualizar_password_docente(persona['id'], password_hash)
    else:
        db.actualizar_password_estudiante(persona['id'], password_hash)

    return {'mensaje': 'Contraseña actualizada. Ya podés iniciar sesión.'}


def _buscar_persona_por_email(email: str) -> dict:
    """Busca el email en docentes y luego en estudiantes. Retorna {tipo, id} o {}."""
    docente = db.obtener_docente_por_email(email)
    if docente:
        return {'tipo': TIPO_DOCENTE, 'id': docente['id']}

    estudiante = db.obtener_estudiante_por_email(email)
    if estudiante:
        return {'tipo': TIPO_ESTUDIANTE, 'id': estudiante['id']}

    return {}
