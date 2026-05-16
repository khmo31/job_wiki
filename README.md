# Job Wiki — 채용공고 자동 수집 · Wiki 변환 · 매칭

공공기관 채용공고를 자동으로 수집하고, LLM 기반으로 분석하여 위키로 구조화하며, 사용자 프로필과 매칭하는 3단계 파이프라인입니다.

## 구조

```
job_wiki/                          # 루트 (GitHub Actions 실행 기준)
│
├── job_raw/                       # ── Step 1: 수집 파이프라인
│   ├── scripts/
│   │   ├── main.py                #   배치 실행기
│   │   ├── harvester.py           #   수집 → 분석 → 저장
│   │   └── wiki_generator.py      # ── Step 2: Raw→Wiki 변환
│   ├── fetcher.py                 #   ALIO API 호출
│   ├── analyzer.py                #   직무 분석 (regex + 선택적 LLM)
│   ├── formatter.py               #   마크다운 렌더링
│   ├── writer.py                  #   파일 저장 + 인덱싱
│   ├── config.py                  #   설정
│   └── 00_Raw/                    #   수집된 공고 (단일 진실 공급원)
│       ├── index.json             #   ALIO ID → filename 매핑
│       └── json_archive/          #   원본 JSON + 분석 결과
│
├── job_wiki/                      # Obsidian 지식 그래프
│   ├── 00_Raw → ../job_raw/00_Raw #  심볼릭 링크 (중복 없음)
│   ├── 10_Wiki/
│   │   ├── Analysis/              #  LLM 분류된 직무 분석 페이지
│   │   └── Entities/
│   │       ├── Companies/         #  기관 프로필
│   │       └── Skills/            #  역량/기술 정의
│   ├── 20_Meta/
│   │   ├── Wiki_Index.json        #  검색용 색인 (점수화 기반)
│   │   ├── Ontology_Map.json      #  키워드 동의어 매핑
│   │   ├── Suggested_Keywords.json#  LLM이 제안한 신규 키워드 (검토 필요)
│   │   └── Graph_State.json       #  그래프 상태
│   └── .obsidian/                 # Obsidian 설정
│
├── job_career/                    # ── Step 3: 매칭 엔진
│   └── src/career_agent/
│       ├── pipeline.py            #   매칭 파이프라인
│       ├── llm_client.py          #   경량 LLM 클라이언트 (SDK 불필요)
│       └── tools/
│           ├── OntologyCheckTool  #   키워드 → 표준 온톨로지 검증
│           └── WikiReadOnlyTool   #   Wiki_Index.json 검색
│
├── .github/workflows/
│   └── harvest.yml                #  주간 자동 수집 + Wiki 변환
└── requirements.txt               #  의존성 (requests)
```

## 3단계 파이프라인 상세

### Step 1: 수집 (`job_raw/harvester.py`)
- ALIO API에서 공고 수집 (실제 or 모의)
- `analyzer.py`가 regex + 선택적 LLM으로 직무 DNA 추출
- 결과: `00_Raw/`에 마크다운 저장, `index.json` 업데이트

### Step 2: Wiki 변환 (`wiki_generator.py`) ✅ 신규
- `00_Raw/index.json`의 신규 항목 감지
- `10_Wiki/Analysis/`에 위키 분석 페이지 생성
- `Wiki_Index.json` 업데이트
- **LLM이 새 기술 키워드 발견 시 `Suggested_Keywords.json`에 제안**

### Step 3: 매칭 (`job_career`)
- **사용자 프로필 → LLM 키워드 추출** (1순위, API 키 필요)
- LLM 실패 시 **regex + Ontology** 기반 추출 (2순위)
- 검증된 키워드로 `Wiki_Index.json` 점수화 → 상위 5개 기관 추천

## LLM 의존성

| 단계 | LLM 역할 | API 키 없으면? |
|------|----------|--------------|
| 수집 분석 | 새 기술 감지, 모호한 직무 분류 | regex만 (정확도↓) |
| Wiki 변환 | 키워드 매핑, 신규 온톨로지 제안 | 기본 분류만 |
| 매칭 | 자연어→키워드 추출 | regex+Ontology (부정확) |

**LLM은 옵션** — 키 없어도 파이프라인은 동작하지만 정확도가 떨어집니다.

## 자동 수집 (GitHub Actions)

매주 월요일 09:00 KST 실행. 수동: Actions → `주간 채용공고 수집` → Run workflow

### GitHub Secrets 설정

| Secret | 용도 | 필수 |
|--------|------|------|
| `ALIO_API_KEY` | 실제 ALIO API 호출 | 수집 시 |
| `NVIDIA_API_KEY` | LLM 분석 (analyzer + wiki + matching) | 권장 |
| `OPENAI_API_KEY` | NVIDIA 대체 | 선택 |
| `GROQ_API_KEY` | 매칭 키워드 추출용 | 선택 |

## 로컬 실행

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Step 1: 수집 테스트 (모의)
cd job_raw && python scripts/main.py --mock --days 7

# Step 2: Wiki 변환
cd job_raw && python scripts/wiki_generator.py
```

## 라이선스

Private — khmo31
