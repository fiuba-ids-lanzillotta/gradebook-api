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
CACHE_TTL_CLASES_SEGUNDOS      = int(os.getenv('CACHE_TTL_CLASES', '300'))
CACHE_TTL_ASISTENCIAS_SEGUNDOS = int(os.getenv('CACHE_TTL_ASISTENCIAS', '60'))

# URL base del frontend, para armar el link de recuperación de contraseña.
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:5001').rstrip('/')

# Recuperación de contraseña: TTL del token de un solo uso (segundos). Default 30 min.
PASSWORD_RESET_TTL_SEGUNDOS = int(os.getenv('PASSWORD_RESET_TTL', '1800'))

# Asistencia: cuántos envíos de QR se simulan por request en modo dev (sin cola)
# y cuántos intentos tiene cada asistencia antes de marcarse con error.
ASISTENCIA_LOTE_EMAILS          = int(os.getenv('ASISTENCIA_LOTE_EMAILS', '15'))
ASISTENCIA_MAX_INTENTOS_ENVIO   = int(os.getenv('ASISTENCIA_MAX_INTENTOS_ENVIO', '3'))

# Reintentos ante errores transitorios de red de Supabase al persistir datos.
ASISTENCIA_DB_MAX_REINTENTOS     = int(os.getenv('ASISTENCIA_DB_MAX_REINTENTOS', '3'))
ASISTENCIA_DB_BACKOFF_MS         = int(os.getenv('ASISTENCIA_DB_BACKOFF_MS', '100'))

# Cola de emails (Upstash QStash → gradebook-mailer, worker serverless). Si
# ambas están configuradas, los emails se encolan al worker; si no, `cola`
# loguea el mensaje que iría a la cola y `enviar_qrs` simula el envío (dev).
# QSTASH_URL es la base regional que muestra la consola de Upstash (la global es
# https://qstash.upstash.io).
QSTASH_URL      = os.getenv('QSTASH_URL', 'https://qstash.upstash.io').rstrip('/')
QSTASH_TOKEN    = os.getenv('QSTASH_TOKEN', '')
MAIL_WORKER_URL = os.getenv('MAIL_WORKER_URL', '').rstrip('/')

# Cuántos QRs lleva cada mensaje encolado a QStash (el worker los manda en una
# sola ejecución; chico para entrar en el timeout serverless) y cuánto dura la
# marca de "encolado" que evita republicar pendientes mientras QStash entrega.
ASISTENCIA_LOTE_EMAILS_WORKER      = int(os.getenv('ASISTENCIA_LOTE_EMAILS_WORKER', '5'))
ASISTENCIA_MARCA_ENCOLADO_SEGUNDOS = int(os.getenv('ASISTENCIA_MARCA_ENCOLADO_SEGUNDOS', '300'))

# Delay escalonado entre mensajes del batch de QStash (segundos): entrega de a
# un lote por vez en vez de todos en paralelo, para no saturar el SMTP (Gmail
# responde 421 ante el burst) ni dejar funciones del worker llegando al timeout.
ASISTENCIA_LOTE_DELAY_SEGUNDOS = int(os.getenv('ASISTENCIA_LOTE_DELAY_SEGUNDOS', '15'))

