# No one can know the soil. v14 · UI repair

**v13 화면 오류 수정판.** 홈 배너 아이콘 SVG 내장, 모든 페이지 공통 기본 CSS 적용, 대시보드의 구형 `/lab` 링크를 `/studio`로 변경했습니다.

# No one can know the soil. · v13 (v9 원본 기반 수정)

v9 메인 홈을 유지하고 **실제 HTML/JS/CSS를 수정**한 버전입니다.

- `/`: 자동 배너·시험 아이콘 홈 (기본)
- `/studio`: 원자료 입력, Python 계산, 그래프, 브라우저 시료 삭제
- `/samples`: 시료별 통합 결과, USCS 판정 근거, 공학적 검토, 브라우저 시료 삭제
- `/dashboard`: SQLite 저장 기록 요약
- `/methods`: 시험 방법 안내
- `/lab`, `/classic`: 구형 별도 페이지 삭제 (404)

모든 주요 페이지의 로고는 `/`로 이동합니다. 함수비 2캔 계산은 삭제하지 않고 시험 분석에 유지했습니다.

## Mac 실행

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements-dev.txt
cp .env.example .env   # AI_API_KEY 에 코디세이 콘솔 키 입력
python3 -m uvicorn app.main:app --reload --port 8001 --env-file .env
```

브라우저에서 [http://127.0.0.1:8001/](https://no-one-can-know-the-soil.vercel.app) 로 접속합니다. `/studio`는 메인 홈이 아닙니다.

## 저장과 삭제

시료 삭제는 브라우저 localStorage의 해당 시료만 삭제합니다. 서버 SQLite 기록은 삭제하지 않습니다. 공개 서버에는 비공개 실험 데이터를 입력하지 마세요. 실제 설계 판단 및 공인 시험 성적서를 대체하지 않습니다.

## AI API (코디세이 AI Gateway)

AI 해설은 OpenAI 대신 **코디세이 콘솔(https://copa.codyssey.kr) Gateway**를 호출합니다 (`app/llm.py`).

| 환경 변수 | 필수 | 기본값 | 설명 |
|---|---|---|---|
| `AI_API_KEY` | ✅ | – | 코디세이 콘솔에서 발급한 키 |
| `AI_BASE_URL` | | `https://copa.codyssey.kr` | Gateway 주소 (`/v1` 있어도 됨) |
| `AI_MODEL` | | `claude-haiku-4` | 콘솔에 안내된 모델 이름 |
| `AI_API_FORMAT` | | 자동 | 비우면 Anthropic 형식 → 404/405 시 OpenAI 호환 형식으로 자동 전환 |
| `AI_MAX_TOKENS` | | `1200` | 응답 최대 토큰 |

키가 없거나 Gateway 호출이 실패하면 규칙 기반 로컬 해설로 자동 전환됩니다. `/api/health`에서 키 설정 여부(값은 노출 안 함)를 확인할 수 있습니다.

## Vercel 배포

1. GitHub에 push 후 Vercel → **Add New Project** → 저장소 선택
2. **Root Directory**를 `Codyssey_Final/No_one_can_know_the_soil_v14` 로 지정 (Framework Preset: Other)
3. **Environment Variables**에 `AI_API_KEY` (필요 시 `AI_MODEL`, `AI_BASE_URL`) 추가 → Deploy
4. 배포 후 `https://<프로젝트>.vercel.app/api/health` 에서 `ai_configured: true` 확인

구성: `api/index.py`(FastAPI 진입점) + `vercel.json`(모든 경로를 FastAPI로 전달). `.vercelignore`로 `.venv`, 테스트, 문서, 발표자료는 업로드에서 제외됩니다.

> ⚠️ Vercel 서버리스는 `/tmp`만 쓸 수 있어 SQLite가 `/tmp/geosoil.sqlite3`에 저장되며, 인스턴스가 바뀌면 **서버 저장 기록·피드백이 초기화**됩니다. 브라우저 localStorage 시료 데이터는 영향 없습니다. 영구 저장이 필요하면 외부 DB(예: Firestore, Vercel Postgres)로 바꿔야 합니다.
