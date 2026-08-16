import json
from types import SimpleNamespace

from gradebook_api import cache


def test_deshabilitado_es_no_op(monkeypatch):
    monkeypatch.setattr(cache, '_obtener_cliente', lambda: None)

    assert cache.obtener('k') is None
    cache.guardar('k', {'a': 1}, 300)   # no debe lanzar
    cache.invalidar('k')                # no debe lanzar


def test_obtener_hit(monkeypatch):
    cliente_falso = SimpleNamespace(get=lambda clave: json.dumps({'a': 1}))
    monkeypatch.setattr(cache, '_obtener_cliente', lambda: cliente_falso)

    assert cache.obtener('k') == {'a': 1}


def test_obtener_miss(monkeypatch):
    cliente_falso = SimpleNamespace(get=lambda clave: None)
    monkeypatch.setattr(cache, '_obtener_cliente', lambda: cliente_falso)

    assert cache.obtener('k') is None


def test_obtener_fail_open(monkeypatch):
    def _explota(clave):
        raise RuntimeError('redis caído')

    monkeypatch.setattr(cache, '_obtener_cliente', lambda: SimpleNamespace(get=_explota))

    assert cache.obtener('k') is None


def test_guardar_serializa_con_ttl(monkeypatch):
    guardado = {}
    cliente_falso = SimpleNamespace(set=lambda clave, valor, ex=None: guardado.update(clave=clave, valor=valor, ex=ex))
    monkeypatch.setattr(cache, '_obtener_cliente', lambda: cliente_falso)

    cache.guardar('k', {'a': 1}, ttl=99)

    assert guardado['clave'].endswith('k')
    assert json.loads(guardado['valor']) == {'a': 1}
    assert guardado['ex'] == 99


def test_invalidar_borra_claves(monkeypatch):
    borradas = []
    cliente_falso = SimpleNamespace(delete=lambda *claves: borradas.extend(claves))
    monkeypatch.setattr(cache, '_obtener_cliente', lambda: cliente_falso)

    cache.invalidar('a', 'b')

    assert len(borradas) == 2
