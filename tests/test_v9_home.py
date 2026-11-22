from fastapi.testclient import TestClient

from app.main import app


def test_new_navigation_and_assets():
    c = TestClient(app)
    for url in (
        '/',
        '/studio',
        '/samples',
        '/methods',
        '/dashboard',
        '/static/home-v9.js',
        '/static/samples-v9.js',
        '/static/icon-limits_workflow.svg',
    ):
        assert c.get(url).status_code == 200
    home = c.get('/').text
    assert '가상 예제 채우기' in home
    assert '시험 방법' in home and '기록 대시보드' in home and '시료 목록' in home
    assert 'href="/studio?test=paired_compaction"' in home
    assert '시료별 통합 분석' in c.get('/samples').text
    assert '14.1.0' == c.get('/api/health').json()['version']
