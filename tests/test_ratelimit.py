from types import SimpleNamespace

from gradebook_api import ratelimit


def _limiter_falso(allowed):
    return SimpleNamespace(limit=lambda identificador: SimpleNamespace(allowed=allowed))


def test_permitido_si_esta_deshabilitado(monkeypatch):
    monkeypatch.setattr(ratelimit, '_obtener_limiter', lambda: None)

    assert ratelimit.esta_permitido('1.2.3.4') is True


def test_permitido_bajo_limite(monkeypatch):
    monkeypatch.setattr(ratelimit, '_obtener_limiter', lambda: _limiter_falso(True))

    assert ratelimit.esta_permitido('1.2.3.4') is True


def test_bloqueado_sobre_limite(monkeypatch):
    monkeypatch.setattr(ratelimit, '_obtener_limiter', lambda: _limiter_falso(False))

    assert ratelimit.esta_permitido('1.2.3.4') is False


def test_fail_open_si_redis_falla(monkeypatch):
    def _explota(identificador):
        raise RuntimeError('redis caído')

    monkeypatch.setattr(ratelimit, '_obtener_limiter', lambda: SimpleNamespace(limit=_explota))

    assert ratelimit.esta_permitido('1.2.3.4') is True
