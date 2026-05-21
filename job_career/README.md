# Career Agent — 사용자 프로필 기반 공공기관 채용 매칭

사용자의 자연어 프로필(경력/기술/자격증)을 분석하고, 확정되지 않은 분류를 먼저 선택한 뒤 최종 추천을 제공하는 공공기관 채용공고 매칭 UI입니다.

[설치 가이드](INSTALL.md) | [워크플로우 상세](WORKFLOW.md)

## 빠른 사용

```bash
# conda 환경 활성화
conda activate job_career

# 프로필 기반 추천
python src/career_agent/pipeline.py --profile "의료정보관리 5년, 간호사 면허"

# 웹 UI
python server.py
# → http://localhost:8080
```

## 아키텍처

2-Track 매칭: **LLM 초기 후보 생성 → Python 최종 추천**

- LLM 키워드 추출 (Facet index md를 프롬프트 컨텍스트로 사용)
- Facet_Index.json 기반 후보 라우팅
- 1차 분석에서는 follow-up 질문만 보여주고 추천은 숨김
- follow-up 선택 이후에는 Python 점수화로만 최종 추천 생성
- facet/raw 검색 + 점수화 (정확/부분 매칭)
- 상위 5개 기관 추천
- 매칭 점수는 100% 기준으로 환산하며, 프로필 입력 기반 단서는 보완 선택보다 3배 높은 가중치를 적용하고 50% 초과만 노출
- follow-up 세션은 1회만 허용하고, 선택 시간이 5분을 넘으면 초기 상태로 복귀
- follow-up 선택지에는 각 분류의 `상관없음`이 포함되어 해당 분류를 무가중치로 처리
- LLM이 키워드를 하나라도 반환하면 초기 follow-up 후보 생성에 활용하고, 최종 추천은 Python이 담당

## 실행 흐름

1. 사용자가 프로필을 입력한다.
2. 1차 분석은 follow-up 질문만 보여주고 추천 기업은 숨긴다.
3. 사용자가 확정되지 않은 분류를 선택한다.
4. 최종 분석에서 추천 기업과 관련 공고를 반환한다.

## 의존성

- `job_wiki/20_Meta/Facet_Index.json` — 2차 분류 인덱스
- `job_wiki/10_Wiki/Facets/**/*.md` — LLM 컨텍스트용 facet 페이지
- LLM API 키 (선택) — 없으면 fallback 모드로 동작

## GitHub Actions 연동

- 수집은 `job_raw/scripts/main.py`가 담당합니다.
- 만료 정리는 `job_core/scripts/cleanup_expired.py`가 담당합니다.
- Wiki 변환은 `job_core/scripts/wiki_generator.py`가 담당합니다.
