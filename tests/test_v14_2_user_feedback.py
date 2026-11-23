"""v14.2: 사용자 테스트(T01~T05) 피드백 반영 회귀 테스트."""

from fastapi.testclient import TestClient

from app.engineering import liquefaction_cycles
from app.main import app

client = TestClient(app)


def test_liquefaction_judgement_triggered():  # T05
    r = liquefaction_cycles(
        [
            {'cycles': 1, 'excess_pore_pressure_kpa': 20},
            {'cycles': 5, 'excess_pore_pressure_kpa': 60},
            {'cycles': 9, 'excess_pore_pressure_kpa': 100},
        ],
        100,
    )
    assert r['liquefaction_triggered'] is True
    assert r['first_ru_ge_1_cycle'] == 9
    assert r['liquefaction_judgement'].startswith('발생')
    assert [p['ru'] for p in r['points']] == [0.2, 0.6, 1.0]  # 반복횟수별 Δu/σ′0
    assert 'Δu / σ′0' in r['ru_definition']


def test_liquefaction_judgement_not_triggered():  # T05
    r = liquefaction_cycles(
        [{'cycles': 1, 'excess_pore_pressure_kpa': 10}, {'cycles': 10, 'excess_pore_pressure_kpa': 80}], 100
    )
    assert r['liquefaction_triggered'] is False
    assert r['first_ru_ge_1_cycle'] is None
    assert r['liquefaction_judgement'].startswith('미발생')


def test_studio_keeps_result_on_requested_test():  # T02: AI 응답 대기 중 탭 전환 시 다른 시험에 저장되던 문제
    js = client.get('/static/studio.js').text
    assert 'const reqTab=tab,reqSample=current' in js
    assert 'target.results[reqTab]=d' in js
    assert 'body:JSON.stringify({task:reqTab,payload})' in js


def test_graphs_have_y_axis_label():  # T01
    studio = client.get('/static/studio.js').text
    samples = client.get('/static/samples-v9.js').text
    assert "transform:'rotate(-90 20 160)'},yl)" in studio
    assert "transform:'rotate(-90 20 150)'},ylab)" in samples
    assert '다짐 최대값은 측정점 기준이며 피팅 추정값이 아닙니다.' not in studio


def test_samples_summary_and_csv_export():  # T04
    js = client.get('/static/samples-v9.js').text
    assert 'function exportCsv' in js and '시험별 핵심 결과 요약' in js
    assert "'\\ufeff'" in js  # 엑셀 한글 깨짐 방지 BOM
    assert 'samples-v9.js?v=142' in client.get('/samples').text
