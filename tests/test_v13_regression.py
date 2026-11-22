from fastapi.testclient import TestClient

from app.main import app


def test_home_and_legacy_removed():
    c = TestClient(app)
    assert '어떤 시험부터 시작할까요?' in c.get('/').text
    assert c.get('/lab').status_code == 404
    assert c.get('/classic').status_code == 404
    for route in ['/studio', '/dashboard', '/methods', '/samples']:
        html = c.get(route).text
        assert 'href="/"' in html
        assert '2캔 원자료 실험실' not in html
    assert 'deleteSample' in c.get('/samples').text
    assert 'deleteCurrentSample' in c.get('/studio').text
    assert 'classification' in c.get('/samples').text


def test_classification_requires_limits_for_fines():
    c = TestClient(app)
    points = [
        {'diameter_mm': 19, 'passing_pct': 100},
        {'diameter_mm': 4.75, 'passing_pct': 96},
        {'diameter_mm': 2, 'passing_pct': 90},
        {'diameter_mm': 0.425, 'passing_pct': 65},
        {'diameter_mm': 0.075, 'passing_pct': 20},
        {'diameter_mm': 0.02, 'passing_pct': 5},
    ]
    missing = c.post('/api/classify', json={'points': points})
    assert missing.status_code == 200
    assert missing.json()['uscs'] == '미확정'
    full = c.post('/api/classify', json={'points': points, 'll': 45, 'pl': 20})
    assert full.status_code == 200
    assert full.json()['uscs'] in ('SC', 'SM', 'SM-SC')
