from datetime import date  # noqa: F401  (disponible para constantes de dominio con fechas)
import os 

# URL base de la API
BASE_URL = '/gradebook_api'

# ---------------------------------------------------------------
# Roles y permisos (RBAC)
# ---------------------------------------------------------------

# Códigos de rol de seguridad (viajan en el JWT y se usan en roles_permisos)
ROL_SUPER_ADMIN = 'super_admin'   # docente a cargo de la materia
ROL_ADMIN       = 'admin'         # ayudantes y colaboradores
ROL_USUARIO     = 'usuario'       # estudiantes

ROLES = (ROL_SUPER_ADMIN, ROL_ADMIN, ROL_USUARIO)

# Cargos de cátedra válidos para los docentes
CARGOS_DOCENTE = ('Profesor', 'Ayudante', 'Colaborador')

# Cuatrimestres válidos de una cursada
CUATRIMESTRES = (1, 2)

# Estados posibles de una inscripción a una cursada
ESTADOS_INSCRIPCION       = ('cursando', 'abandono', 'baja')
ESTADO_INSCRIPCION_DEFAULT = 'cursando'

# Paginación (query params _offset / _limit)
MIN_OFFSET     = 0
MIN_LIMIT      = 1
DEFAULT_OFFSET = '0'
DEFAULT_LIMIT  = '10'

# El rol RBAC del docente se DERIVA de su cargo (no se guarda en la base).
CARGO_A_ROL = {
    'Profesor':    ROL_SUPER_ADMIN,
    'Ayudante':    ROL_ADMIN,
    'Colaborador': ROL_ADMIN,
}

# Tipos de sujeto autenticable (viaja en el JWT como `tipo`)
TIPO_DOCENTE    = 'docente'
TIPO_ESTUDIANTE = 'estudiante'

# El rol RBAC del estudiante es siempre 'usuario'.
ROL_ESTUDIANTE = ROL_USUARIO

# Catálogo de permisos (código = recurso.accion). Fuente de verdad del seed en
# db/init_db.sql; acá se listan para referenciarlos sin literales sueltos.
PERMISO_DOCENTES_LEER         = 'docentes.leer'
PERMISO_DOCENTES_GESTIONAR    = 'docentes.gestionar'
PERMISO_ESTUDIANTES_LEER      = 'estudiantes.leer'
PERMISO_ESTUDIANTES_GESTIONAR = 'estudiantes.gestionar'
PERMISO_CURSADAS_LEER         = 'cursadas.leer'
PERMISO_ROLES_GESTIONAR       = 'roles.gestionar'
PERMISO_PERMISOS_ASIGNAR      = 'permisos.asignar'

# ---------------------------------------------------------------
# Longitudes de campos
# ---------------------------------------------------------------

MAXIMO_NOMBRE      = 100
MAXIMO_APELLIDO    = 100
MAXIMO_PADRON      = 20

# Formato de fecha ISO (YYYY-MM-DD) usado internamente y en el JSON de la API
FECHA_ISO_FORMATO = '%Y-%m-%d'

# ---------------------------------------------------------------
# Códigos de error
# ---------------------------------------------------------------

ERROR_CODE_INVALID_BODY        = 'invalid.body'
ERROR_CODE_INVALID_MIN_VALUE   = 'invalid.min.value'
ERROR_CODE_INVALID_MAX_VALUE   = 'invalid.max.value'
ERROR_CODE_INVALID_EMAIL       = 'invalid.email.format'
ERROR_CODE_INVALID_BOOL        = 'invalid.bool'
ERROR_CODE_INVALID_CARGO       = 'invalid.cargo.docente'
ERROR_CODE_CREDENCIALES        = 'invalid.credentials'
ERROR_CODE_API_KEY_INVALIDA    = 'api.key.invalid'
ERROR_CODE_RATE_LIMIT          = 'rate.limit.exceeded'
ERROR_CODE_TOKEN_FALTANTE      = 'auth.token.missing'
ERROR_CODE_TOKEN_INVALIDO      = 'auth.token.invalid'
ERROR_CODE_TOKEN_EXPIRADO      = 'auth.token.expired'
ERROR_CODE_SIN_PERMISO         = 'auth.forbidden'
ERROR_CODE_DOCENTE_NOT_FOUND   = 'docente.not.found'
ERROR_CODE_ESTUDIANTE_NOT_FOUND = 'estudiante.not.found'
ERROR_CODE_EMAIL_DUPLICADO     = 'email.duplicated'
ERROR_CODE_PADRON_DUPLICADO    = 'padron.duplicated'
ERROR_CODE_ROL_NOT_FOUND       = 'rol.not.found'
ERROR_CODE_PERMISO_NOT_FOUND   = 'permiso.not.found'
ERROR_CODE_ARCHIVO_FALTANTE    = 'file.missing'
ERROR_CODE_CSV_INVALIDO        = 'invalid.csv'
ERROR_CODE_INVALID_CUATRIMESTRE = 'invalid.cuatrimestre'
ERROR_CODE_CURSADA_VIGENTE_NOT_FOUND = 'cursada.vigente.not.found'
ERROR_CODE_INVALID_ESTADO_INSCRIPCION = 'invalid.estado.inscripcion'
ERROR_CODE_INSCRIPCION_NOT_FOUND = 'inscripcion.not.found'
ERROR_CODE_TOKEN_RESET_INVALIDO = 'reset.token.invalido'

# Mensaje uniforme del pedido de recuperación (no revela si el email existe)
MENSAJE_RESET_SOLICITADO = 'Si el email está registrado, te enviamos un enlace para restablecer la contraseña.'

RECAPTCHA_SECRET = os.getenv('RECAPTCHA_SECRET', '')
RECAPTCHA_DISABLED = os.getenv('RECAPTCHA_DISABLED', 'false').lower() == 'true'
RECAPTCHA_VERIFY_URL = 'https://www.google.com/recaptcha/api/siteverify'

ERROR_CODE_RECAPTCHA_FALTANTE = 'recaptcha.missing'
ERROR_CODE_RECAPTCHA_INVALIDO = 'recaptcha.invalid'