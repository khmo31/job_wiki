# Job Wiki — 채용공고 자동 수집 · Wiki 변환 · 매칭

공공기관 채용공고를 ALIO API로 자동 수집하고, LLM 기반 분석을 통해 Obsidian Wiki로 구조화하며, 사용자 프로필과 매칭하는 3단계 파이프라인입니다.

## 디렉토리 구조

```
job_wiki/
├── job_raw/                    # Step 1-2: 수집 + Wiki 변환 파이프라인
│   ├── scripts/
│   │   ├── main.py             #   배치 실행기
│   │   ├── harvester.py        #   수집 → 분석 → 저장
│   │   ├── wiki_generator.py   #   Raw → Wiki 변환
│   │   ├── merge_ontology.py   #   신규 키워드 → Ontology 자동 병합
│   │   ├── recover_markdown.py #   기존 아카이브에서 .md 복구 (일회성)
│   │   └── stats_visualizer.py #   통계 시각화
│   ├── fetcher.py              #   ALIO API 호출
│   ├── analyzer.py             #   직무 분석 (regex + 선택적 LLM)
│   ├── formatter.py            #   마크다운 렌더링
│   ├── writer.py               #   파일 저장 + 인덱싱
│   ├── config.py               #   설정 (API 키, 모델, NCS 필터)
│   ├── utils.py                #   유틸리티 (파일명 생성, ID 추출)
│   ├── 00_Raw/                 #   단일 진실 공급원
│   │   ├── index.json          #   545+ entries: ALIO ID → 파일명 매핑
│   │   ├── json_archive/       #   415 files: 원본 JSON + 분석 결과
│   │   └── *.md                #   415 files: 마크다운 채용공고
│   └── docs/README.md          #   상세 기술 문서
│
├── job_wiki/                   # Obsidian 지식 그래프 (최종 Wiki 출력물)
│   ├── 00_Raw → ../job_raw/00_Raw/  # 심볼릭 링크
│   ├── 10_Wiki/
│   │   ├── Analysis/           # 417 files: LLM 분류된 직무 분석 페이지
│   │   └── Entities/
│   │       ├── Companies/      # 122 files: 기관 프로필
│   │       └── Skills/         # 829 files: 역량/기술 정의
│   ├── 20_Meta/
│   │   ├── Wiki_Index.json     # 검색용 색인 (417 entries)
│   │   ├── Ontology_Map.json   # 키워드 동의어 매핑 (239 키워드)
│   │   ├── Suggested_Keywords.json  # LLM 제안 신규 키워드 (검토 필요)
│   │   ├── Graph_State.json    # 그래프 상태
│   │   └── Harvest_Log.json    # 수집 로그
│   └── .obsidian/              # Obsidian 설정
│
├── job_career/                 # Step 3: 매칭 엔진
│   ├── server.py               # 웹 서버
│   ├── frontend/               # HTML/JS/CSS 대시보드
│   └── src/career_agent/
│       ├── pipeline.py         # 매칭 파이프라인 (LLM→regex fallback)
│       ├── llm_client.py       # 경량 LLM 클라이언트 (Groq/OpenAI/NVIDIA)
│       ├── main_batch.py       # 배치 실행
│       └── tools/
│           └── custom_tool.py  # OntologyCheck + WikiSearch
│
└── .github/workflows/
    └── harvest.yml             # CI/CD: 주간 자동 수집 + Wiki 변환
```

## 현재 데이터 현황 (2026-05-19 기준)

| 항목 | 개수 | 상태 |
|------|------|------|
| 수집된 공고 (index.json) | 547 | ✅ |
| JSON 아카이브 | 417 | ✅ (415 with analysis) |
| 00_Raw 마크다운 | 415 | ✅ 복구 완료 |
| Wiki Analysis 페이지 | 417 | ✅ |
| Companies 프로필 | 122 | ✅ Analysis 기반 재생성 |
| Skills 정의 | 829 | ✅ Analysis 기반 재생성 |
| Wiki_Index 검색 엔트리 | 417 | ✅ |
| Ontology 키워드 | 239 | ✅ |
| CI/CD workflow | — | ✅ 매주 월 09:00 KST |

## 3단계 파이프라인

### Step 1: 수집 (Harvester)
- `fetcher.py`가 ALIO 공공데이터 API에서 채용공고 목록 수집
- NCS 기반 필터링으로 세부 공고 선별 (DETAIL_KEYWORDS 매칭)
- `analyzer.py`가 regex + 선택적 LLM(Groq/OpenAI/NVIDIA)으로 직무 DNA 추출
- 결과: `00_Raw/{날짜}_{ID}_{회사}_{제목}.md` + `json_archive/`에 원본+분석 저장

### Step 2: Wiki 변환 (wiki_generator.py)
- `00_Raw/index.json`의 신규 항목 감지 → `10_Wiki/Analysis/`에 위키 생성
- `Wiki_Index.json` 업데이트 (점수화 기반 검색 인덱스)
- LLM이 새 기술 키워드 발견 시 `Suggested_Keywords.json`에 제안

### Step 3: 매칭 (job_career/pipeline.py)
- **1순위**: LLM 키워드 추출 → Ontology 검증 → Wiki Index 점수화
- **2순위**: regex + Ontology fallback (API 키 없을 때)
- 결과: 사용자 프로필 기반 상위 5개 기관 추천

## LLM 의존성

| 단계 | LLM 역할 | API 키 없으면? |
|------|----------|----------------|
| Harvester 분석 | 새 기술 감지, 모호한 직무 분류 | regex only (정확도↓) |
| Wiki 변환 | 키워드 매핑, 신규 온톨로지 제안 | 기본 분류 only |
| 매칭 | 자연어→키워드 추출 | regex+Ontology (fallback) |

**LLM은 옵션** — 키 없어도 파이프라인은 동작합니다.

### LLM 제공자 우선순위

1. **OpenCode Go** (`OPENCODE_API_KEY`) — `deepseek-v4-flash`, $0.14/M input, rate limit 없음
2. Groq (`GROQ_API_KEY`) — `llama-3.3-70b`, 30 RPM 제한
3. OpenAI (`OPENAI_API_KEY`) — `gpt-4o-mini`
4. NVIDIA (`NVIDIA_API_KEY`) — `deepseek-ai/deepseek-v4-flash`

## 빠른 시작

```bash
# 1. Python venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. 환경변수 설정 (선택)
export OPENCODE_API_KEY="sk-..."   # LLM 분석용 (OpenCode Go, deepseek-v4-flash)
export ALIO_API_KEY="..."         # 실제 ALIO API 수집용

# 3. 수집 실행 (모의 데이터)
cd job_raw
python scripts/main.py --days 7

# 4. Wiki 변환
python scripts/wiki_generator.py

# 5. 온톨로지 병합
python scripts/merge_ontology.py
```

## GitHub Actions (CI/CD)

매주 월요일 09:00 KST 자동 실행:
1. 만료 공고 정리 (`cleanup_expired.py`)
2. 채용공고 수집 (`harvester.py`)
3. Wiki 변환 (`wiki_generator.py`)
4. 온톨로지 자동 병합 (`merge_ontology.py`)
5. 변경사항 커밋 및 푸시

### GitHub Secrets 설정

| Secret | 용도 | 필수 |
|--------|------|------|
| `ALIO_API_KEY` | 실제 ALIO API 호출 | 수집 시 필수 |
| `OPENCODE_API_KEY` | LLM 분석 (OpenCode Go, deepseek-v4-flash) | 권장 |
| `GROQ_API_KEY` | Groq 대체 (fallback) | 선택 |
| `OPENAI_API_KEY` | OpenAI 대체 (fallback) | 선택 |
| `NVIDIA_API_KEY` | NVIDIA 대체 (fallback) | 선택 |

## 주요 버그 수정 (2026-05-19)

1. **save_markdown() 무한 스킵 버그** — `analyze_objective_dna()`가 `save_markdown()`보다 먼저 index.json에 alio_id를 등록하여 `exists_for_id()` 체크가 항상 True를 반환, .md 파일이 단 하나도 저장되지 않던 문제 수정. `writer.py`의 `save_markdown()`이 index 존재 여부 대신 실제 파일 존재 여부를 체크하도록 변경.

2. **raw.list 데이터 구조 불일치** — ALIO API의 raw 데이터가 `{"list": {...}, "detail": {...}}` 형태로 중첩되어 있었으나, `wiki_generator.py`와 `formatter.py`가 flat 구조 가정. `raw.list`와 flat 구조를 모두 지원하도록 fallback 로직 추가.

3. **Company/Skill 스텁 파일** — 실 분석 데이터 없이 빈 템플릿으로 생성된 102개 Company, 200개 Skill 파일을 실제 Analysis 데이터 기반 프로필로 교체.

4. **Graph_State/Harvest_Log 구식** — 실제 데이터와 불일치하던 메타 파일 업데이트.

## 라이선스

Private — khmo31
