"""Deterministic educational soil-test calculations. SI units unless specified."""

from __future__ import annotations

import math

SIEVES = [(75.0, '75 mm'), (19.0, '19 mm'), (4.75, 'No.4'), (2.0, 'No.10'), (0.425, 'No.40'), (0.075, 'No.200')]


def _number(v, name):
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ValueError(f'{name}: 숫자를 입력하세요.') from None
    if not math.isfinite(x):
        raise ValueError(f'{name}: 유한한 숫자만 허용됩니다.')
    return x


def _interpolate(points, diameter):
    """Log-diameter interpolation of passing percentage, only within measured range."""
    for d, p in points:
        if math.isclose(d, diameter, rel_tol=1e-9):
            return p
    for (d1, p1), (d2, p2) in zip(points, points[1:], strict=False):
        if d1 >= diameter >= d2:
            return p1 + (p2 - p1) * (math.log10(diameter) - math.log10(d1)) / (math.log10(d2) - math.log10(d1))
    return None


def _diameter(points, target):
    for d, p in points:
        if math.isclose(p, target, abs_tol=1e-9):
            return d
    for (d1, p1), (d2, p2) in zip(points, points[1:], strict=False):
        if p1 >= target >= p2 and p1 != p2:
            return 10 ** (math.log10(d1) + (target - p1) / (p2 - p1) * (math.log10(d2) - math.log10(d1)))
    return None


def _fine_symbol(ll, pi):
    if ll is None or pi is None:
        return None
    if ll < 0 or pi < 0 or pi > ll:
        raise ValueError('액성한계·소성지수 값이 물리적으로 타당하지 않습니다.')
    if ll < 50:
        if 4 <= pi <= 7 and pi >= 0.73 * (ll - 20):
            return 'CL-ML'
        return 'CL' if pi >= 7 and pi >= 0.73 * (ll - 20) else 'ML'
    return 'CH' if pi >= 0.73 * (ll - 20) else 'MH'


def grain_analysis(rows, ll=None, pl=None, nonplastic=False):
    if len(rows) < 2:
        raise ValueError('입도 데이터는 최소 2개 이상의 체 크기가 필요합니다.')
    points = []
    for row in rows:
        d = _number(row.get('diameter_mm'), '체 크기')
        p = _number(row.get('passing_pct'), '통과율')
        if d <= 0 or not 0 <= p <= 100:
            raise ValueError('체 크기는 양수, 통과율은 0~100%여야 합니다.')
        points.append((d, p))
    points.sort(reverse=True)
    if len({d for d, _ in points}) != len(points):
        raise ValueError('중복된 체 크기는 허용되지 않습니다.')
    if any(points[i][1] < points[i + 1][1] for i in range(len(points) - 1)):
        raise ValueError('입경이 작아질수록 통과율이 증가할 수 없습니다. 데이터를 확인하세요.')
    p4 = _interpolate(points, 4.75)
    p200 = _interpolate(points, 0.075)
    if p4 is None or p200 is None:
        raise ValueError('USCS 분류에는 No.4(4.75 mm), No.200(0.075 mm)을 포함하는 입도 범위가 필요합니다.')
    fines = p200
    gravel = 100 - p4
    sand = p4 - p200
    d10, d30, d60 = (_diameter(points, t) for t in (10, 30, 60))
    cu = d60 / d10 if d10 and d60 else None
    cc = d30 * d30 / (d10 * d60) if d10 and d30 and d60 else None
    warnings = []
    if ll is not None:
        ll = _number(ll, '액성한계')
    if pl is not None:
        pl = _number(pl, '소성한계')
    if (ll is None) != (pl is None) and not nonplastic:
        warnings.append('액성한계와 소성한계를 모두 입력해야 소성지수를 계산할 수 있습니다.')
    if ll is not None and pl is not None:
        if ll < 0 or pl < 0 or pl > ll:
            raise ValueError('액성한계는 소성한계 이상이어야 합니다.')
    pi = ll - pl if ll is not None and pl is not None and not nonplastic else None
    if nonplastic:
        pi = 0
    fine = (
        _fine_symbol(ll, pi)
        if not nonplastic
        else ('ML' if ll is not None and ll < 50 else 'MH' if ll is not None else None)
    )
    if fines >= 50:
        symbol = fine or '미확정'
        if fine is None:
            warnings.append('세립토 분류에는 액성한계와 소성한계(또는 비소성 판정)가 필요합니다.')
        warnings.append(
            '유기질토(OL/OH/PT) 여부는 별도 유기물/건조 액성한계 시험이 필요합니다. 본 앱은 무기질 가정의 예비 분류입니다.'
        )
    else:
        is_gravel = gravel >= sand
        base = 'G' if is_gravel else 'S'
        well = (cu >= 4 if is_gravel else cu >= 6) and 1 <= cc <= 3 if cu is not None and cc is not None else None
        clean = base + ('W' if well else 'P') if well is not None else None
        suffix = None
        if fine is not None:
            suffix = 'C' if fine in ('CL', 'CH') else 'M' if fine in ('ML', 'MH') else 'M-C'
        if fines < 5:
            symbol = clean or '미확정'
            if clean is None:
                warnings.append('D10/D30/D60을 산정할 입도 범위가 부족하여 W/P 판정을 할 수 없습니다.')
        elif fines <= 12:
            if clean is None or suffix is None:
                symbol = '미확정'
                warnings.append('5~12% 세립분 구간의 이중기호에는 입도계수와 소성한계 시험이 필요합니다.')
            elif suffix == 'M-C':
                symbol = clean + '-GM' if is_gravel else clean + '-SM'
                warnings.append('경계 소성 영역: 세부 이중기호는 전문가 검토가 필요합니다.')
            else:
                symbol = clean + '-' + base + suffix
        else:
            if suffix is None:
                symbol = '미확정'
                warnings.append('세립분 12% 초과 조립토에는 액성·소성한계 시험이 필요합니다.')
            elif suffix == 'M-C':
                symbol = base + 'M-' + base + 'C'
            else:
                symbol = base + suffix
    if fines == 50:
        warnings.append('No.200 통과율이 정확히 50%인 경계값입니다. 세립토 기준을 적용했습니다.')
    properties = {
        'GW': '깨끗하고 입도분포가 양호한 자갈',
        'GP': '깨끗하고 입도분포가 불량한 자갈',
        'SW': '깨끗하고 입도분포가 양호한 모래',
        'SP': '깨끗하고 입도분포가 불량한 모래',
        'GM': '실트질 자갈',
        'GC': '점토질 자갈',
        'SM': '실트질 모래',
        'SC': '점토질 모래',
        'ML': '저소성 무기질 실트(예비)',
        'CL': '저소성 무기질 점토(예비)',
        'MH': '고소성 무기질 실트(예비)',
        'CH': '고소성 무기질 점토(예비)',
        'CL-ML': '실트·점토 경계영역(예비)',
    }
    desc = properties.get(symbol, '복합/경계 분류 또는 추가 시험 필요')
    return {
        'points': [{'diameter_mm': d, 'passing_pct': p} for d, p in points],
        'p4': round(p4, 3),
        'p200': round(p200, 3),
        'gravel_pct': round(gravel, 3),
        'sand_pct': round(sand, 3),
        'fines_pct': round(fines, 3),
        'd10_mm': round(d10, 5) if d10 else None,
        'd30_mm': round(d30, 5) if d30 else None,
        'd60_mm': round(d60, 5) if d60 else None,
        'cu': round(cu, 3) if cu else None,
        'cc': round(cc, 3) if cc else None,
        'll': ll,
        'pl': pl,
        'pi': pi,
        'uscs': symbol,
        'description': desc,
        'warnings': warnings,
        'note': 'USCS 예비 판정. ASTM D2487의 전체 분류 절차 및 현장 기술자 검토를 대체하지 않습니다.',
    }


def water_content(wet_container, dry_container, container):
    wet = _number(wet_container, '습윤+용기')
    dry = _number(dry_container, '건조+용기')
    can = _number(container, '용기')
    if not wet >= dry > can >= 0:
        raise ValueError('질량은 습윤+용기 ≥ 건조+용기 > 용기 ≥ 0이어야 합니다.')
    return round(100 * (wet - dry) / (dry - can), 3)


def compaction(rows):
    if len(rows) < 3:
        raise ValueError('다짐곡선에는 최소 3개의 시험점이 필요합니다.')
    points = []
    for r in rows:
        w = _number(r.get('water_pct'), '함수비')
        wet = _number(r.get('wet_density'), '습윤밀도')
        if w < 0 or wet <= 0:
            raise ValueError('함수비는 0 이상, 습윤밀도는 양수여야 합니다.')
        points.append({'water_pct': w, 'wet_density': wet, 'dry_density': wet / (1 + w / 100)})
    points.sort(key=lambda x: x['water_pct'])
    if len({p['water_pct'] for p in points}) != len(points):
        raise ValueError('함수비 중복 시험점은 허용하지 않습니다.')
    peak = max(points, key=lambda x: x['dry_density'])
    return {
        'points': [{k: round(v, 5) for k, v in p.items()} for p in points],
        'measured_max_dry_density': round(peak['dry_density'], 5),
        'measured_optimum_water_pct': peak['water_pct'],
        'note': '시험점 중 최대값만 표시합니다. 포물선 피팅에 의한 추정 OMC/MDD가 아니며, 표준/수정 다짐 에너지 및 단위를 확인하세요.',
    }


def consolidation(rows, initial_height_mm, initial_void_ratio=None):
    h = _number(initial_height_mm, '초기 높이')
    if h <= 0:
        raise ValueError('초기 높이는 양수여야 합니다.')
    e0 = None if initial_void_ratio is None else _number(initial_void_ratio, '초기간극비')
    if e0 is not None and e0 < 0:
        raise ValueError('초기간극비는 0 이상이어야 합니다.')
    if len(rows) < 2:
        raise ValueError('압밀 데이터는 최소 2개 하중단계가 필요합니다.')
    pts = []
    for r in rows:
        stress = _number(r.get('stress_kpa'), '유효응력')
        settlement = _number(r.get('settlement_mm'), '누적 침하량')
        if stress <= 0 or not 0 <= settlement < h:
            raise ValueError('응력은 양수, 누적 침하량은 0 이상 초기 높이 미만이어야 합니다.')
        pts.append(
            {
                'stress_kpa': stress,
                'settlement_mm': settlement,
                'strain_pct': 100 * settlement / h,
                'void_ratio': e0 - (settlement / h) * (1 + e0) if e0 is not None else None,
            }
        )
    pts.sort(key=lambda x: x['stress_kpa'])
    if len({p['stress_kpa'] for p in pts}) != len(pts):
        raise ValueError('중복 응력은 허용하지 않습니다.')
    if any(pts[i]['settlement_mm'] > pts[i + 1]['settlement_mm'] for i in range(len(pts) - 1)):
        raise ValueError('단조 증가 재하 단계에서 누적 침하량이 감소했습니다. 제하 단계는 별도 분석해야 합니다.')
    return {
        'points': pts,
        'note': 'e-log σ′ 곡선용 기본 계산만 제공합니다. Cc/Cv/선행압밀압력 산정은 별도 시험 시간·재하이력 및 해석이 필요합니다.',
    }


# Additional educational modules: direct shear, unconfined compression, Atterberg limits.
def direct_shear(rows, area_mm2):
    """Peak direct shear envelope, tau = c + sigma*tan(phi), kPa."""
    area = _number(area_mm2, '전단면적')
    if area <= 0:
        raise ValueError('전단면적은 양수여야 합니다.')
    if len(rows) < 2:
        raise ValueError('전단시험은 서로 다른 수직응력의 시험점이 최소 2개 필요합니다.')
    pts = []
    for r in rows:
        normal = _number(r.get('normal_load_n'), '수직하중')
        shear = _number(r.get('peak_shear_load_n'), '최대 전단하중')
        if normal < 0 or shear < 0:
            raise ValueError('하중은 0 이상이어야 합니다.')
        pts.append(
            {
                'normal_load_n': normal,
                'peak_shear_load_n': shear,
                'normal_stress_kpa': normal / area * 1000,
                'shear_stress_kpa': shear / area * 1000,
            }
        )
    pts.sort(key=lambda r: r['normal_stress_kpa'])
    xs = [r['normal_stress_kpa'] for r in pts]
    ys = [r['shear_stress_kpa'] for r in pts]
    if len(set(xs)) < 2:
        raise ValueError('서로 다른 수직응력이 최소 2개 필요합니다.')
    xm = sum(xs) / len(xs)
    ym = sum(ys) / len(ys)
    ssx = sum((x - xm) ** 2 for x in xs)
    slope = sum((x - xm) * (y - ym) for x, y in zip(xs, ys, strict=True)) / ssx
    intercept = ym - slope * xm
    ssy = sum((y - ym) ** 2 for y in ys)
    r2 = 1 - sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys, strict=True)) / ssy if ssy > 0 else None
    warnings = []
    if len(pts) < 3:
        warnings.append('2점 회귀는 적합도 검증이 불가능합니다. 3개 이상의 수직응력 수준을 권장합니다.')
    if slope < 0:
        warnings.append('전단강도 포락선 기울기가 음수입니다. 데이터와 파괴점 판정을 확인하세요.')
    if intercept < 0:
        warnings.append('회귀 절편이 음수입니다. 음의 점착력을 설계값으로 사용하지 마세요.')
    return {
        'points': pts,
        'cohesion_kpa': round(intercept, 4),
        'friction_angle_deg': round(math.degrees(math.atan(slope)), 4),
        'slope': round(slope, 6),
        'r_squared': round(r2, 5) if r2 is not None else None,
        'warnings': warnings,
        'note': '직접전단시험의 최대하중과 초기 단면적을 이용한 교육용 선형 Mohr-Coulomb 회귀입니다. 면적 보정, 배수조건, 시험속도, 잔류강도 및 유효응력 여부를 검토해야 합니다.',
    }


def unconfined_compression(rows, initial_diameter_mm, initial_height_mm):
    """Area-corrected UCS with compression-positive axial strain."""
    d = _number(initial_diameter_mm, '초기 직경')
    h = _number(initial_height_mm, '초기 높이')
    if d <= 0 or h <= 0:
        raise ValueError('직경과 높이는 양수여야 합니다.')
    if len(rows) < 2:
        raise ValueError('일축압축시험은 최소 2개 측정점이 필요합니다.')
    a0 = math.pi * d * d / 4
    pts = []
    for r in rows:
        shortening = _number(r.get('shortening_mm'), '축방향 압축량')
        force = _number(r.get('load_n'), '축하중')
        if not 0 <= shortening < h or force < 0:
            raise ValueError('압축량은 0 이상 초기 높이 미만, 하중은 0 이상이어야 합니다.')
        strain = shortening / h
        corrected = a0 / (1 - strain)
        pts.append(
            {
                'shortening_mm': shortening,
                'load_n': force,
                'axial_strain_pct': 100 * strain,
                'corrected_area_mm2': corrected,
                'axial_stress_kpa': force / corrected * 1000,
            }
        )
    pts.sort(key=lambda x: x['axial_strain_pct'])
    if len(set(x['axial_strain_pct'] for x in pts)) != len(pts):
        raise ValueError('중복 압축량 측정점은 허용하지 않습니다.')
    peak = max(pts, key=lambda x: x['axial_stress_kpa'])
    warnings = []
    if peak is pts[-1]:
        warnings.append('최대 응력이 마지막 측정점에서 나타났습니다. 파괴점 도달 여부를 확인하세요.')
    if pts[-1]['axial_strain_pct'] > 20:
        warnings.append('큰 축변형률에서는 단면적 보정 가정의 타당성을 확인하세요.')
    return {
        'points': pts,
        'initial_area_mm2': round(a0, 4),
        'qu_kpa': round(peak['axial_stress_kpa'], 4),
        'peak_strain_pct': round(peak['axial_strain_pct'], 4),
        'su_estimate_kpa': round(peak['axial_stress_kpa'] / 2, 4),
        'warnings': warnings,
        'note': 'su=qu/2는 포화 점성토의 비배수조건을 가정한 참고 추정치입니다. 실제 시험조건을 확인하세요. 단면적은 A=A0/(1-ε)로 보정했습니다.',
    }


def liquid_limit(rows):
    """Casagrande multi-point flow curve w = a + b*log10(N), LL at N=25."""
    if len(rows) < 2:
        raise ValueError('액성한계는 서로 다른 타격횟수의 시험점 2개 이상이 필요합니다.')
    pts = []
    for r in rows:
        n = _number(r.get('blows'), '타격횟수')
        if n <= 0 or not n.is_integer():
            raise ValueError('타격횟수는 양의 정수여야 합니다.')
        w = water_content(r.get('wet_container'), r.get('dry_container'), r.get('container'))
        pts.append({'blows': int(n), 'water_content_pct': w, 'log10_blows': math.log10(n)})
    pts.sort(key=lambda x: x['blows'])
    if len(set(x['blows'] for x in pts)) < 2:
        raise ValueError('서로 다른 타격횟수가 필요합니다.')
    xs = [p['log10_blows'] for p in pts]
    ys = [p['water_content_pct'] for p in pts]
    xm = sum(xs) / len(xs)
    ym = sum(ys) / len(ys)
    slope = sum((x - xm) * (y - ym) for x, y in zip(xs, ys, strict=True)) / sum((x - xm) ** 2 for x in xs)
    intercept = ym - slope * xm
    ll = intercept + slope * math.log10(25)
    warnings = []
    if not min(p['blows'] for p in pts) <= 25 <= max(p['blows'] for p in pts):
        warnings.append('25회가 측정 범위 밖에 있어 외삽입니다. 25회 전후 시험점을 추가하세요.')
    if slope >= 0:
        warnings.append('일반적인 유동곡선과 달리 타격횟수가 증가해도 함수비가 감소하지 않습니다. 원자료를 검토하세요.')
    if len(pts) < 3:
        warnings.append('2점만으로 산정했습니다. 신뢰성 향상을 위해 3개 이상의 측정점을 권장합니다.')
    return {
        'points': pts,
        'liquid_limit_pct': round(ll, 3),
        'flow_index': round(-slope, 4),
        'flow_curve_slope': round(slope, 4),
        'flow_curve_intercept': round(intercept, 4),
        'warnings': warnings,
        'note': 'Casagrande 다점법(25회 기준) 계산입니다. 낙하 높이, 홈 폐합, 시험 절차와 적용 규격을 확인하세요. 콘관입법 결과와 직접 혼용하지 마세요.',
    }


def plastic_limit(rows):
    if len(rows) < 2:
        raise ValueError('소성한계는 함수비 반복 측정값 2개 이상을 입력하세요.')
    pts = []
    for r in rows:
        w = water_content(r.get('wet_container'), r.get('dry_container'), r.get('container'))
        pts.append(
            {
                'wet_container': _number(r.get('wet_container'), '습윤+용기'),
                'dry_container': _number(r.get('dry_container'), '건조+용기'),
                'container': _number(r.get('container'), '용기'),
                'water_content_pct': w,
            }
        )
    avg = sum(p['water_content_pct'] for p in pts) / len(pts)
    spread = max(p['water_content_pct'] for p in pts) - min(p['water_content_pct'] for p in pts)
    warnings = []
    if spread > 2:
        warnings.append('반복 측정 함수비 차이가 2%p를 초과합니다. 시험 반복성과 적용 규격의 허용차를 확인하세요.')
    return {
        'points': pts,
        'plastic_limit_pct': round(avg, 3),
        'replicate_range_pct_points': round(spread, 3),
        'warnings': warnings,
        'note': '반복 측정 함수비의 산술평균입니다. 소성한계의 실제 판정은 흙실 지름 약 3.2 mm에서 부스러지는 상태 등 해당 시험규격의 절차를 충족해야 합니다.',
    }


def liquefaction_cycles(rows, initial_effective_stress_kpa):
    """Educational pore pressure ratio ru vs cyclic loading, NOT liquefaction resistance CRR."""
    stress = _number(initial_effective_stress_kpa, '초기 유효구속응력')
    if stress <= 0:
        raise ValueError('초기 유효구속응력은 양수여야 합니다.')
    if len(rows) < 2:
        raise ValueError('반복하중 시험은 최소 2개 측정점이 필요합니다.')
    pts = []
    for row in rows:
        cycles = _number(row.get('cycles'), '반복횟수')
        pressure = _number(row.get('excess_pore_pressure_kpa'), '과잉간극수압')
        if cycles < 0 or not cycles.is_integer() or pressure < 0:
            raise ValueError('반복횟수는 0 이상의 정수, 과잉간극수압은 0 이상이어야 합니다.')
        pts.append({'cycles': int(cycles), 'excess_pore_pressure_kpa': pressure, 'ru': round(pressure / stress, 5)})
    pts.sort(key=lambda x: x['cycles'])
    if len(set(p['cycles'] for p in pts)) != len(pts):
        raise ValueError('중복된 반복횟수는 허용되지 않습니다.')
    threshold = next((p['cycles'] for p in pts if p['ru'] >= 1), None)
    warnings = [
        'ru≥1은 해당 입력 조건에서 초기 유효구속응력에 해당하는 과잉간극수압 도달을 뜻합니다. 실제 액상화 판정은 시험 조건·변형률·배수조건 등을 함께 검토해야 합니다.',
        'CSR/CRR, 현장 액상화 위험도, 안전율은 이 데이터만으로 산정하지 않습니다.',
    ]
    if any(p['ru'] > 1.1 for p in pts):
        warnings.append('ru가 1을 크게 초과합니다. 센서 기준점과 초기 유효응력 설정을 확인하세요.')
    triggered = threshold is not None
    max_ru = round(max(p['ru'] for p in pts), 5)
    judgement = f'발생 ({threshold}회에서 ru≥1.0 도달)' if triggered else f'미발생 (최대 ru={max_ru}, 1.0 미도달)'
    return {
        'points': pts,
        'liquefaction_judgement': judgement,
        'liquefaction_triggered': triggered,
        'first_ru_ge_1_cycle': threshold,
        'liquefaction_criterion_ru': 1.0,
        'max_ru': max_ru,
        'ru_definition': 'ru = Δu / σ′0 (각 반복횟수에서 측정한 과잉간극수압 증가량 ÷ 초기 유효구속응력)',
        'warnings': warnings,
        'note': '반복하중 시험의 과잉간극수압비 ru=Δu/σ′0를 반복횟수마다 계산하고, ru≥1.0(초기 유효응력 소실) 도달 여부로 '
        '시험 시료의 액상화 발생을 판정합니다. 기준을 ru≥0.95나 양진폭 변형률 5%로 두는 경우도 있으므로 시험 기준을 확인하세요. '
        '현장 액상화 위험도(CSR/CRR, 안전율)를 판정하는 기능은 아닙니다.',
    }


# Raw field-sheet workflows: no spreadsheet or assumed instrument calibration required.
def water_batch(rows):
    if len(rows) < 1:
        raise ValueError('최소 1개의 함수비 캔을 입력하세요.')
    points = []
    for i, r in enumerate(rows, 1):
        w = water_content(r.get('wet_container'), r.get('dry_container'), r.get('container'))
        points.append(
            {
                'can': i,
                'wet_container': float(r['wet_container']),
                'dry_container': float(r['dry_container']),
                'container': float(r['container']),
                'water_content_pct': w,
            }
        )
    avg = sum(x['water_content_pct'] for x in points) / len(points)
    return {
        'points': points,
        'average_water_content_pct': round(avg, 3),
        'water_content_pct': round(avg, 3),
        'range_pct_points': round(
            max(x['water_content_pct'] for x in points) - min(x['water_content_pct'] for x in points), 3
        ),
        'warnings': ([] if len(points) > 1 else ['1개 캔만 측정했습니다. 반복성 검토에는 추가 시료가 필요합니다.']),
        'note': '캔별 함수비의 산술평균입니다. 서로 다른 시료·깊이의 결과를 무조건 평균하지 마세요.',
    }


def compaction_raw(rows, mold_volume_cm3):
    volume = _number(mold_volume_cm3, '몰드 체적')
    if volume <= 0:
        raise ValueError('몰드 체적은 양수여야 합니다.')
    if len(rows) < 3:
        raise ValueError('다짐곡선에는 최소 3개 시험점이 필요합니다.')
    computed = []
    for i, r in enumerate(rows, 1):
        mold = _number(r.get('mold_mass_g'), '몰드 질량')
        full = _number(r.get('mold_soil_mass_g'), '몰드+습윤토 질량')
        if mold < 0 or full <= mold:
            raise ValueError(f'{i}번 시험점: 몰드+시료 질량은 몰드보다 커야 합니다.')
        w = water_content(r.get('wet_container'), r.get('dry_container'), r.get('container'))
        wet_density = (full - mold) / volume
        computed.append({'water_pct': w, 'wet_density': wet_density, 'mold_soil_mass_g': full, 'mold_mass_g': mold})
    out = compaction(computed)
    out['raw_measurements'] = computed
    out['mold_volume_cm3'] = volume
    out['warnings'] = [
        '각 다짐점의 함수비는 입력한 대표 캔 1개의 결과입니다. 반복 캔이 있다면 별도 함수비 분석에서 평균을 확인하세요.',
        '몰드 체적·해머·낙하높이·층수·시료 입도 조건을 확인해야 시험법 적합성을 판단할 수 있습니다.',
    ]
    return out


def sieve_retained(rows, total_dry_mass_g):
    total = _number(total_dry_mass_g, '전체 건조질량')
    if total <= 0:
        raise ValueError('전체 건조질량은 양수여야 합니다.')
    retained = []
    for r in rows:
        d = _number(r.get('diameter_mm'), '체 크기')
        m = _number(r.get('retained_mass_g'), '잔류질량')
        if d <= 0 or m < 0:
            raise ValueError('체 크기는 양수, 잔류질량은 0 이상이어야 합니다.')
        retained.append((d, m))
    retained.sort(reverse=True)
    if len({d for d, _ in retained}) != len(retained):
        raise ValueError('중복 체 크기가 있습니다.')
    if sum(m for _, m in retained) > total * 1.001:
        raise ValueError('잔류질량 합이 전체 건조질량을 초과합니다.')
    cumulative = 0
    points = []
    for d, m in retained:
        cumulative += m
        points.append({'diameter_mm': d, 'passing_pct': 100 * (1 - cumulative / total)})
    result = grain_analysis(points)
    result['retained_mass_total_g'] = round(sum(m for _, m in retained), 4)
    result['unaccounted_mass_g'] = round(total - sum(m for _, m in retained), 4)
    result['warnings'].append(
        '잔류질량 합계에 팬(pan) 질량이 포함되지 않으면 No.200 통과율이 과대평가될 수 있습니다. 체 분석 전후 질량수지를 확인하세요.'
    )
    return result


# v5: five independent compaction points, two water-content cans per point.
def paired_compaction(rows, mold_volume_cm3):
    volume = _number(mold_volume_cm3, '몰드 체적 (cm³)')
    if volume <= 0:
        raise ValueError('몰드 체적은 양수여야 합니다.')
    if len(rows) < 3:
        raise ValueError('다짐곡선에는 최소 3개 이상의 다짐시험점이 필요합니다.')
    derived = []
    detail = []
    warnings = []
    for i, r in enumerate(rows, 1):
        mold = _number(r.get('mold_mass_g'), '몰드 무게')
        full = _number(r.get('mold_soil_mass_g'), '몰드+습윤시료 무게')
        if mold < 0 or full <= mold:
            raise ValueError(f'{i}번 다짐점: 몰드 질량을 확인하세요.')
        cans = []
        for j in (1, 2):
            can = r.get(f'can{j}')
            if not isinstance(can, dict):
                raise ValueError(f'{i}번 다짐점: {j}번 캔 데이터가 필요합니다.')
            w = water_content(can.get('wet_container'), can.get('dry_container'), can.get('container'))
            cans.append(w)
        avg = sum(cans) / 2
        wet_density = (full - mold) / volume
        dry_density = wet_density / (1 + avg / 100)
        derived.append({'water_pct': avg, 'wet_density': wet_density})
        detail.append(
            {
                'point_no': i,
                'can_numbers': [2 * i - 1, 2 * i],
                'can_water_pct': cans,
                'average_water_pct': round(avg, 3),
                'difference_pct_points': round(abs(cans[0] - cans[1]), 3),
                'wet_soil_mass_g': round(full - mold, 3),
                'wet_density': round(wet_density, 5),
                'dry_density': round(dry_density, 5),
            }
        )
        if abs(cans[0] - cans[1]) > 2:
            warnings.append(f'{i}번 다짐점: 두 캔의 함수비 차이가 2%p를 초과합니다. 재확인 권장(규격상 허용차 아님).')
    out = compaction(derived)
    out['paired_details'] = detail
    out['mold_volume_cm3'] = volume
    out['warnings'] = warnings + [
        '두 캔의 함수비 산술평균으로 다짐점별 건조밀도를 계산했습니다. 몰드 체적과 다짐 에너지·시험법을 확인하세요.'
    ]
    out['note'] = (
        '최대 건조밀도는 측정된 시험점 중 최대값이며 곡선 꼭짓점 추정값이 아닙니다. 실제 캔과 다짐점의 짝을 확인하세요.'
    )
    return out


def limits_workflow(dry_cans, wet_cans, liquid_rows, plastic_rows):
    """Initial moisture groups are NOT used as LL points; independent LL and PL trials."""
    if len(dry_cans) != 2 or len(wet_cans) != 2:
        raise ValueError('초기 건조측·습윤측 함수비는 각각 정확히 2개의 캔을 입력하세요.')

    def group(rows):
        vals = [water_content(r.get('wet_container'), r.get('dry_container'), r.get('container')) for r in rows]
        return {
            'cans_water_pct': vals,
            'average_pct': round(sum(vals) / len(vals), 3),
            'range_pct_points': round(max(vals) - min(vals), 3),
        }

    dry = group(dry_cans)
    wet = group(wet_cans)
    ll = liquid_limit(liquid_rows)
    pl = plastic_limit(plastic_rows)
    pi = ll['liquid_limit_pct'] - pl['plastic_limit_pct']
    warnings = list(ll.get('warnings', [])) + list(pl.get('warnings', []))
    if pi < 0:
        warnings.append('PI가 음수입니다. LL·PL 시험값과 시료의 동일성 및 판정 조건을 재검토하세요.')
    return {
        'initial_dry_group': dry,
        'initial_wet_group': wet,
        'liquid_limit_pct': ll['liquid_limit_pct'],
        'plastic_limit_pct': pl['plastic_limit_pct'],
        'plasticity_index_pct': round(pi, 3),
        'flow_index': ll['flow_index'],
        'flow_curve_slope': ll['flow_curve_slope'],
        'flow_curve_intercept': ll['flow_curve_intercept'],
        'points': ll['points'],
        'plastic_points': pl['points'],
        'warnings': warnings,
        'note': '초기 건조측/습윤측의 두 캔 평균은 별도 참고 함수비이며 LL 계산에 직접 대입하지 않습니다. LL은 타격횟수별 함수비의 유동곡선 25회 값입니다.',
    }
