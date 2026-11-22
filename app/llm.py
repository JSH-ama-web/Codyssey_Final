"""코디세이 AI Gateway(copa.codyssey.kr) 비동기 클라이언트.

환경 변수
  AI_API_KEY    : 코디세이 콘솔에서 발급한 키 (필수, 코드/깃에 절대 넣지 않음)
  AI_BASE_URL   : Gateway 주소, 기본 https://copa.codyssey.kr (끝에 /v1 이 있어도 됨)
  AI_MODEL      : 모델 이름, 기본 claude-haiku-4
  AI_API_FORMAT : 비우면 Anthropic Messages 형식 → 404/405 시 OpenAI 호환 형식으로 자동 전환
                  'anthropic' / 'openai' 로 고정 가능
  AI_MAX_TOKENS : 응답 최대 토큰, 기본 1200
  AI_TIMEOUT    : 요청 제한 시간(초), 기본 40
"""
from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger(__name__)
_resolved_format: str | None = None  # 자동 감지 결과 캐시


class LLMError(Exception):
    pass


def _env(name: str, default: str = '') -> str:
    return os.getenv(name, '').strip() or default


def settings() -> dict:
    return {
        'api_key': _env('AI_API_KEY'),
        'base_url': _env('AI_BASE_URL', 'https://copa.codyssey.kr'),
        'model': _env('AI_MODEL', 'claude-haiku-4'),
        'format': _env('AI_API_FORMAT').lower(),
        'max_tokens': int(_env('AI_MAX_TOKENS', '1200')),
        'timeout': float(_env('AI_TIMEOUT', '40')),
    }


def is_configured() -> bool:
    return bool(settings()['api_key'])


def public_config() -> dict:
    """키 값은 노출하지 않는 진단용 정보 (/api/health)."""
    s = settings()
    return {'api_key_set': bool(s['api_key']), 'base_url': s['base_url'], 'model': s['model'],
            'format': s['format'] or f"auto({_resolved_format or 'anthropic'})"}


def _url(base: str, path: str) -> str:
    base = base.rstrip('/')
    if base.endswith('/v1'):
        base = base[:-3]
    return base + path


async def _anthropic(client: httpx.AsyncClient, s: dict, system: str, user: str, temperature: float) -> str:
    res = await client.post(_url(s['base_url'], '/v1/messages'),
        headers={'x-api-key': s['api_key'], 'anthropic-version': '2023-06-01', 'content-type': 'application/json'},
        json={'model': s['model'], 'max_tokens': s['max_tokens'], 'temperature': temperature,
              'system': system, 'messages': [{'role': 'user', 'content': user}]})
    res.raise_for_status()
    blocks = res.json().get('content', [])
    return ''.join(b.get('text', '') for b in blocks if b.get('type') == 'text').strip()


async def _openai(client: httpx.AsyncClient, s: dict, system: str, user: str, temperature: float) -> str:
    res = await client.post(_url(s['base_url'], '/v1/chat/completions'),
        headers={'Authorization': f"Bearer {s['api_key']}", 'content-type': 'application/json'},
        json={'model': s['model'], 'max_tokens': s['max_tokens'], 'temperature': temperature,
              'messages': [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]})
    res.raise_for_status()
    return (res.json()['choices'][0]['message'].get('content') or '').strip()


def _describe(e: httpx.HTTPStatusError) -> str:
    code = e.response.status_code
    logger.warning('AI Gateway HTTP %s: %s', code, e.response.text[:300])
    if code in (401, 403):
        return f'AI 인증 실패({code}): AI_API_KEY 를 확인하세요.'
    if code == 404:
        return f"AI 주소나 모델 이름이 올바르지 않습니다(404). AI_BASE_URL·AI_MODEL='{settings()['model']}' 확인"
    if code == 429:
        return 'AI 사용량 한도를 초과했습니다(429). 잠시 후 다시 시도하세요.'
    return f'AI API 오류({code})'


async def complete(system: str, user: str, temperature: float = 0.1) -> str:
    """system + user 프롬프트 → 텍스트 응답. 실패하면 LLMError."""
    global _resolved_format
    s = settings()
    if not s['api_key']:
        raise LLMError('AI_API_KEY 가 설정되지 않았습니다.')
    fmt = s['format'] or _resolved_format or 'anthropic'
    try:
        async with httpx.AsyncClient(timeout=s['timeout']) as client:
            try:
                call = _openai if fmt == 'openai' else _anthropic
                text = await call(client, s, system, user, temperature)
            except httpx.HTTPStatusError as e:
                # 형식 자동 감지: Anthropic 경로가 없으면 OpenAI 호환으로 한 번 전환
                if s['format'] or fmt != 'anthropic' or e.response.status_code not in (404, 405):
                    raise
                logger.info('Anthropic 형식 %s → OpenAI 호환 형식으로 전환', e.response.status_code)
                fmt = 'openai'
                text = await _openai(client, s, system, user, temperature)
        _resolved_format = fmt
        return text
    except httpx.HTTPStatusError as e:
        raise LLMError(_describe(e)) from e
    except httpx.TimeoutException as e:
        raise LLMError('AI 응답 시간이 초과됐습니다.') from e
    except httpx.HTTPError as e:
        raise LLMError(f'AI 서버 연결 실패: {e}') from e
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise LLMError('AI 응답 형식을 해석하지 못했습니다. AI_API_FORMAT 설정을 확인하세요.') from e
