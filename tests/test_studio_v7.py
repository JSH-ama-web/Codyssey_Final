from fastapi.testclient import TestClient

from app.main import app


def test_studio_and_classic_pages():
    client = TestClient(app)
    for url in ('/', '/studio', '/dashboard', '/methods', '/static/studio.js', '/static/studio.css'):
        assert client.get(url).status_code == 200
    assert '어떤 시험부터 시작할까요?' in client.get('/').text


def test_studio_api_grain_shear_ucs():
    client = TestClient(app)
    tests = [
        (
            'water_batch',
            {
                'rows': [
                    {'container': 10, 'wet_container': 40, 'dry_container': 35},
                    {'container': 11, 'wet_container': 41, 'dry_container': 36},
                ]
            },
        ),
        (
            'shear',
            {
                'area_mm2': 3600,
                'rows': [
                    {'normal_load_n': 100, 'peak_shear_load_n': 70},
                    {'normal_load_n': 200, 'peak_shear_load_n': 125},
                    {'normal_load_n': 300, 'peak_shear_load_n': 185},
                ],
            },
        ),
        (
            'ucs',
            {
                'initial_diameter_mm': 50,
                'initial_height_mm': 100,
                'rows': [
                    {'shortening_mm': 0, 'load_n': 0},
                    {'shortening_mm': 1, 'load_n': 100},
                    {'shortening_mm': 2, 'load_n': 160},
                ],
            },
        ),
        (
            'liquefaction',
            {
                'initial_effective_stress_kpa': 100,
                'rows': [{'cycles': 1, 'excess_pore_pressure_kpa': 12}, {'cycles': 5, 'excess_pore_pressure_kpa': 34}],
            },
        ),
    ]
    for task, payload in tests:
        res = client.post('/api/analyze', json={'task': task, 'payload': payload})
        assert res.status_code == 200, (task, res.text)
        assert 'result' in res.json() and 'explanation' in res.json()
