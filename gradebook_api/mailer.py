"""
Envío de emails (Flask-Mail / SMTP) para la recuperación de contraseña.

Env-gated: si no hay credenciales de mail (`MAIL_USERNAME`/`MAIL_PASSWORD`) o
`MAIL_SUPPRESS_SEND=true`, no se envía nada: se loguea el link (modo dev). Así el
flujo funciona en desarrollo y en tests sin depender de un SMTP real.

Fail-safe: ante cualquier error de SMTP se loguea y no se propaga, para no romper
el request ni la respuesta uniforme del endpoint.
"""
import logging

from flask import current_app
from flask_mail import Mail, Message

from .config import (
    MAIL_USERNAME,
    MAIL_PASSWORD,
    MAIL_SUPPRESS_SEND,
)

logger = logging.getLogger(__name__)


def _mail_configurado() -> bool:
    return bool(MAIL_USERNAME and MAIL_PASSWORD) and not MAIL_SUPPRESS_SEND


def enviar_email_recuperacion(destinatario: str, link: str) -> None:
    """Envía el email con el link de recuperación. Si no hay SMTP, loguea el link (dev)."""
    if not _mail_configurado():
        logger.warning(f'[password-reset] Email deshabilitado; link para {destinatario}: {link}')

        return

    try:
        mensaje = Message(
            subject='Recuperá tu contraseña',
            recipients=[destinatario],
            html=_cuerpo_html(link),
        )

        Mail(current_app).send(mensaje)
    except Exception as error:
        # Fail-safe: no rompemos el request ni la respuesta uniforme si el SMTP
        # falla. Logueamos el error (y el link, para recuperar el flujo en dev).
        logger.error(f'[password-reset] No se pudo enviar el email a {destinatario}: {error}. Link: {link}')


def _cuerpo_html(link: str) -> str:
    return f"""
    <p>Recibimos un pedido para restablecer tu contraseña.</p>
    <p><a href="{link}">Hacé clic acá para elegir una nueva contraseña</a>.</p>
    <p>El enlace vence en 30 minutos y se puede usar una sola vez. Si no fuiste vos, ignorá este mensaje.</p>
    """
