import os
os.environ['DATABASE_PATH']=':memory:'  # overridden below to persistent temporary file
from fastapi.testclient import TestClient
from app.main import app
from app.engineering import liquefaction_cycles, direct_shear

def test_liquefaction_basic():
    r=liquefaction_cycles([{'cycles':0,'excess_pore_pressure_kpa':0},{'cycles':10,'excess_pore_pressure_kpa':100}],100)
    assert r['max_ru']==1 and r['first_ru_ge_1_cycle']==10

def test_liquefaction_rejects_duplicates():
    import pytest
    with pytest.raises(ValueError): liquefaction_cycles([{'cycles':1,'excess_pore_pressure_kpa':10},{'cycles':1,'excess_pore_pressure_kpa':20}],100)

def test_saved_record_crud(tmp_path,monkeypatch):
    import app.main as module
    monkeypatch.setattr(module,'DB',tmp_path/'records.sqlite3')
    client=TestClient(app)
    owner='a'*64; other='b'*64
    payload={'area_mm2':3600,'rows':[{'normal_load_n':180,'peak_shear_load_n':126},{'normal_load_n':360,'peak_shear_load_n':216},{'normal_load_n':540,'peak_shear_load_n':306}]}
    body={'owner_key':owner,'title':'직접전단 A','task':'shear','payload':payload,'result':direct_shear(payload['rows'],payload['area_mm2']),'explanation':{'answer':'예제'}}
    created=client.post('/api/records',json=body)
    assert created.status_code==201,created.text
    rid=created.json()['id']
    listing=client.get('/api/records',params={'owner_key':owner})
    assert listing.status_code==200 and len(listing.json()['records'])==1
    assert client.get(f'/api/records/{rid}',params={'owner_key':other}).status_code==404
    loaded=client.get(f'/api/records/{rid}',params={'owner_key':owner})
    assert loaded.json()['result']['cohesion_kpa']==10
    assert client.request('DELETE',f'/api/records/{rid}',json={'owner_key':other}).status_code==404
    assert client.request('DELETE',f'/api/records/{rid}',json={'owner_key':owner}).status_code==200
    assert client.get(f'/api/records/{rid}',params={'owner_key':owner}).status_code==404

def test_liquefaction_endpoint():
    client=TestClient(app)
    resp=client.post('/api/analyze',json={'task':'liquefaction','payload':{'initial_effective_stress_kpa':100,'rows':[{'cycles':0,'excess_pore_pressure_kpa':0},{'cycles':10,'excess_pore_pressure_kpa':90}]}})
    assert resp.status_code==200,resp.text
    assert resp.json()['result']['max_ru']==0.9


def test_reject_tampered_results(tmp_path,monkeypatch):
    import app.main as module
    monkeypatch.setattr(module,'DB',tmp_path/'records.sqlite3')
    body={'owner_key':'a'*64,'title':'잘못된 결과','task':'water','payload':{'wet_container':85,'dry_container':75,'container':25},'result':{'water_content_pct':999},'explanation':{'answer':'테스트'}}
    assert TestClient(app).post('/api/records',json=body).status_code==422
