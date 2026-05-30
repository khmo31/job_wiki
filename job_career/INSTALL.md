# Career Agent 설치 가이드

## 요구사항

- Python 3.11+
- `conda activate job_career`
- `pip install -e .` 로 `job_career` 패키지 설치
- LLM API 키 (선택 — 없으면 regex+facet fallback)

`pyproject.toml` 기준 런타임 의존성:
- `flask`
- `flask-cors`
- `python-dotenv`
- `pydantic`
- `requests`

## 설치

```bash
# 1. conda 환경 활성화
conda activate job_career

# 2. job_career 패키지 설치
cd job_wiki/job_career
pip install -e .
```

루트 워크스페이스를 처음 세팅할 때는 아래도 함께 설치하세요.

```bash
cd job_wiki
pip install -r requirements.txt
pip install -r job_raw/requirements.txt
```

## 환경변수

매칭 엔진은 4가지 LLM 제공자를 지원합니다 (우선순위 순):

| 변수 | 예시 | 제공자 |
|------|------|--------|
| `OPENCODE_API_KEY` | (OpenClaw key) | OpenCode Go (1순위, deepseek-v4-flash) |
| `GROQ_API_KEY` | `gsk_...` | Groq (2순위) |
| `OPENAI_API_KEY` | `sk-...` | OpenAI (3순위) |
| `NVIDIA_API_KEY` | `nvapi-...` | NVIDIA (4순위) |

선택적 변수:
- `LLM_EXTRACT_MODEL`: 사용할 모델명 (기본: `deepseek-v4-flash`)
- `OPENCODE_BASE_URL`: OpenCode Go API 엔드포인트 (기본: `https://opencode.ai/zen/go/v1/chat/completions`)
- `ONTOLOGY_CHECK_CACHE_TTL`: 온톨로지 캐시 TTL (초, 기본 60)

## 실행

```bash
# 1. 자동 매칭 (프로필 기반)
cd job_career
python src/career_agent/pipeline.py --profile "병원 의무기록 5년, 개인정보보호 교육 이수"

# 2. 배치 모드
python src/career_agent/main_batch.py

# 3. 웹 서버 (프론트엔드 포함)
python server.py
```

## 캐시

`20_Meta/ontology_cache.json`에 검증 결과가 TTL 기간 동안 캐시됩니다.
캐시 초기화가 필요하면:
```bash
rm job_wiki/20_Meta/ontology_cache.json
```

## 데이터 의존성

매칭 엔진은 다음 데이터 파일을 필요로 합니다:

```
job_wiki/20_Meta/
├── Facet_Index.json       # facet 집계 색인 (필수)
└── ontology_cache.json    # 검증 캐시 (선택)
```

Facet_Index.json이 없으면 먼저 `job_core/scripts/wiki_generator.py`를 실행하세요.
