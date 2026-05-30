# 프로젝트 변경 기록

기준: 2026-05-21 작업 내역을 커밋 순서대로 정리했습니다.

## 프로젝트 변화 흐름 요약

아래는 이번 대화에서 진행한 전체 변경 과정을 작업 순서대로 정리한 메모입니다.

### 1) raw 수집 중심 구조로 재정리

- `job_raw`의 수집 기준을 NCS 하드코딩에서 공고 원문 필드 중심으로 바꿨습니다.
- `ncsCdNmLst`, `hireTypeNmLst`, `recrutSeNm`, `acbgCondNmLst`, `workRgnNmLst`, `aplyQlfcCn`, `prefCondCn`, `prefCn`, `scrnprcdrMthdExpln` 같은 원문 태그를 그대로 보존하도록 수정했습니다.
- 상세 수집 조건도 NCS 필터가 아니라 최근성/호출 상한 기준으로 바꿨습니다.
- `job_raw/config.py`는 환경변수 기반으로 정리하고, 불필요한 고정 필터 값들을 제거했습니다.

### 2) raw 마크다운과 아카이브 확장

- `job_raw/formatter.py`에서 원문 태그와 추출된 태그를 마크다운 frontmatter에 포함하도록 바꿨습니다.
- `job_raw/scripts/harvester.py`는 수집, 저장, 아카이빙만 담당하도록 단순화했습니다.
- 저장된 raw 파일은 `00_Raw`와 `json_archive`를 함께 유지하는 구조로 맞췄습니다.

### 3) facet 기반 2차 분류 위키 생성

- `job_core/scripts/wiki_generator.py`를 raw 기반 facet 생성기로 바꿨습니다.
- `job_wiki/10_Wiki/Facets`와 `job_wiki/20_Meta/Facet_Index.json`를 생성하도록 만들었습니다.
- NCS, 고용형태, 채용구분, 학력, 지역, 응시자격, 우대사항, 전형방법 등 2차 분류 축을 raw 데이터에서 직접 만들도록 정리했습니다.
- 기존 분석/온톨로지/재분석 계열 스크립트와 설정 파일은 삭제했습니다.

### 4) 불필요한 파일과 문서 정리

- `job_core`에 남아 있던 분석, 온톨로지, 재분석, 통계, 복구용 스크립트들을 삭제했습니다.
- `job_raw`의 임시/보조 스크립트와 `__pycache__`도 제거했습니다.
- 루트 README와 `job_raw` 문서를 새 구조에 맞게 다시 썼습니다.
- `job_career`는 UI이므로 유지하고, 그 외 구조만 정리했습니다.

### 5) job_career의 추천 흐름을 facet 기반으로 전환

- `job_career/src/career_agent/llm_client.py`를 온톨로지 중심에서 facet index md 중심으로 바꿨습니다.
- LLM 프롬프트는 `Facet_Index.json`으로 관련 facet을 좁힌 뒤, 해당 `index.md`만 넣는 방식으로 정리했습니다.
- `job_career/src/career_agent/pipeline.py`는 facet/raw 색인 기반으로 키워드 검증과 기관 점수화를 하도록 수정했습니다.
- `job_career/src/career_agent/tools/custom_tool.py`는 `Facet_Index.json`과 raw 아카이브를 읽는 방식으로 맞췄습니다.
- `job_career`의 `pyproject.toml`, `INSTALL.md`, `README.md`, `WORKFLOW.md`도 새 흐름에 맞게 고쳤습니다.

### 6) job_career의 환경 로딩과 서버 디버그 정리

- `job_career/src/career_agent/__init__.py`에서 workspace 루트 `.env`를 자동 로드하도록 넣었습니다.
- `job_career/server.py`도 동일하게 `.env`를 직접 읽도록 바꿔, 서버 시작 시점부터 OpenCode Go 키가 보이게 했습니다.
- 서버 로그에 `OPENCODE_API_KEY`, `OPENCODE_BASE_URL`, `LLM_EXTRACT_MODEL` 상태를 마스킹해서 남기도록 했습니다.
- `main_batch.py`와 서버 subprocess 경로도 함께 검증했습니다.

### 7) OpenCode Go 설정 확정

- OpenCode Go 공식 문서를 기준으로 엔드포인트를 `https://opencode.ai/zen/go/v1/chat/completions`로 맞췄습니다.
- 모델은 `deepseek-v4-flash`를 사용하도록 지정했습니다.
- `reasoning_effort`는 `low`로 두고, 추출 토큰 상한은 기본 8192로 올렸습니다.
- facet 컨텍스트가 들어가면 1024 토큰에서는 reasoning만 나오던 문제를 확인했고, 더 큰 토큰 예산에서 final JSON 배열이 실제로 반환되는 것도 검증했습니다.

### 8) 검증과 배포

- `job_career` conda 환경에서 editable install과 import 스모크 테스트를 성공시켰습니다.
- 서버 실행 시 OpenCode Go 키가 실제로 읽히는 것도 확인했습니다.
- 최종 변경분은 GitHub `main` 브랜치에 푸시했습니다.

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

## 2026-05-30 - 핵심 의도 가중치와 순위 표시 정리

- `job_career/src/career_agent/llm_client.py`에서 LLM 추출 결과를 `core_keywords`, `support_keywords`, `follow_up_keywords`로 나누는 구조를 추가했습니다.
- `job_career/src/career_agent/pipeline.py`는 core 6배, support 3배, follow-up 1배로 가중치를 반영하고, 정렬 기준은 `raw_score` 중심으로 바꿨습니다.
- `job_career/src/career_agent/pipeline.py`의 추천 흐름을 core → support → follow_up 3단계 후보 좁힘으로 바꿨습니다.
- 1차/2차 분류에서 후보가 0개면 전체 기업으로 확장하지 않고, 맞춤 기업 없음 메시지로 종료하도록 정리했습니다.
- 0개 종료 문구를 더 사용자 친화적으로 다듬고, 핵심 조건을 조금 넓혀 다시 시도하도록 안내했습니다.
- 1차+2차 분류 결과가 1~5개면 follow 단계 없이 바로 공고를 보여주고, 6개 이상일 때만 3차 follow 필터로 넘어가도록 바꿨습니다.
- stage별 후보 파일 제한이 실제 점수화에 반영되도록 수정해서, 필터링된 공고만 추천되도록 바로잡았습니다.
- 초기 단계에서는 기존대로 추천 기관을 숨기고 follow-up 질문만 보여주는 흐름은 유지했습니다.
- `job_career/frontend/script.js`는 퍼센트 중심 표시 대신 `1순위`, `2순위` 같은 순위 중심 표시로 바꿨습니다.
- `job_career/server.py`로 실행되는 터미널 로그에는 핵심/보조/후속 키워드와 최종 추천 순위를 함께 남기도록 정리했습니다.
- 디버그 확인용으로만 쓰이던 프론트엔드 패널은 제거하고, 확인 경로를 백엔드 로그로 통일했습니다.

영향 파일:
- `job_career/src/career_agent/llm_client.py`
- `job_career/src/career_agent/pipeline.py`
- `job_career/frontend/script.js`
- `job_career/frontend/index.html`
- `job_career/README.md`
- `job_career/WORKFLOW.md`

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
