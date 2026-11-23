import pytest
from fastapi.testclient import TestClient

from app.engineering import limits_workflow, paired_compaction
from app.main import app


def can(c, w, d):
    return {'container': c, 'wet_container': w, 'dry_container': d}


def paired_rows():
    return [
        {
            'mold_mass_g': 4256,
            'mold_soil_mass_g': 5800 + i * 50,
            'can1': can(10, 40 + i, 35),
            'can2': can(11, 41 + i, 36),
        }
        for i in range(5)
    ]


def test_paired_calculation():
    result = paired_compaction(paired_rows(), 1000)
    assert len(result['paired_details']) == 5
    assert result['paired_details'][0]['can_numbers'] == [1, 2]
    assert result['paired_details'][0]['can_water_pct'] == [20.0, 20.0]
    assert result['paired_details'][0]['average_water_pct'] == 20.0
    assert result['paired_details'][0]['wet_density'] == 1.544
    assert result['paired_details'][0]['dry_density'] == pytest.approx(1.544 / 1.2, abs=0.00001)


def test_reject_bad_can():
    rows = paired_rows()
    rows[0]['can2']['dry_container'] = 8
    with pytest.raises(ValueError):
        paired_compaction(rows, 1000)


def test_limits_groups_not_ll():
    li = [{'blows': n, **can(10, 30 + (40 - n) / 10, 25)} for n in [34, 29, 24, 19]]
    out = limits_workflow([can(10, 30, 26)] * 2, [can(10, 32, 26)] * 2, li, [can(10, 30, 27)] * 2)
    assert out['initial_dry_group']['average_pct'] == 25
    assert out['initial_wet_group']['average_pct'] == 37.5
    assert out['liquid_limit_pct'] > 0
    assert out['plasticity_index_pct'] == pytest.approx(out['liquid_limit_pct'] - out['plastic_limit_pct'], abs=0.001)


def test_api_and_pages():
    client = TestClient(app)
    assert client.get('/lab').status_code == 404
    assert client.get('/dashboard').status_code == 200
    assert client.get('/api/health').json()['version'] == '14.2.0'
    r = client.post(
        '/api/analyze', json={'task': 'paired_compaction', 'payload': {'rows': paired_rows(), 'mold_volume_cm3': 1000}}
    )
    assert r.status_code == 200, r.text
    assert '분석 결과: {' not in r.json()['explanation']['answer']
    assert '측정 최대 건조밀도' in r.json()['explanation']['answer']
