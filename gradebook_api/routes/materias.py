from flask import Blueprint, jsonify

from ..constants import PERMISO_CURSADAS_LEER
from ..utils import requiere_permiso
from ..services.materias import listar_materias

materias_bp = Blueprint('materias', __name__)


@materias_bp.route('/materias', methods=['GET'])
@requiere_permiso(PERMISO_CURSADAS_LEER)
def get_materias():
    """Catálogo de materias (código + nombre). Requiere cursadas.leer."""
    return jsonify(listar_materias())
