"""Tests de servicios con la capa de datos (db) mockeada; no tocan Supabase."""
import pytest

from gradebook_api import db, cache
from gradebook_api.services import items


def _codigos(excepcion):
    return [error['code'] for error in excepcion.value.args[0]['errors']]


# ---------------------------------------------------------------
# items.listar_items (usa cache)
# ---------------------------------------------------------------

def test_listar_items_usa_cache(monkeypatch):
    # Si el cache tiene valor, no debe tocar la base.
    monkeypatch.setattr(cache, 'obtener', lambda clave: [
        {'id': 1, 'nombre': 'cacheado', 'descripcion': None, 'activo': True},
    ])

    assert items.listar_items() == [
        {'id': 1, 'nombre': 'cacheado', 'descripcion': None, 'activo': True},
    ]


# ---------------------------------------------------------------
# items.crear_item
# ---------------------------------------------------------------

def test_crear_item_ok(monkeypatch):
    monkeypatch.setattr(cache, 'invalidar', lambda *claves: None)
    monkeypatch.setattr(db, 'obtener_item_por_nombre', lambda nombre: {})
    monkeypatch.setattr(db, 'insertar_item', lambda *args: 99)
    monkeypatch.setattr(db, 'obtener_item_por_id',
                        lambda item_id: {'id': item_id, 'nombre': 'X', 'descripcion': None, 'activo': True})

    resultado = items.crear_item({'nombre': 'X'})

    assert resultado['id'] == 99 and resultado['activo'] is True


def test_crear_item_nombre_duplicado(monkeypatch):
    monkeypatch.setattr(db, 'obtener_item_por_nombre', lambda nombre: {'id': 2, 'nombre': nombre})

    with pytest.raises(ValueError) as excepcion:
        items.crear_item({'nombre': 'X'})

    assert _codigos(excepcion) == ['nombre.duplicated']
    assert excepcion.value.args[1] == 409


# ---------------------------------------------------------------
# items.actualizar_item
# ---------------------------------------------------------------

def test_actualizar_item_invalida_cache(monkeypatch):
    invalidadas = []
    monkeypatch.setattr(cache, 'invalidar', lambda *claves: invalidadas.extend(claves))
    monkeypatch.setattr(db, 'obtener_item_por_id',
                        lambda item_id: {'id': item_id, 'nombre': 'X', 'descripcion': None, 'activo': True})
    monkeypatch.setattr(db, 'obtener_item_por_nombre', lambda nombre: {})
    monkeypatch.setattr(db, 'actualizar_item', lambda *args: 1)

    items.actualizar_item(1, {'nombre': 'Y'})

    assert 'items:filas' in invalidadas


def test_actualizar_item_404(monkeypatch):
    monkeypatch.setattr(db, 'obtener_item_por_id', lambda item_id: {})

    with pytest.raises(ValueError) as excepcion:
        items.actualizar_item(999, {'nombre': 'X'})

    assert excepcion.value.args[1] == 404


# ---------------------------------------------------------------
# items.eliminar_item_por_id
# ---------------------------------------------------------------

def test_eliminar_item_404(monkeypatch):
    monkeypatch.setattr(db, 'obtener_item_por_id', lambda item_id: {})

    with pytest.raises(ValueError) as excepcion:
        items.eliminar_item_por_id(999)

    assert excepcion.value.args[1] == 404
