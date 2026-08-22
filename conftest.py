"""
Config compartida de pytest.

Fija credenciales dummy de Supabase antes de importar la app, para que el
cliente se pueda construir sin depender del entorno real. Los tests cubren
funciones puras (validaciones, servicios con la db mockeada) y no hacen
llamadas de red.
"""
import os

os.environ.setdefault('SUPABASE_URL', 'http://localhost:54321')
os.environ.setdefault('SUPABASE_KEY', 'test-key')

# Deshabilitar Upstash Redis en los tests (cache y rate limiting fail-open), para
# no depender de un .env con credenciales reales. Se fija explícitamente (no
# setdefault) para que `load_dotenv` de config.py no lo sobrescriba con el .env.
os.environ['UPSTASH_REDIS_REST_URL'] = ''
os.environ['UPSTASH_REDIS_REST_TOKEN'] = ''

# Deshabilitar reCAPTCHA en los tests (el login no debe pegarle a Google).
os.environ['RECAPTCHA_DISABLED'] = 'true'
