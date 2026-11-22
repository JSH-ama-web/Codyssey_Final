"""운영 로그·오류 처리.

- 모든 API 요청을 JSON 한 줄 로그로 남긴다 (Vercel → Project → Logs 에서 확인).
- 처리되지 않은 예외는 request_id 와 함께 스택트레이스를 로그로 남기고,
  사용자에게는 내부 정보 없이 request_id 만 돌려준다.
- 각 응답에 X-Request-ID 헤더를 붙여 사용자 제보와 서버 로그를 연결한다.
"""

from __future__ import annotations

import json
import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger('geosoil')
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False

STARTED_AT = time.time()
STATS = {'requests': 0, 'errors_4xx': 0, 'errors_5xx': 0}


def log_event(event: str, **fields) -> None:
    logger.info(json.dumps({'event': event, 'ts': round(time.time(), 3), **fields}, ensure_ascii=False))


def uptime_info() -> dict:
    return {'started_at': int(STARTED_AT), 'uptime_s': int(time.time() - STARTED_AT), **STATS}


def install(app: FastAPI) -> None:
    @app.middleware('http')
    async def access_log(request: Request, call_next):
        request_id = request.headers.get('x-request-id') or uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            STATS['requests'] += 1
            STATS['errors_5xx'] += 1
            logger.exception(
                json.dumps(
                    {
                        'event': 'unhandled_error',
                        'request_id': request_id,
                        'method': request.method,
                        'path': request.url.path,
                    },
                    ensure_ascii=False,
                )
            )
            return JSONResponse(
                status_code=500,
                content={'detail': '서버 내부 오류가 발생했습니다.', 'request_id': request_id},
                headers={'X-Request-ID': request_id},
            )
        elapsed = round((time.perf_counter() - start) * 1000, 1)
        STATS['requests'] += 1
        if 400 <= response.status_code < 500:
            STATS['errors_4xx'] += 1
        elif response.status_code >= 500:
            STATS['errors_5xx'] += 1
        if request.url.path.startswith('/api/'):
            log_event(
                'request',
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                ms=elapsed,
            )
        response.headers['X-Request-ID'] = request_id
        return response
