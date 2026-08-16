"""
Configuración de la aplicación leída del entorno (variables de deploy).

Se separa de `constants.py` (que sólo tiene constantes de dominio) porque estos
valores dependen del entorno y algunos son sensibles (credenciales, secretos).
"""
import os

from dotenv import load_dotenv

load_dotenv()

# Credenciales del panel de administración (único usuario, vía variables de entorno).
# ADMIN_PASSWORD es un hash bcrypt del password (no el password en texto plano).
ADMIN_USER     = os.getenv('ADMIN_USER', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '')

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
CACHE_TTL_ITEMS_SEGUNDOS = int(os.getenv('CACHE_TTL_ITEMS', '300'))
