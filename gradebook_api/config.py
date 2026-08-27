"""
Configuración de la aplicación leída del entorno (variables de deploy).

Se separa de `constants.py` (que sólo tiene constantes de dominio) porque estos
valores dependen del entorno y algunos son sensibles (credenciales, secretos).
"""
import os

from dotenv import load_dotenv

load_dotenv()

# Configuración JWT
JWT_SECRET           = os.getenv('JWT_SECRET', 'change-me-please')
JWT_ALGORITHM        = 'HS256'
JWT_EXPIRACION_HORAS = int(os.getenv('JWT_EXPIRACION_HORAS', '8'))

# Configuración de Supabase. El backend usa la key service_role (no se expone
# al frontend). En local, ambos valores los imprime `supabase start`.
SUPABASE_URL = os.getenv('SUPABASE_URL', '')
SUPABASE_KEY = os.getenv('SUPABASE_KEY', '')

# Orígenes permitidos para CORS (lista separada por comas). Default '*' (todos);
# en producción conviene restringirlo al dominio del frontend.
CORS_ORIGINS = [origen.strip() for origen in os.getenv('CORS_ORIGINS', '*').split(',') if origen.strip()]

# API key para restringir el consumo al frontend. Si está vacía, la verificación
# queda deshabilitada (la API es pública). Si tiene valor, todas las requests
# deben enviar el header X-API-Key con ese valor.
API_KEY = os.getenv('API_KEY', '')

# Upstash Redis (REST): backend compartido para rate limiting y cache. Si no hay
# credenciales, ambos quedan deshabilitados (fail-open).
UPSTASH_REDIS_REST_URL   = os.getenv('UPSTASH_REDIS_REST_URL', '')
UPSTASH_REDIS_REST_TOKEN = os.getenv('UPSTASH_REDIS_REST_TOKEN', '')

# Rate limiting: límite por IP (RATE_LIMIT_MAX requests por RATE_LIMIT_WINDOW seg).
RATE_LIMIT_MAXIMO           = int(os.getenv('RATE_LIMIT_MAX', '100'))
RATE_LIMIT_VENTANA_SEGUNDOS = int(os.getenv('RATE_LIMIT_WINDOW', '60'))

# Cache en Redis (cache-aside con invalidación explícita en cada escritura). El
# TTL es una red de seguridad por si se pierde una invalidación; uno por recurso.
CACHE_TTL_ROLES_SEGUNDOS       = int(os.getenv('CACHE_TTL_ROLES', '300'))
CACHE_TTL_CURSADAS_SEGUNDOS    = int(os.getenv('CACHE_TTL_CURSADAS', '300'))
CACHE_TTL_ESTUDIANTES_SEGUNDOS = int(os.getenv('CACHE_TTL_ESTUDIANTES', '60'))
CACHE_TTL_DOCENTES_SEGUNDOS    = int(os.getenv('CACHE_TTL_DOCENTES', '300'))
CACHE_TTL_PERMISOS_SEGUNDOS    = int(os.getenv('CACHE_TTL_PERMISOS', '600'))

# URL base del frontend, para armar el link de recuperación de contraseña.
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5001').rstrip('/')

# Recuperación de contraseña: TTL del token de un solo uso (segundos). Default 30 min.
PASSWORD_RESET_TTL_SEGUNDOS = int(os.getenv('PASSWORD_RESET_TTL', '1800'))

# Asistencia: el envío de QRs se hace por lotes (empujado por el polling del
# front, para no exceder el timeout serverless). Cuántos emails por request y
# cuántos reintentos por email antes de marcarlo con error.
ASISTENCIA_LOTE_EMAILS          = int(os.getenv('ASISTENCIA_LOTE_EMAILS', '15'))
ASISTENCIA_MAX_INTENTOS_ENVIO   = int(os.getenv('ASISTENCIA_MAX_INTENTOS_ENVIO', '3'))

# Email (Flask-Mail). Si MAIL_USERNAME/MAIL_PASSWORD están vacíos o
# MAIL_SUPPRESS_SEND=true, no se envía: se loguea el link (modo dev).
MAIL_SERVER         = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
MAIL_PORT           = int(os.getenv('MAIL_PORT', '587'))
MAIL_USE_TLS        = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
MAIL_USE_SSL        = os.getenv('MAIL_USE_SSL', 'false').lower() == 'true'
MAIL_USERNAME       = os.getenv('MAIL_USERNAME', '')
MAIL_PASSWORD       = os.getenv('MAIL_PASSWORD', '')
# Si MAIL_DEFAULT_SENDER está vacío o sin definir, se usa MAIL_USERNAME (Gmail
# exige que el remitente sea la cuenta autenticada).
MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', '') or MAIL_USERNAME
MAIL_SUPPRESS_SEND  = os.getenv('MAIL_SUPPRESS_SEND', 'false').lower() == 'true'

