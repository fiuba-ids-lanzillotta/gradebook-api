"""
Envío de emails (Flask-Mail / SMTP) para recuperación de contraseña y bienvenida.

Env-gated: si no hay credenciales de mail (`MAIL_USERNAME`/`MAIL_PASSWORD`) o
`MAIL_SUPPRESS_SEND=true`, no se envía nada: se loguea el link/password (modo dev). Así el
flujo funciona en desarrollo y en tests sin depender de un SMTP real.

Fail-safe: ante cualquier error de SMTP se loguea y no se propaga, para no romper
el request ni la respuesta uniforme del endpoint.
"""
import logging

from flask import current_app, render_template
from flask_mail import Mail, Message

from .config import (
    MAIL_USERNAME,
    MAIL_PASSWORD,
    MAIL_SUPPRESS_SEND,
)

logger = logging.getLogger(__name__)


def _mail_configurado() -> bool:
    return bool(MAIL_USERNAME and MAIL_PASSWORD) and not MAIL_SUPPRESS_SEND


def enviar_email_recuperacion(destinatario: str, link: str,
                              nombre: str = '', apellido: str = '') -> None:
    """Envía el email con el link de recuperación. Si no hay SMTP, loguea el link (dev)."""
    if not _mail_configurado():
        logger.warning(f'[password-reset] Email deshabilitado; link para {destinatario}: {link}')

        return

    try:
        mensaje = Message(
            subject='Recuperá tu contraseña',
            recipients=[destinatario],
            html=_cuerpo_html(link, nombre, apellido),
        )

        Mail(current_app).send(mensaje)
    except Exception as error:
        logger.error(f'[password-reset] No se pudo enviar el email a {destinatario}: {error}. Link: {link}')


def _cuerpo_html(link: str, nombre: str = '', apellido: str = '') -> str:
    saludo = f"{(apellido or '').strip()} {(nombre or '').strip()}".strip() or 'estudiante'

    return render_template(
        'emails/recuperacion.html',
        saludo=saludo,
        link=link,
    )


def enviar_email_qr_asistencia(destinatario: str, nombre: str, clase: dict,
                               codigo: str, qr_png: bytes, apellido: str = '') -> None:
    """
    Envía el email con el QR de asistencia (PNG inline) para una clase.

    A diferencia del reset, NO es fail-safe: si el SMTP falla, propaga la
    excepción para que el service la registre y reintente en el próximo lote. Si
    el mail no está configurado (dev/tests), loguea y no envía (se toma como ok).
    """
    if not _mail_configurado():
        logger.warning(f'[asistencia] Email deshabilitado; QR para {destinatario} codigo={codigo}')

        return

    mensaje = Message(
        subject='Clase presencial obligatoria Lanzillota',
        recipients=[destinatario],
        html=_cuerpo_html_qr(nombre, clase, codigo, apellido),
    )
    mensaje.attach(
        'qr-asistencia.png',
        'image/png',
        qr_png,
        disposition='inline',
        headers={'Content-ID': '<qr_asistencia>'},
    )

    Mail(current_app).send(mensaje)


def _cuerpo_html_qr(nombre: str, clase: dict, codigo: str, apellido: str = '') -> str:
    saludo = f"{(apellido or '').strip()} {(nombre or '').strip()}".strip() or 'estudiante'
    fecha = str(clase.get('fecha') or '')[:10]

    return render_template(
        'emails/asistencia_qr.html',
        saludo=saludo,
        fecha=fecha,
        codigo=codigo or '',
    )


def enviar_email_nuevo_docente(destinatario: str, nombre: str, apellido: str,
                                rol: str, password: str) -> None:
    """
    Envía el email de bienvenida a un nuevo docente con su contraseña temporal.

    Fail-safe: ante cualquier error de SMTP se loguea y no se propaga, para no romper
    el request ni la respuesta uniforme del endpoint.
    """
    if not _mail_configurado():
        logger.warning(f'[nuevo-docente] Email deshabilitado; password para {destinatario}: {password}')

        return

    try:
        mensaje = Message(
            subject='Bienvenido a Gradebook Lanzillotta',
            recipients=[destinatario],
            html=_cuerpo_html_nuevo_docente(nombre, apellido, rol, password),
        )

        Mail(current_app).send(mensaje)
    except Exception as error:
        logger.error(f'[nuevo-docente] No se pudo enviar el email a {destinatario}: {error}. Password: {password}')


def _cuerpo_html_nuevo_docente(nombre: str, apellido: str, rol: str, password: str) -> str:
    saludo = f"{(apellido or '').strip()} {(nombre or '').strip()}".strip() or 'docente'

    return render_template(
        'emails/nuevo_docente.html',
        saludo=saludo,
        rol=rol,
        password=password,
    )
