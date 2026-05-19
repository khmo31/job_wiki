# Job Wiki — 채용공고 자동 수집 · Wiki 변환 · 매칭

공공기관 채용공고를 ALIO API로 자동 수집하고, 원문 태그를 바탕으로 Facet Wiki로 구조화하며, 사용자 프로필과 매칭하는 파이프라인입니다.

## 디렉토리 구조

```
job_wiki/
├── job_raw/                    # Step 1: 수집 + 원문 저장
│   ├── scripts/
│   │   ├── main.py             #   배치 실행기
│   │   └── harvester.py        #   수집 → 저장
│   ├── fetcher.py              #   ALIO API 호출
│   ├── formatter.py            #   마크다운 렌더링
│   ├── writer.py               #   파일 저장 + 인덱싱
│   ├── utils.py                #   유틸리티 (파일명 생성, ID 추출)
│   ├── 00_Raw/                 #   단일 진실 공급원
│   │   ├── index.json          #   ALIO ID → 파일명 매핑
│   │   ├── json_archive/       #   원본 JSON 아카이브
│   │   └── *.md                #   마크다운 채용공고
│   └── docs/README.md          #   상세 기술 문서
│
├── job_wiki/                   # Obsidian 지식 그래프 (최종 Wiki 출력물)
│   ├── 00_Raw → ../job_raw/00_Raw/  # 심볼릭 링크
│   ├── 10_Wiki/
│   │   └── Facets/             # 2차 분류 허브
│   ├── 20_Meta/
│   │   └── Facet_Index.json    # facet 색인
│   └── .obsidian/              # Obsidian 설정
│
├── job_career/                 # UI / 매칭 엔진
│   ├── server.py               # 웹 서버
│   ├── frontend/               # HTML/JS/CSS 대시보드
│   └── src/career_agent/
│       ├── pipeline.py         # 매칭 파이프라인
│       ├── llm_client.py       # 경량 LLM 클라이언트
│       ├── main_batch.py       # 배치 실행
│       └── tools/
│           └── custom_tool.py  # WikiSearch
│
└── .github/workflows/
    └── harvest.yml             # CI/CD: 주간 자동 수집 + Wiki 변환
```

## 현재 데이터 현황 (2026-05-19 기준)

| 항목 | 상태 |
|------|------|
| 수집된 공고 | ✅ |
| JSON 아카이브 | ✅ |
| 00_Raw 마크다운 | ✅ |
| Facet Wiki | ✅ |
| Facet_Index | ✅ |
| CI/CD workflow | ✅ 매주 월 09:00 KST |

## 3단계 파이프라인

### Step 1: 수집 (Harvester)
- `fetcher.py`가 ALIO 공공데이터 API에서 채용공고 목록 수집
- 원문 필드(`ncsCdNmLst`, `hireTypeNmLst`, `recrutSeNm`, `acbgCondNmLst`, `workRgnNmLst`, `aplyQlfcCn`, `prefCondCn`, `prefCn`, `scrnprcdrMthdExpln`)를 그대로 보존
- 결과: `00_Raw/{날짜}_{ID}_{회사}_{제목}.md` + `json_archive/`에 원본 저장

### Step 2: Wiki 변환 (wiki_generator.py)
- `00_Raw/index.json`과 `json_archive/`를 읽어 `10_Wiki/Facets/`에 2차 분류 허브 생성
- `Facet_Index.json` 업데이트

### Step 3: 매칭 (job_career/pipeline.py)
- **1순위**: raw 태그 정규화 → facet 매칭
- **2순위**: 규칙 기반 키워드 fallback
- 결과: 사용자 프로필 기반 추천

## 태그 기반 분류

- 핵심 분류는 원문 필드를 그대로 사용합니다.
- `ncsCdNmLst`, `hireTypeNmLst`, `recrutSeNm`, `acbgCondNmLst`, `workRgnNmLst`, `aplyQlfcCn`, `prefCondCn`, `prefCn`, `scrnprcdrMthdExpln`을 2차 분류 축으로 사용합니다.
- LLM은 기본 파이프라인에서 제외했습니다.

## 빠른 시작

```bash
# 1. Python venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. 환경변수 설정 (선택)
export ALIO_API_KEY="..."         # 실제 ALIO API 수집용

# 3. 수집 실행 (모의 데이터)
cd job_raw
python scripts/main.py --days 7

# 4. Wiki 변환
python scripts/wiki_generator.py

```

## GitHub Actions (CI/CD)

매주 월요일 09:00 KST 자동 실행:
1. 만료 공고 정리 (`cleanup_expired.py`)
2. 채용공고 수집 (`harvester.py`)
3. Wiki 변환 (`wiki_generator.py`)
4. 변경사항 커밋 및 푸시

### GitHub Secrets 설정

| Secret | 용도 | 필수 |
|--------|------|------|
| `ALIO_API_KEY` | 실제 ALIO API 호출 | 수집 시 필수 |
| `GROQ_API_KEY` | LLM 실험용 | 선택 |
| `OPENAI_API_KEY` | LLM 실험용 | 선택 |
| `NVIDIA_API_KEY` | LLM 실험용 | 선택 |

## 주요 버그 수정 (2026-05-19)

1. **save_markdown() 무한 스킵 버그** — `save_markdown()`이 실제 파일 존재 여부를 기준으로 건너뛰도록 수정.

2. **raw.list 데이터 구조 불일치** — ALIO API의 raw 데이터가 `{"list": {...}, ...}` 형태여도 저장·렌더가 동작하도록 fallback 로직 추가.

3. **Facet Wiki 추가** — 원문 태그를 기반으로 2차 분류 허브를 생성하도록 변경.

## 라이선스

Private — khmo31
