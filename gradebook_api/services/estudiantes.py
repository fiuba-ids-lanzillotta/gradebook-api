import csv
import io

from ..constants import (
    ERROR_CODE_ESTUDIANTE_NOT_FOUND,
    ERROR_CODE_EMAIL_DUPLICADO,
    ERROR_CODE_PADRON_DUPLICADO,
    ERROR_CODE_CSV_INVALIDO,
)
from ..utils import construir_error_api, hashear_password
from ..validators.estudiantes import validar_body_estudiante
from .. import db


def construir_estudiante_dto(estudiante: dict) -> dict:
    """DTO público de un estudiante (nunca expone el password_hash)."""
    return {
        'id':         estudiante['id'],
        'padron':     estudiante['padron'],
        'nombre':     estudiante['nombre'],
        'apellido':   estudiante['apellido'],
        'email':      estudiante['email'],
        'activo':     estudiante.get('activo', True),
        'created_at': estudiante.get('created_at'),
        'updated_at': estudiante.get('updated_at'),
    }


def listar_estudiantes() -> list[dict]:
    """Retorna todos los estudiantes (ordenados por apellido)."""
    return [construir_estudiante_dto(estudiante) for estudiante in db.obtener_todos_los_estudiantes()]


def buscar_estudiante_por_id(estudiante_id: int) -> dict:
    """Busca un estudiante por id. Lanza ValueError 404 si no existe."""
    return construir_estudiante_dto(_obtener_estudiante_o_404(estudiante_id))


def crear_estudiante(body: dict) -> dict:
    """Valida el body, verifica padrón/email únicos, hashea el password e inserta."""
    datos = validar_body_estudiante(body, requiere_password=True)
    _validar_padron_unico(datos['padron'])
    _validar_email_unico(datos['email'])

    nuevo_id = db.insertar_estudiante(
        datos['padron'], datos['nombre'], datos['apellido'], datos['email'],
        hashear_password(datos['password'])
    )

    return buscar_estudiante_por_id(nuevo_id)


def actualizar_estudiante(estudiante_id: int, body: dict) -> dict:
    """Valida el body y actualiza un estudiante. Si viene password, lo actualiza."""
    _obtener_estudiante_o_404(estudiante_id)
    datos = validar_body_estudiante(body, requiere_password=False)
    _validar_padron_unico(datos['padron'], excluir_id=estudiante_id)
    _validar_email_unico(datos['email'], excluir_id=estudiante_id)

    db.actualizar_estudiante(
        estudiante_id, datos['padron'], datos['nombre'], datos['apellido'], datos['email']
    )

    if datos['password']:
        db.actualizar_password_estudiante(estudiante_id, hashear_password(datos['password']))

    return buscar_estudiante_por_id(estudiante_id)


def eliminar_estudiante_por_id(estudiante_id: int) -> None:
    """Elimina un estudiante por id, o lanza ValueError 404 si no existe."""
    _obtener_estudiante_o_404(estudiante_id)

    db.eliminar_estudiante(estudiante_id)


# ---------------------------------------------------------------
# Alta masiva por CSV (padrón de la cursada, export SIU)
# ---------------------------------------------------------------

def importar_estudiantes_csv(contenido: str) -> dict:
    """
    Da de alta estudiantes desde un CSV del detalle de inscripción (export SIU).

    Formato (separador `;`, con cabecera): `Legajo`, `Alumno` ("Apellido, Nombre")
    y `Email` (admite el prefijo "Email Principal: "). El password inicial de cada
    estudiante es su padrón. Omite los que ya existen (por padrón o email) y reporta
    las filas inválidas. Retorna un resumen `{creados, omitidos, errores}`.
    """
    filas, errores = _parsear_csv_estudiantes(contenido)

    if not filas and not errores:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_CSV_INVALIDO,
            message='CSV vacío o inválido',
            description="El CSV no tiene filas de estudiantes. Se espera separador ';' y cabecera con 'Legajo', 'Alumno' y 'Email'."
        ))

    existentes = db.obtener_todos_los_estudiantes()
    padrones   = {estudiante['padron'] for estudiante in existentes}
    emails     = {(estudiante['email'] or '').lower() for estudiante in existentes}

    nuevos   = []
    omitidos = []

    for fila in filas:
        clave_email = fila['email'].lower()

        if fila['padron'] in padrones:
            omitidos.append({'padron': fila['padron'], 'motivo': 'padrón ya existe'})
        elif clave_email in emails:
            omitidos.append({'padron': fila['padron'], 'motivo': 'email ya existe'})
        else:
            padrones.add(fila['padron'])
            emails.add(clave_email)
            nuevos.append({
                'padron':        fila['padron'],
                'nombre':        fila['nombre'],
                'apellido':      fila['apellido'],
                'email':         fila['email'],
                'password_hash': hashear_password(fila['padron']),
            })

    insertados = db.insertar_estudiantes_bulk(nuevos)

    return {
        'creados':  len(insertados),
        'omitidos': omitidos,
        'errores':  errores,
    }


def _limpiar_email(bruto: str) -> str:
    """Normaliza el email del export SIU (quita el prefijo 'Email Principal: ')."""
    bruto = (bruto or '').strip()
    if ':' in bruto:
        bruto = bruto.split(':', 1)[1]

    return bruto.strip()


def _parsear_csv_estudiantes(contenido: str) -> tuple[list[dict], list[dict]]:
    """
    Parsea el CSV y retorna (filas_validas, errores).

    filas_validas: [{padron, nombre, apellido, email}]. errores: [{fila, motivo}].
    """
    filas   = []
    errores = []
    lector  = csv.DictReader(io.StringIO(contenido), delimiter=';')

    for numero, registro in enumerate(lector, start=2):
        padron = (registro.get('Legajo') or '').strip()
        alumno = (registro.get('Alumno') or '').strip()
        email  = _limpiar_email(registro.get('Email') or '')

        if not padron or not alumno:
            errores.append({'fila': numero, 'motivo': 'Falta Legajo o Alumno'})
        elif ', ' not in alumno:
            errores.append({'fila': numero, 'motivo': f"Alumno sin formato 'Apellido, Nombre': {alumno}"})
        elif '@' not in email:
            errores.append({'fila': numero, 'motivo': f'Email inválido: {email}'})
        else:
            apellido, nombre = alumno.split(', ', 1)
            filas.append({
                'padron':   padron,
                'nombre':   nombre.strip(),
                'apellido': apellido.strip(),
                'email':    email,
            })

    return filas, errores


def _validar_email_unico(email: str, excluir_id: int | None = None) -> None:
    """Verifica que el email no esté usado por otro estudiante. Lanza 409 si ya está en uso."""
    otro = db.obtener_estudiante_por_email(email)

    if otro and otro['id'] != excluir_id:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_EMAIL_DUPLICADO,
            message='Email en uso',
            description=f"Ya existe un estudiante con el email '{email}'"
        ), 409)


def _validar_padron_unico(padron: str, excluir_id: int | None = None) -> None:
    """Verifica que el padrón no esté usado por otro estudiante. Lanza 409 si ya está en uso."""
    otro = db.obtener_estudiante_por_padron(padron)

    if otro and otro['id'] != excluir_id:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_PADRON_DUPLICADO,
            message='Padrón en uso',
            description=f"Ya existe un estudiante con el padrón '{padron}'"
        ), 409)


def _obtener_estudiante_o_404(estudiante_id: int) -> dict:
    """Retorna la fila del estudiante o lanza 404."""
    estudiante = db.obtener_estudiante_por_id(estudiante_id)

    if not estudiante:
        raise ValueError(construir_error_api(
            code=ERROR_CODE_ESTUDIANTE_NOT_FOUND,
            message='Estudiante no encontrado',
            description=f"No existe un estudiante con id '{estudiante_id}'"
        ), 404)

    return estudiante
