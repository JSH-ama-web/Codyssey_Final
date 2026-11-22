import pytest
from fastapi.testclient import TestClient

from app.engineering import direct_shear, liquid_limit, plastic_limit, unconfined_compression
from app.main import app


def test_shear_envelope():
    rows = [
        {'normal_load_n': 180, 'peak_shear_load_n': 126},
        {'normal_load_n': 360, 'peak_shear_load_n': 216},
        {'normal_load_n': 540, 'peak_shear_load_n': 306},
    ]
    r = direct_shear(rows, 3600)
    assert r['cohesion_kpa'] == pytest.approx(10)
    assert r['friction_angle_deg'] == pytest.approx(26.5651, abs=0.001)
    assert r['r_squared'] == 1


def test_shear_invalid():
    with pytest.raises(ValueError):
        direct_shear([{'normal_load_n': 1, 'peak_shear_load_n': 1}] * 2, 3600)


def test_ucs():
    rows = [{'shortening_mm': 0, 'load_n': 0}, {'shortening_mm': 2, 'load_n': 200}, {'shortening_mm': 4, 'load_n': 150}]
    r = unconfined_compression(rows, 50, 100)
    assert r['qu_kpa'] == pytest.approx(200 / (3.141592653589793 * 625 / 0.98) * 1000, abs=0.001)
    assert r['su_estimate_kpa'] == pytest.approx(r['qu_kpa'] / 2, abs=0.001)


def test_ucs_invalid():
    with pytest.raises(ValueError):
        unconfined_compression([{'shortening_mm': 100, 'load_n': 10}, {'shortening_mm': 2, 'load_n': 30}], 50, 100)


def test_liquid():
    rows = [
        {'blows': 15, 'wet_container': 36, 'dry_container': 30, 'container': 10},
        {'blows': 25, 'wet_container': 35.4, 'dry_container': 30, 'container': 10},
        {'blows': 35, 'wet_container': 35, 'dry_container': 30, 'container': 10},
    ]
    r = liquid_limit(rows)
    assert 26 < r['liquid_limit_pct'] < 28
    assert r['flow_index'] > 0


def test_liquid_invalid():
    with pytest.raises(ValueError):
        liquid_limit([{'blows': 25, 'wet_container': 30, 'dry_container': 25, 'container': 10}] * 2)


def test_plastic():
    rows = [
        {'wet_container': 25.2, 'dry_container': 23, 'container': 10},
        {'wet_container': 25.4, 'dry_container': 23.1, 'container': 10},
    ]
    r = plastic_limit(rows)
    assert 16 < r['plastic_limit_pct'] < 18


def test_new_api():
    cases = {
        'shear': {
            'area_mm2': 3600,
            'rows': [
                {'normal_load_n': 180, 'peak_shear_load_n': 126},
                {'normal_load_n': 360, 'peak_shear_load_n': 216},
            ],
        },
        'ucs': {
            'initial_diameter_mm': 50,
            'initial_height_mm': 100,
            'rows': [{'shortening_mm': 0, 'load_n': 0}, {'shortening_mm': 2, 'load_n': 200}],
        },
        'liquid': {
            'rows': [
                {'blows': 15, 'wet_container': 36, 'dry_container': 30, 'container': 10},
                {'blows': 35, 'wet_container': 35, 'dry_container': 30, 'container': 10},
            ]
        },
        'plastic': {
            'rows': [
                {'wet_container': 25.2, 'dry_container': 23, 'container': 10},
                {'wet_container': 25.4, 'dry_container': 23.1, 'container': 10},
            ]
        },
    }
    client = TestClient(app)
    for task, payload in cases.items():
        r = client.post('/api/analyze', json={'task': task, 'payload': payload})
        assert r.status_code == 200, (task, r.text)
        assert 'points' in r.json()['result']
