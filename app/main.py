import json
import os
import sqlite3
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import llm, observability
from .agent import explain, route

ROOT = Path(__file__).resolve().parent.parent
# Vercel 서버리스는 /tmp 만 쓰기 가능 (인스턴스가 바뀌면 초기화됨)
_DEFAULT_DB = '/tmp/geosoil.sqlite3' if os.getenv('VERCEL') else str(ROOT / 'geosoil.sqlite3')
DB = Path(os.getenv('DATABASE_PATH') or _DEFAULT_DB)
app = FastAPI(
    title='No one can know the soil.', version='14.2.0', description='교육용 토질시험 원자료 계산 및 공학적 해석 Agent'
)
observability.install(app)
app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')


class AnalysisRequest(BaseModel):
    task: str
    payload: dict
    question: str = '시험 결과, 지반 거동 가능성, 시공 시 주의사항, 추가 시험 및 한계를 구분해 설명해줘.'


class SavedRecord(BaseModel):
    owner_key: str = Field(min_length=24, max_length=128, pattern=r'^[a-zA-Z0-9_-]+$')
    title: str = Field(min_length=1, max_length=120)
    task: str = Field(min_length=1, max_length=30)
    payload: dict
    result: dict
    explanation: dict


class RecordOwner(BaseModel):
    owner_key: str = Field(min_length=24, max_length=128, pattern=r'^[a-zA-Z0-9_-]+$')


class Feedback(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = Field(min_length=3, max_length=1000)
    task: str = Field(default='general', max_length=30)


def connection():
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB, timeout=10)
    conn.execute(
        'CREATE TABLE IF NOT EXISTS feedback (id TEXT PRIMARY KEY, created_at INTEGER, rating INTEGER, comment TEXT, task TEXT)'
    )
    conn.execute(
        'CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, owner_key TEXT NOT NULL, created_at INTEGER NOT NULL, title TEXT NOT NULL, task TEXT NOT NULL, payload TEXT NOT NULL, result TEXT NOT NULL, explanation TEXT NOT NULL)'
    )
    conn.execute('CREATE INDEX IF NOT EXISTS idx_records_owner ON records(owner_key, created_at DESC)')
    conn.commit()
    return conn


@app.get('/')
def home():
    return FileResponse(ROOT / 'static' / 'home.html')


@app.get('/samples')
def samples_page():
    return FileResponse(ROOT / 'static' / 'samples.html')


@app.get('/studio')
def studio():
    return FileResponse(ROOT / 'static' / 'studio.html')


@app.get('/dashboard')
def dashboard():
    return FileResponse(ROOT / 'static' / 'dashboard.html')


@app.get('/methods')
def methods():
    return FileResponse(ROOT / 'static' / 'methods.html')


@app.get('/manifest.webmanifest')
def manifest():
    return FileResponse(ROOT / 'static' / 'manifest.webmanifest', media_type='application/manifest+json')


@app.get('/sw.js')
def sw():
    return FileResponse(ROOT / 'static' / 'sw.js', media_type='text/javascript')


@app.get('/api/health')
def health():
    return {
        'status': 'ok',
        'version': '14.2.0',
        'ai_configured': llm.is_configured(),
        'ai': llm.public_config(),
        'runtime': observability.uptime_info(),
        'commit': os.getenv('VERCEL_GIT_COMMIT_SHA', 'local')[:7],
    }


@app.post('/api/analyze')
async def analyze(request: AnalysisRequest):
    try:
        result = route(request.task, request.payload)
    except (ValueError, KeyError, TypeError, ZeroDivisionError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    explanation = await explain(request.task, result, request.question[:1500])
    return {'task': request.task, 'result': result, 'explanation': explanation}


class ClassificationRequest(BaseModel):
    points: list[dict]
    ll: float | None = None
    pl: float | None = None
    nonplastic: bool = False


@app.post('/api/classify')
def classify_soil(item: ClassificationRequest):
    from .engineering import grain_analysis

    try:
        return grain_analysis(item.points, ll=item.ll, pl=item.pl, nonplastic=item.nonplastic)
    except (ValueError, KeyError, TypeError, ZeroDivisionError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post('/api/feedback', status_code=201)
def feedback(item: Feedback):
    with connection() as conn:
        conn.execute(
            'INSERT INTO feedback VALUES (?,?,?,?,?)',
            (str(uuid.uuid4()), int(time.time()), item.rating, item.comment, item.task),
        )
    return {'saved': True}


@app.get('/api/feedback/stats')
def feedback_stats():
    with connection() as conn:
        n, avg = conn.execute('SELECT COUNT(*), AVG(rating) FROM feedback').fetchone()
    return {'count': n, 'average_rating': round(avg, 2) if avg is not None else None}


# Private-by-secret record ownership: suitable for a local educational MVP, not full user authentication.
@app.post('/api/records', status_code=201)
def save_record(item: SavedRecord):
    if item.task not in (
        'grain',
        'compaction',
        'consolidation',
        'water',
        'shear',
        'ucs',
        'liquid',
        'plastic',
        'liquefaction',
        'water_batch',
        'compaction_raw',
        'sieve_raw',
        'paired_compaction',
        'limits_workflow',
    ):
        raise HTTPException(status_code=422, detail='지원하지 않는 시험 유형')
    try:
        verified_result = route(item.task, item.payload)
    except (ValueError, KeyError, TypeError, ZeroDivisionError) as exc:
        raise HTTPException(status_code=422, detail='입력 자료 검증 실패: ' + str(exc)) from exc
    if verified_result != item.result:
        raise HTTPException(status_code=422, detail='계산 결과와 입력값이 일치하지 않습니다. 분석을 다시 실행하세요.')
    serialized = [
        json.dumps(v, ensure_ascii=False, allow_nan=False) for v in (item.payload, verified_result, item.explanation)
    ]
    if sum(map(len, serialized)) > 300000:
        raise HTTPException(status_code=413, detail='저장 용량 제한 초과')
    rid = str(uuid.uuid4())
    created = int(time.time())
    with connection() as conn:
        conn.execute(
            'INSERT INTO records VALUES (?,?,?,?,?,?,?,?)',
            (rid, item.owner_key, created, item.title, item.task, *serialized),
        )
    return {'id': rid, 'created_at': created, 'saved': True}


@app.get('/api/records')
def list_records(owner_key: str):
    if len(owner_key) < 24 or len(owner_key) > 128 or not all(c.isalnum() or c in '_-' for c in owner_key):
        raise HTTPException(status_code=422, detail='올바른 저장소 키가 필요합니다.')
    with connection() as conn:
        rows = conn.execute(
            'SELECT id,created_at,title,task FROM records WHERE owner_key=? ORDER BY created_at DESC LIMIT 100',
            (owner_key,),
        ).fetchall()
    return {'records': [dict(zip(('id', 'created_at', 'title', 'task'), r, strict=True)) for r in rows]}


@app.get('/api/records/{record_id}')
def get_record(record_id: str, owner_key: str):
    with connection() as conn:
        row = conn.execute(
            'SELECT id,created_at,title,task,payload,result,explanation FROM records WHERE id=? AND owner_key=?',
            (record_id, owner_key),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail='기록을 찾을 수 없습니다.')
    return {
        'id': row[0],
        'created_at': row[1],
        'title': row[2],
        'task': row[3],
        'payload': json.loads(row[4]),
        'result': json.loads(row[5]),
        'explanation': json.loads(row[6]),
    }


@app.delete('/api/records/{record_id}')
def delete_record(record_id: str, item: RecordOwner):
    with connection() as conn:
        cur = conn.execute('DELETE FROM records WHERE id=? AND owner_key=?', (record_id, item.owner_key))
    if not cur.rowcount:
        raise HTTPException(status_code=404, detail='기록을 찾을 수 없습니다.')
    return {'deleted': True}
