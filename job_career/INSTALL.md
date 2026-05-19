# Career Agent 설치 가이드

## 요구사항

- Python 3.11+
- 요청: `pip install -r ../requirements.txt` (루트 requirements.txt 사용)
- CrewAI (온톨로지 검증 도구용, 경량)
- LLM API 키 (선택 — 없으면 regex+Ontology fallback)

## 설치

```bash
# 1. 루트 requirements.txt 설치
cd job_wiki
pip install -r requirements.txt

# 2. job_career 전용 추가 패키지
pip install crewai  # 커스텀 도구용
```

## 환경변수

매칭 엔진은 3가지 LLM 제공자를 지원합니다 (우선순위 순):

| 변수 | 예시 | 제공자 |
|------|------|--------|
| `GROQ_API_KEY` | `gsk_...` | Groq (1순위) |
| `OPENAI_API_KEY` | `sk-...` | OpenAI (2순위) |
| `NVIDIA_API_KEY` | `nvapi-...` | NVIDIA (3순위) |

선택적 변수:
- `LLM_EXTRACT_MODEL`: 사용할 모델명 (기본: `llama-3.3-70b-versatile`)
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

## 온톨로지 캐시

`20_Meta/ontology_cache.json`에 온톨로지 검증 결과가 TTL 기간 동안 캐시됩니다.
캐시 초기화가 필요하면:
```bash
rm job_wiki/20_Meta/ontology_cache.json
```

## 데이터 의존성

매칭 엔진은 다음 데이터 파일을 필요로 합니다:

```
job_wiki/20_Meta/
├── Ontology_Map.json      # 표준 키워드 + 동의어 (필수)
├── Wiki_Index.json        # 검색 인덱스 (필수, 417 entries)
└── Suggested_Keywords.json # LLM 제안 키워드 (선택)
```

Wiki_Index.json이 비어있으면 (`{}`) 먼저 wiki_generator.py를 실행하세요.
