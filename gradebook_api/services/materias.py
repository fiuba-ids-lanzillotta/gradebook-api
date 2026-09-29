"""Materias: catálogo de lectura."""
from .. import db


def listar_materias() -> list[dict]:
    """Catálogo completo de materias ordenadas por código."""
    return db.listar_materias()
