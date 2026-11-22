from fastapi.testclient import TestClient

from app.main import app


def test_methods_page():
    r = TestClient(app).get('/methods')
    assert r.status_code == 200
    assert '액성한계' in r.text
    assert 'No one can know the soil.' in r.text


def test_home_brand():
    r = TestClient(app).get('/')
    assert r.status_code == 200
    assert 'No one can know the soil.' in r.text
