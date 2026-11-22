from fastapi.testclient import TestClient
from app.main import app

def test_sample_dashboard_and_home_navigation():
 c=TestClient(app)
 home=c.get('/').text
 assert 'id="demo"' in home
 assert 'id="dots"' in home
 assert 'href="/samples"' in home
 assert 'href="/methods"' in home
 assert 'href="/dashboard"' in home
 assert 'href="/" class="brand"' in home
 assert 'sampleList' in c.get('/samples').text
 assert '서버 기록 불러오기' in c.get('/samples').text
 assert 'href="/"' in c.get('/methods').text
 assert 'href="/"' in c.get('/dashboard').text
