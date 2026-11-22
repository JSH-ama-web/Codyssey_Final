import pytest
from app.agent import route

def test_water_batch():
    out=route('water_batch',{'rows':[{'container':20,'wet_container':70,'dry_container':60},{'container':10,'wet_container':50,'dry_container':42}]})
    assert out['points'][0]['water_content_pct']==25
    assert out['average_water_content_pct']==pytest.approx((25+25)/2)

def test_compaction_raw():
    rows=[]
    for mass,wet,dry in [(1900,65,60),(2000,70,60),(1980,75,60)]:
        rows.append({'mold_mass_g':4000,'mold_soil_mass_g':4000+mass,'container':20,'wet_container':wet,'dry_container':dry})
    out=route('compaction_raw',{'mold_volume_cm3':1000,'rows':rows})
    assert len(out['points'])==3
    assert out['measured_max_dry_density']>0

def test_bad_mass():
    with pytest.raises(ValueError):route('water_batch',{'rows':[{'container':20,'wet_container':30,'dry_container':20}]})
