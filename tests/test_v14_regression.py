from fastapi.testclient import TestClient

from app.main import app


def test_navigation_and_assets():
    c = TestClient(app)
    for path in (
        '/',
        '/studio',
        '/studio?test=paired_compaction',
        '/studio?test=shear',
        '/studio?test=ucs',
        '/studio?test=consolidation',
        '/samples',
        '/methods',
        '/dashboard',
        '/static/base-v14.css',
        '/static/polish-v14.css',
    ):
        assert c.get(path).status_code == 200, path
    home = c.get('/').text
    assert 'class="test-illustration"' in home
    assert 'href="/studio?test=paired_compaction"' in home
    assert 'href="/dashboard"' in home
    assert 'href="/samples"' in home
    for path in ('/studio', '/samples', '/methods', '/dashboard'):
        html = c.get(path).text
        assert '/static/polish-v14.css' in html
        assert 'href="/"' in html
    dash = c.get('/dashboard').text
    assert '/lab#' not in dash
    assert '/studio?test=limits_workflow' in dash
    assert c.get('/api/health').json()['version'] == '14.2.0'
