"""Tests del módulo cola (publish a QStash) con requests mockeado; sin red."""
import json

import pytest

from gradebook_api import cola


class _Respuesta:
    def __init__(self, ok=True, status_code=200, text=''):
        self.ok = ok
        self.status_code = status_code
        self.text = text


def _configurar_cola(monkeypatch):
    monkeypatch.setattr(cola, 'QSTASH_URL', 'https://qstash.upstash.io')
    monkeypatch.setattr(cola, 'QSTASH_TOKEN', 'token-test')
    monkeypatch.setattr(cola, 'MAIL_WORKER_URL', 'https://mailer.test')


def test_cola_no_configurada_por_defecto():
    # conftest fija QSTASH_TOKEN/MAIL_WORKER_URL en ''
    assert cola.cola_configurada() is False
    assert cola.publicar('/emails/confirmacion', {}) is False
    assert cola.publicar_lote('/emails/qr-lote', [{}]) is False


def test_publicar_ok_envia_a_qstash(monkeypatch):
    _configurar_cola(monkeypatch)

    llamadas = []
    monkeypatch.setattr(cola.requests, 'post', lambda *a, **k: llamadas.append((a, k)) or _Respuesta())

    assert cola.publicar('/emails/confirmacion', {'asistencia_id': 7}) is True

    (args, kwargs) = llamadas[0]
    assert args[0] == 'https://qstash.upstash.io/v2/publish/https://mailer.test/emails/confirmacion'
    assert kwargs['json'] == {'asistencia_id': 7}
    assert kwargs['headers']['Authorization'] == 'Bearer token-test'


def test_publicar_rechazo_retorna_false(monkeypatch):
    _configurar_cola(monkeypatch)
    monkeypatch.setattr(cola.requests, 'post',
                        lambda *a, **k: _Respuesta(ok=False, status_code=401, text='invalid token'))

    assert cola.publicar('/emails/confirmacion', {'asistencia_id': 7}) is False


def test_publicar_error_de_red_retorna_false(monkeypatch):
    _configurar_cola(monkeypatch)

    def explota(*a, **k):
        raise ConnectionError('caida')

    monkeypatch.setattr(cola.requests, 'post', explota)

    assert cola.publicar('/emails/confirmacion', {}) is False


def test_publicar_lote_arma_batch(monkeypatch):
    _configurar_cola(monkeypatch)

    llamadas = []
    monkeypatch.setattr(cola.requests, 'post', lambda *a, **k: llamadas.append((a, k)) or _Respuesta())

    cuerpos = [{'clase_id': 5, 'asistencia_ids': [1, 2]}, {'clase_id': 5, 'asistencia_ids': [3]}]
    assert cola.publicar_lote('/emails/qr-lote', cuerpos) is True

    (args, kwargs) = llamadas[0]
    assert args[0] == 'https://qstash.upstash.io/v2/batch'

    mensajes = kwargs['json']
    assert len(mensajes) == 2
    assert mensajes[0]['url'] == 'https://mailer.test/emails/qr-lote'
    assert json.loads(mensajes[0]['body']) == cuerpos[0]
    assert mensajes[0]['headers']['Content-Type'] == 'application/json'


def test_publicar_lote_vacio_no_llama(monkeypatch):
    _configurar_cola(monkeypatch)
    monkeypatch.setattr(cola.requests, 'post', lambda *a, **k: pytest.fail('no debería llamar a QStash'))

    assert cola.publicar_lote('/emails/qr-lote', []) is False
