from fastapi.testclient import TestClient
from app.main import app

def test_dashboard_v6_assets():
    c=TestClient(app)
    for path in ("/dashboard", "/static/dashboard.js", "/static/v6.css", "/api/health"):
        r=c.get(path)
        assert r.status_code==200, (path,r.status_code)
    html=c.get("/dashboard").text
    for phrase in ("시험 유형별 분석 현황", "최근 7일 시험 기록", "저장된 시험 기록", "detailPlot"):
        assert phrase in html
