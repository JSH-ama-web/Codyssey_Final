"""Transparent tool-routing agent and small local retrieval knowledge base."""
import os
from .engineering import grain_analysis, compaction, consolidation, water_content, direct_shear, unconfined_compression, liquid_limit, plastic_limit, liquefaction_cycles, water_batch, compaction_raw, sieve_retained, paired_compaction, limits_workflow

KNOWLEDGE=[
 ('USCS','USCS는 No.200 통과율 50%를 기준으로 조립토와 세립토를 나누며, 조립토는 No.4 기준으로 자갈과 모래를 구분한다. 조립토의 세립분 함량 5% 미만, 5~12%, 12% 초과에 따라 단일/이중 기호를 검토한다.'),
 ('입도계수','균등계수 Cu=D60/D10, 곡률계수 Cc=D30²/(D10×D60)이다. GW는 Cu≥4 및 1≤Cc≤3, SW는 Cu≥6 및 1≤Cc≤3이다.'),
 ('소성도','소성지수 PI=LL−PL, A선은 PI=0.73(LL−20)이다. LL 50 경계는 L/H 구분에 사용한다. 경계·유기질 여부는 추가 검토한다.'),
 ('다짐','건조밀도=습윤밀도/(1+w/100). 최대건조밀도와 최적함수비는 다짐 에너지와 시험 조건에 의존한다. 측정 최대값과 곡선 피팅 추정치를 구별한다.'),
 ('압밀','압밀 시험에서 누적 침하량과 초기 높이로 축변형률을 계산한다. 초기 간극비가 있으면 e=e0−(ΔH/H0)(1+e0)이다. Cc와 Cv는 추가 자료 및 해석이 필요하다.'),
 ('직접전단','수직응력과 파괴 시 최대 전단응력의 선형회귀로 점착력 c와 내부마찰각 phi를 산정한다. 초기 면적 사용, 배수조건, 면적 보정의 한계를 명시한다.'),
 ('일축압축','일축압축강도 qu는 축응력-축변형률 곡선의 최대값이다. 포화 점성토 비배수 조건일 때만 su≈qu/2를 참고한다.'),
 ('액성한계','Casagrande 다점법은 함수비와 타격횟수 로그의 유동곡선을 통해 25회에 대응하는 함수비를 액성한계 LL로 계산한다.'),
 ('소성한계','소성한계 PL은 소성 상태와 반고체 상태의 경계 함수비이며 반복 시험 함수비를 평균한다. PI=LL−PL이다.'),
 ('액상화','반복하중 시험의 과잉간극수압비 ru=Δu/초기 유효구속응력. ru가 1에 접근하면 초기 유효응력 소실에 가까워질 수 있지만 현장 액상화 위험도 및 CRR을 의미하지 않는다.'),
 ('주의','투수성·압축성·전단강도는 USCS 분류만으로 확정할 수 없다. 밀도, 구조, 포화도, 응력상태 및 별도 시험 결과를 함께 확인해야 한다.')]

def retrieve(question, n=3):
    words=set(question.lower().replace('/',' ').split())
    scored=[]
    for title,body in KNOWLEDGE:
        hay=(title+' '+body).lower()
        score=sum(2 if w in title.lower() else 1 for w in words if len(w)>1 and w in hay)
        scored.append((score,title,body))
    scored.sort(reverse=True)
    return [{'source':title,'text':body} for _,title,body in scored[:n]]

def route(task, payload):
    if task=='paired_compaction': return paired_compaction(payload['rows'],payload['mold_volume_cm3'])
    if task=='limits_workflow': return limits_workflow(payload['dry_cans'],payload['wet_cans'],payload['liquid_rows'],payload['plastic_rows'])
    if task=='sieve_raw': return sieve_retained(payload['rows'],payload['total_dry_mass_g'])
    if task=='compaction_raw': return compaction_raw(payload['rows'],payload['mold_volume_cm3'])
    if task=='water_batch': return water_batch(payload['rows'])
    if task=='grain': return grain_analysis(payload['rows'],payload.get('ll'),payload.get('pl'),payload.get('nonplastic',False))
    if task=='compaction': return compaction(payload['rows'])
    if task=='consolidation': return consolidation(payload['rows'],payload['initial_height_mm'],payload.get('initial_void_ratio'))
    if task=='water': return {'water_content_pct':water_content(payload['wet_container'],payload['dry_container'],payload['container'])}
    if task=='shear': return direct_shear(payload['rows'],payload['area_mm2'])
    if task=='ucs': return unconfined_compression(payload['rows'],payload['initial_diameter_mm'],payload['initial_height_mm'])
    if task=='liquid': return liquid_limit(payload['rows'])
    if task=='plastic': return plastic_limit(payload['rows'])
    if task=='liquefaction': return liquefaction_cycles(payload['rows'],payload['initial_effective_stress_kpa'])
    raise ValueError('지원하지 않는 분석 작업입니다.')

async def explain(task, result, question):
    import json
    docs=retrieve(question+' '+task)
    # Korean-only fallback: never dump JSON as a user-facing interpretation.
    names={'grain':'입도분석','sieve_raw':'체 잔류질량 분석','compaction':'다짐시험','compaction_raw':'다짐 원자료','paired_compaction':'2캔 평균 다짐시험','water':'함수비','water_batch':'함수비 반복측정','liquid':'액성한계','plastic':'소성한계','limits_workflow':'액성·소성한계 통합','shear':'직접전단','ucs':'일축압축','consolidation':'압밀','liquefaction':'액상화 반복하중'}
    metrics={'uscs':'USCS 예비 분류','liquid_limit_pct':'액성한계','plastic_limit_pct':'소성한계','plasticity_index_pct':'소성지수','measured_max_dry_density':'측정 최대 건조밀도','measured_optimum_water_pct':'최대 건조밀도에 해당하는 함수비','average_water_content_pct':'평균 함수비','water_content_pct':'함수비','cohesion_kpa':'점착력','friction_angle_deg':'내부마찰각','qu_kpa':'일축압축강도','max_ru':'최대 과잉간극수압비','fines_pct':'세립분 비율'}
    units={'liquid_limit_pct':'%','plastic_limit_pct':'%','plasticity_index_pct':'%','measured_max_dry_density':'g/cm³','measured_optimum_water_pct':'%','average_water_content_pct':'%','water_content_pct':'%','cohesion_kpa':'kPa','friction_angle_deg':'°','qu_kpa':'kPa','fines_pct':'%'}
    found=[f"{label}: {result[k]} {units.get(k,'')}" for k,label in metrics.items() if result.get(k) is not None]
    details='\n'.join('• '+x for x in found) if found else '측정점의 그래프와 계산 표를 확인하세요.'
    issues='\n'.join('• '+str(x) for x in result.get('warnings',[])) or '자동 경고는 없습니다. 원자료와 시험조건의 별도 확인은 필요합니다.'
    fallback=(f"[시험] {names.get(task,'토질시험')}\n\n[계산 결과]\n{details}\n\n"
              f"[데이터 품질 및 주의]\n{issues}\n\n"
              '[공학적 의미]\n시험에서 직접 산정한 값은 토질의 일부 특성을 보여줍니다. 다짐·압밀·전단·함수비 시험값은 각각 시험조건에 종속되므로 다른 현장 조건에 그대로 적용할 수 없습니다.\n\n'
              '[시공 전 검토]\n성토·기초·사면·배수 설계 전 지층 연속성, 지하수위, 밀도, 다짐 상태, 응력 이력, 강도·압축성 시험을 확인해야 합니다. 현재 값만으로 지지력·침하·투수계수·안전율을 확정할 수 없습니다.\n\n'
              '[해석 한계]\n'+result.get('note','시험 규격과 계측 조건을 확인하세요.')+'\n\n'
              '[관련 근거]\n'+'\n'.join('• '+x['source']+': '+x['text'] for x in docs))
    from . import llm
    if not llm.is_configured(): return {'mode':'rules+local-rag','answer':fallback,'sources':docs}
    system=('당신은 토질공학 교육용 해설 Agent다. 계산 결과를 변경하거나 숫자를 지어내지 마라. 한국어로 관찰 결과, 가능한 지반 거동, 시공시 확인 사항, 보완 시험, 해석 한계를 구분해 설명하라. '
            '보고서 초안은 작성하지 마라. 투수성·압축성·지지력·침하·안전율을 시험 없이 확정하지 마라. 출처가 없으면 추측하지 마라.')
    user=json.dumps({'task':task,'result':result,'question':question,'retrieved':docs},ensure_ascii=False)
    try:
        answer=await llm.complete(system,user,temperature=0.1)
        return {'mode':'codyssey-ai+local-rag','answer':answer or fallback,'sources':docs}
    except llm.LLMError as exc:
        return {'mode':'rules+local-rag-fallback','answer':fallback,'sources':docs,'warning':f'AI API 요청에 실패하여 검증 가능한 로컬 해설로 전환했습니다. ({exc})'}
