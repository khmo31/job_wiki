# Career Agent — 사용자 프로필 기반 공공기관 채용 매칭

사용자의 자연어 프로필(경력/기술/자격증)을 분석하여 가장 적합한 공공기관 채용공고를 추천합니다.

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

2-Track 매칭: **LLM 우선 → regex+facet fallback**

- LLM 키워드 추출 (Facet index md를 프롬프트 컨텍스트로 사용)
- Facet_Index.json 기반 후보 라우팅
- facet/raw 검색 + 점수화 (정확/부분 매칭)
- 상위 5개 기관 추천

## 의존성

- `job_wiki/20_Meta/Facet_Index.json` — 2차 분류 인덱스
- `job_wiki/10_Wiki/Facets/**/*.md` — LLM 컨텍스트용 facet 페이지
- LLM API 키 (선택) — 없으면 fallback 모드로 동작
