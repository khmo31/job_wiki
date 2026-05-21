# 프로젝트 변경 기록

기준: 2026-05-21 작업 내역을 커밋 순서대로 정리했습니다.

## 2026-05-21 09ba7f91 - Refine career matching flow

- `job_career`의 추천 흐름을 단계형으로 재구성했습니다.
- 초기 분석에서는 추천 기업을 바로 보여주지 않고, follow-up 질문만 노출하도록 변경했습니다.
- LLM이 추출한 키워드를 follow-up 분류 판정에도 반영하도록 조정했습니다.
- `LLM -> Python` 분리를 명확히 하고, 최종 추천은 Python 점수화로만 계산하도록 정리했습니다.
- 원본 공고 아카이브 경로와 파일명 해석 로직을 실제 수집 구조에 맞게 수정했습니다.
- 관련 공고 목록은 공고별 최종 매칭률 기준으로 50% 이상만 남기도록 정리했습니다.
- OpenCode 엔드포인트, LLM timeout, session lifecycle 관련 동작을 맞췄습니다.
- UI는 초기 결과를 "분류 선택 대기" 흐름으로 표현하도록 조정했습니다.

영향 파일:
- `job_career/src/career_agent/pipeline.py`
- `job_career/src/career_agent/main_batch.py`
- `job_career/src/career_agent/llm_client.py`
- `job_career/server.py`
- `job_career/frontend/script.js`
- `job_career/frontend/index.html`
- `job_career/README.md`

## 2026-05-21 dbd63c1 - Align harvest workflow with current pipeline

- GitHub Actions 수집 워크플로우를 현재 `job_raw` / `job_core` 구조에 맞게 정리했습니다.
- Windows식 `cd` 의존을 제거하고, 우분투 러너에서 바로 실행되는 bash-safe 경로 호출로 변경했습니다.
- 수집 단계에서 `job_raw/scripts/main.py`를 직접 실행하도록 맞췄습니다.
- 만료 정리와 Wiki 변환도 각각 `job_core/scripts/cleanup_expired.py`, `job_core/scripts/wiki_generator.py`를 직접 호출하도록 수정했습니다.
- `job_raw/requirements.txt`를 함께 설치하도록 보강했습니다.

영향 파일:
- `.github/workflows/harvest.yml`

## 2026-05-21 b4586af - auto: 채용공고 수집 (2026-05-21)

- 자동 수집 실행으로 `job_raw/00_Raw` 아래 원문 채용공고와 `json_archive`가 갱신되었습니다.
- `job_wiki/10_Wiki/Facets`와 `job_wiki/20_Meta/Facet_Index.json`가 새 원문을 반영하도록 업데이트되었습니다.
- 수집 대상에 대한 Obsidian facet 페이지가 함께 갱신되었습니다.

영향 범위:
- `job_raw/00_Raw/*`
- `job_raw/00_Raw/index.json`
- `job_raw/00_Raw/json_archive/*`
- `job_wiki/10_Wiki/Facets/*`
- `job_wiki/20_Meta/Facet_Index.json`

## 2026-05-21 7f5e580 - Update README for current workflow

- 루트 README와 서브 프로젝트 README를 현재 워크플로우 기준으로 정리했습니다.
- `job_raw` / `job_core` / `job_career`의 역할을 다시 설명하고, 실제 실행 경로를 문서화했습니다.
- GitHub Actions가 현재 구조와 맞물려 동작한다는 점을 문서에 반영했습니다.

영향 파일:
- `README.md`
- `job_career/README.md`
- `job_raw/README.md`

## 2026-05-21 361bf70 - Refine staged matching flow

- 1차 분석과 최종 추천의 책임을 분리했습니다.
- LLM은 초기 키워드 후보 생성에 사용하고, follow-up 판정에는 Python 로직을 함께 사용하도록 조정했습니다.
- 최종 추천 단계는 Python-only로 처리되도록 분리했습니다.
- 매칭 점수는 키워드 개수보다 카테고리 히트 개수를 기준으로 계산하도록 변경했습니다.
- 초기 분석에서는 추천 기업을 숨기고, 분류 선택 후에만 최종 추천을 보여주도록 UI를 정리했습니다.
- README 문서도 새 단계형 흐름에 맞게 갱신했습니다.

영향 파일:
- `README.md`
- `job_career/README.md`
- `job_career/frontend/script.js`
- `job_career/src/career_agent/pipeline.py`

## 2026-05-21 de0a3d8 - Document job career dependencies

- `job_career` 실행에 필요한 런타임 패키지를 `pyproject.toml`에 명시했습니다.
- `flask`, `flask-cors`, `python-dotenv`를 의존성에 추가했습니다.
- 루트 README와 `job_career/INSTALL.md`에 설치 순서와 패키지 구성을 반영했습니다.
- 공통 수집 패키지와 `job_raw` 패키지 설치 흐름을 문서화했습니다.

영향 파일:
- `job_career/pyproject.toml`
- `README.md`
- `job_career/INSTALL.md`

## 요약

- 수집 파이프라인은 `job_raw` 중심 구조로 정리되었습니다.
- Wiki 변환은 `job_core/scripts/wiki_generator.py`가 담당합니다.
- `job_career`는 단계형 분석 구조로 바뀌었고, 최종 추천은 Python 점수화가 담당합니다.
- 관련 문서, 워크플로우, 의존성 선언까지 현재 구조에 맞게 정리되었습니다.
