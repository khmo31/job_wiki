# Job Wiki — 채용공고 자동 수집 · 분석 · 매칭

공공기관 채용공고를 자동으로 수집하고, 직무 분석 결과를 위키로 정리하며, 사용자 프로필과 매칭하는 파이프라인입니다.

## 구조

```
job_wiki/
├── job_raw/           # 채용공고 수집 파이프라인
│   ├── scripts/       # main.py, harvester.py
│   ├── fetcher.py     # ALIO API 호출
│   ├── analyzer.py    # 직무 분석 (regex + 선택적 LLM)
│   ├── formatter.py   # 마크다운 렌더링
│   ├── writer.py      # 파일 저장 및 인덱싱
│   ├── config.py      # 설정
│   └── 00_Raw/        # 수집된 공고 원본 (단일 진실 공급원)
├── job_wiki/          # Obsidian 위키 (지식 그래프)
│   ├── 00_Raw → ../job_raw/00_Raw  # 심볼릭 링크
│   ├── 10_Wiki/       # 분석 결과 + 기업/스킬 엔티티
│   ├── 20_Meta/       # 색인, 온톨로지, 그래프 상태
│   └── .obsidian/     # Obsidian 설정
├── job_career/        # 로컬 매칭 엔진 (LLM 불필요)
│   └── src/career_agent/  # OntologyCheckTool + WikiReadOnlyTool
├── .github/workflows/ # GitHub Actions (주간 자동 수집)
└── requirements.txt   # 의존성 (requests)
```

## 워크플로우

1. **수집**: 주 1회 GitHub Actions가 ALIO API에서 신규 채용공고 수집
2. **분석**: 규칙 기반(regex) + 선택적 LLM으로 직무 DNA 분석
3. **저장**: 수집 결과를 `job_raw/00_Raw/`에 마크다운 + JSON 아카이브로 저장
4. **매칭**: `job_career`가 위키 색인 기반으로 사용자 프로필과 추천 기관 매칭

## 자동 수집 (GitHub Actions)

매주 월요일 09:00 KST에 실행됩니다.
수동 실행: `Actions → 주간 채용공고 수집 → Run workflow`

**실제 ALIO API 사용을 위해 GitHub Secrets 설정:**
- `ALIO_API_KEY`: ALIO 오픈API 키
- `NVIDIA_API_KEY`: LLM 분석용 (선택, 없으면 regex+heuristic 모드)

## 로컬 실행

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 모의 데이터로 수집 테스트
cd job_raw && python scripts/main.py --mock --days 7
```

## 라이선스

Private — khmo31
