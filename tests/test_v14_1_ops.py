"""v14.1: 코디세이 AI Gateway 연동·운영 로그·헬스체크 회귀 테스트."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from fastapi.testclient import TestClient

from app import llm
from app.main import app

client = TestClient(app)
WATER = {'task': 'water', 'payload': {'wet_container': 50, 'dry_container': 45, 'container': 20}}


@pytest.fixture
def gateway(monkeypatch):
    """코디세이 Gateway를 흉내 내는 로컬 서버 (anthropic 경로 on/off 가능)."""
    state = {'anthropic': True, 'seen': []}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['content-length'])))
            state['seen'].append((self.path, body['model']))
            if self.path == '/v1/messages' and state['anthropic']:
                out = {'content': [{'type': 'text', 'text': 'anthropic 해설'}]}
            elif self.path == '/v1/chat/completions':
                out = {'choices': [{'message': {'content': 'openai 해설'}}]}
            else:
                self.send_response(404)
                self.end_headers()
                return
            data = json.dumps(out, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header('content-type', 'application/json')
            self.end_headers()
            self.wfile.write(data)

    server = HTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv('AI_API_KEY', 'test-key')
    monkeypatch.setenv('AI_BASE_URL', f'http://127.0.0.1:{server.server_port}/v1')
    monkeypatch.delenv('AI_API_FORMAT', raising=False)
    monkeypatch.setattr(llm, '_resolved_format', None)
    yield state
    server.shutdown()


def test_health_reports_ai_and_runtime_without_secret(monkeypatch):
    monkeypatch.setenv('AI_API_KEY', 'secret-value')
    body = client.get('/api/health').json()
    assert body['status'] == 'ok' and body['ai_configured'] is True
    assert 'secret-value' not in json.dumps(body)
    assert {'uptime_s', 'requests', 'errors_5xx'} <= set(body['runtime'])


def test_request_id_header_on_every_response():
    assert client.get('/api/health').headers['x-request-id']


def test_codyssey_gateway_anthropic_format(gateway):
    exp = client.post('/api/analyze', json=WATER).json()['explanation']
    assert exp['mode'] == 'codyssey-ai+local-rag' and exp['answer'] == 'anthropic 해설'
    assert gateway['seen'][0] == ('/v1/messages', 'claude-haiku-4')


def test_codyssey_gateway_falls_back_to_openai_format(gateway):
    gateway['anthropic'] = False
    exp = client.post('/api/analyze', json=WATER).json()['explanation']
    assert exp['answer'] == 'openai 해설'
    assert [p for p, _ in gateway['seen']] == ['/v1/messages', '/v1/chat/completions']


def test_no_key_uses_local_explanation(monkeypatch):
    monkeypatch.delenv('AI_API_KEY', raising=False)
    exp = client.post('/api/analyze', json=WATER).json()['explanation']
    assert exp['mode'] == 'rules+local-rag'


def test_gateway_failure_is_logged_and_falls_back(monkeypatch, caplog):
    monkeypatch.setenv('AI_API_KEY', 'k')
    monkeypatch.setenv('AI_BASE_URL', 'http://127.0.0.1:9')
    monkeypatch.setenv('AI_TIMEOUT', '2')
    exp = client.post('/api/analyze', json=WATER).json()['explanation']
    assert exp['mode'] == 'rules+local-rag-fallback' and 'warning' in exp
