import pytest
from fastapi.testclient import TestClient

from app.engineering import compaction, consolidation, grain_analysis, water_content
from app.main import app

SAND = [
    {'diameter_mm': 19, 'passing_pct': 100},
    {'diameter_mm': 4.75, 'passing_pct': 96},
    {'diameter_mm': 2, 'passing_pct': 88},
    {'diameter_mm': 0.425, 'passing_pct': 60},
    {'diameter_mm': 0.075, 'passing_pct': 4},
    {'diameter_mm': 0.02, 'passing_pct': 1},
]


def test_grain_mass_balance():
    r = grain_analysis(SAND, 28, 20)
    assert r['uscs'] in ('SW', 'SP')
    assert r['gravel_pct'] + r['sand_pct'] + r['fines_pct'] == pytest.approx(100)
    assert r['p200'] == 4


def test_invalid_monotonic():
    with pytest.raises(ValueError):
        grain_analysis([{'diameter_mm': 4.75, 'passing_pct': 20}, {'diameter_mm': 0.075, 'passing_pct': 30}])


def test_missing_boundaries():
    with pytest.raises(ValueError):
        grain_analysis([{'diameter_mm': 2, 'passing_pct': 70}, {'diameter_mm': 0.1, 'passing_pct': 20}])


def test_water():
    assert water_content(85, 75, 25) == 20


def test_compaction():
    r = compaction(
        [
            {'water_pct': 8, 'wet_density': 1.8},
            {'water_pct': 12, 'wet_density': 2},
            {'water_pct': 16, 'wet_density': 2.1},
        ]
    )
    assert r['measured_max_dry_density'] > 1.7


def test_consolidation():
    r = consolidation([{'stress_kpa': 25, 'settlement_mm': 0.2}, {'stress_kpa': 50, 'settlement_mm': 0.4}], 20, 0.8)
    assert r['points'][0]['void_ratio'] == pytest.approx(0.782)


def test_api_health():
    r = TestClient(app).get('/api/health')
    assert r.status_code == 200


def test_api_analyze():
    r = TestClient(app).post('/api/analyze', json={'task': 'grain', 'payload': {'rows': SAND, 'll': 28, 'pl': 20}})
    assert r.status_code == 200 and 'uscs' in r.json()['result']


def test_api_invalid():
    r = TestClient(app).post(
        '/api/analyze', json={'task': 'water', 'payload': {'wet_container': 5, 'dry_container': 7, 'container': 2}}
    )
    assert r.status_code == 422
