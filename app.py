import logging

# Usar el almacén de certificados del sistema operativo para verificar TLS.
# Necesario en entornos con inspección SSL corporativa (root CA propio en la
# cadena). Debe ejecutarse antes de crear el cliente de Supabase (httpx).
import truststore
truststore.inject_into_ssl()

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_mail import Mail

from gradebook_api.constants import BASE_URL, ERROR_CODE_API_KEY_INVALIDA, ERROR_CODE_RATE_LIMIT
from gradebook_api.config import (
    CORS_ORIGINS,
    API_KEY,
    MAIL_SERVER,
    MAIL_PORT,
    MAIL_USE_TLS,
    MAIL_USE_SSL,
    MAIL_USERNAME,
    MAIL_PASSWORD,
    MAIL_DEFAULT_SENDER,
    MAIL_SUPPRESS_SEND,
)
from gradebook_api.utils import construir_error_api
from gradebook_api.ratelimit import esta_permitido
from gradebook_api.routes.auth import auth_bp
from gradebook_api.routes.docentes import docentes_bp
from gradebook_api.routes.estudiantes import estudiantes_bp
from gradebook_api.routes.cursadas import cursadas_bp
from gradebook_api.routes.asistencias import asistencias_bp
from gradebook_api.routes.roles import roles_bp

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(name)s - %(message)s')

app = Flask(__name__)
app.json.sort_keys = False

# Habilitar CORS para que el frontend pueda consumir la API. Los orígenes
# permitidos se configuran con CORS_ORIGINS (default: todos).
CORS(app, origins=CORS_ORIGINS)

# Email (Flask-Mail): se usa para el mail de recuperación de contraseña. Si no
# hay credenciales, el mailer loguea el link en vez de enviar (modo dev).
app.config.update(
    MAIL_SERVER=MAIL_SERVER,
    MAIL_PORT=MAIL_PORT,
    MAIL_USE_TLS=MAIL_USE_TLS,
    MAIL_USE_SSL=MAIL_USE_SSL,
    MAIL_USERNAME=MAIL_USERNAME,
    MAIL_PASSWORD=MAIL_PASSWORD,
    MAIL_DEFAULT_SENDER=MAIL_DEFAULT_SENDER,
    MAIL_SUPPRESS_SEND=MAIL_SUPPRESS_SEND,
)
Mail(app)


@app.before_request
def validar_api_key():
    """
    Restringe el consumo al frontend: exige el header X-API-Key.

    Solo se aplica si API_KEY está configurada (si no, la API es pública). Los
    preflight CORS (OPTIONS) se dejan pasar. En caché de CDN (cache hit) este
    hook no corre, así que los GET cacheados siguen sirviéndose desde el edge.
    """
    if not API_KEY or request.method == 'OPTIONS':
        return None

    if request.headers.get('X-API-Key') != API_KEY:
        return jsonify(construir_error_api(
            code=ERROR_CODE_API_KEY_INVALIDA,
            message='API key inválida o faltante',
            description='Debe enviarse el header X-API-Key con una clave válida.'
        )), 401

    return None


@app.before_request
def aplicar_rate_limit():
    """
    Limita las solicitudes por IP (si el rate limiting está configurado).

    Env-gated y fail-open: sin credenciales de Upstash no hace nada; si Redis
    falla, deja pasar el request. Nota: con un frontend server-rendered, el
    tráfico comparte su IP, así que RATE_LIMIT_MAXIMO debe contemplar eso.
    """
    if request.method == 'OPTIONS':
        return None

    if not esta_permitido(_ip_cliente()):
        return jsonify(construir_error_api(
            code=ERROR_CODE_RATE_LIMIT,
            message='Demasiadas solicitudes',
            description='Superaste el límite de solicitudes. Probá de nuevo en unos segundos.'
        )), 429

    return None


def _ip_cliente() -> str:
    """IP del cliente. En Vercel viene en X-Forwarded-For (primer valor)."""
    reenviada = request.headers.get('X-Forwarded-For', '')

    return reenviada.split(',')[0].strip() or request.remote_addr or 'desconocido'


app.register_blueprint(auth_bp, url_prefix=BASE_URL)
app.register_blueprint(docentes_bp, url_prefix=BASE_URL)
app.register_blueprint(estudiantes_bp, url_prefix=BASE_URL)
app.register_blueprint(cursadas_bp, url_prefix=BASE_URL)
app.register_blueprint(asistencias_bp, url_prefix=BASE_URL)
app.register_blueprint(roles_bp, url_prefix=BASE_URL)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
