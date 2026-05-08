P-Reinforce Harvester Prototype

이 저장소는 공공기관 채용 API(ALIO)로부터 채용공고를 수집해
원본 JSON 아카이브와 함께 YAML frontmatter가 포함된 마크다운을 `00_Raw/`에 저장하고,
경량 규칙과 LLM 분석을 결합해 직무 속성(예: `core_logic`, `latent_skills`)을 추출·정리하는 파이프라인입니다.

프로젝트 구조 변경 안내
- `scripts/`: 실행 스크립트(이전 루트의 실행용 .py 파일들)
- `config/`: 환경 파일(`.env`) 및 설정 관련 보조 파일
- `docs/`: 문서(이 파일)
- 루트: 핵심 모듈(`config.py`, `analyzer.py`, `fetcher.py`, `formatter.py`, `utils.py`, `writer.py`) 및 `00_Raw/`

빠른 시작 (프로젝트 루트에서 실행)
1. 가상환경 활성화

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

2. `.env` 배치

```powershell
# 기본 위치: config/.env (repo will load config/.env automatically)
notepad config\.env
```

3. 샘플 실행

```powershell
.\.venv\Scripts\python.exe scripts\run_reanalyze_2.py
```

4. 배치(재수확) 실행 — `.env`의 `REANALYZE_TARGET`로 제어

```powershell
$env:REANALYZE_TARGET="50"
.\.venv\Scripts\python.exe scripts\reanalyze_force.py
```

중요 설정 요약
- `REANALYZE_TARGET`: 배치 재분석 기본 건수(예: 20)
- `NCS_FILTER_MODE`: `'off'|'soft'|'hard'` — NCS 기반 LLM 호출 필터링
- `FORCE_COMPOSE_CONTEXT`: 공고 컨텍스트 강제 결합 여부
- `FORCE_LLM_OVERRIDE`: LLM 호출 강제화

도움말
- 스크립트는 `scripts/`로 이동되어 있습니다. 루트에서 `python scripts/<script>.py`로 실행하세요.
- `config.py`는 `config/.env`와 루트 `.env`(있는 경우)를 자동으로 로드합니다.

원하시면 제가 바로 `.env` 값을 바꿔 테스트 실행해 드리겠습니다.
