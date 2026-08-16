from datetime import date  # noqa: F401  (disponible para constantes de dominio con fechas)

# URL base de la API
BASE_URL = '/gradebook_api'

# Rol del único usuario de administración (viaja dentro del JWT)
ROL_ADMIN = 'admin'

# Longitudes máximas de los campos del recurso de ejemplo (items)
MAXIMO_NOMBRE      = 100
MAXIMO_DESCRIPCION = 500

# Formato de fecha ISO (YYYY-MM-DD) usado internamente y en el JSON de la API
FECHA_ISO_FORMATO = '%Y-%m-%d'

# Códigos de error
ERROR_CODE_INVALID_BODY      = 'invalid.body'
ERROR_CODE_INVALID_MIN_VALUE = 'invalid.min.value'
ERROR_CODE_INVALID_MAX_VALUE = 'invalid.max.value'
ERROR_CODE_INVALID_EMAIL     = 'invalid.email.format'
ERROR_CODE_INVALID_BOOL      = 'invalid.bool'
ERROR_CODE_CREDENCIALES      = 'invalid.credentials'
ERROR_CODE_API_KEY_INVALIDA  = 'api.key.invalid'
ERROR_CODE_RATE_LIMIT        = 'rate.limit.exceeded'
ERROR_CODE_TOKEN_FALTANTE    = 'auth.token.missing'
ERROR_CODE_TOKEN_INVALIDO    = 'auth.token.invalid'
ERROR_CODE_TOKEN_EXPIRADO    = 'auth.token.expired'
ERROR_CODE_SIN_PERMISO       = 'auth.forbidden'
ERROR_CODE_ITEM_NOT_FOUND    = 'item.not.found'
ERROR_CODE_NOMBRE_DUPLICADO  = 'nombre.duplicated'
