P-Reinforce Harvester Prototype

이 저장소는 공공기관 채용 API(ALIO)로부터 채용공고를 수집해
원본 JSON 아카이브와 함께 YAML frontmatter가 포함된 마크다운을 `00_Raw/`에 저장하고,
원문 태그를 그대로 보존해 2차 분류용 facet 위키를 만드는 파이프라인입니다.

핵심 흐름
- `fetcher.py`: ALIO 목록과 상세를 수집
- `formatter.py`: raw 필드와 추출 태그를 마크다운으로 렌더링
- `writer.py`: `00_Raw/`와 `json_archive/` 저장
- `scripts/harvester.py`: 수집 오케스트레이션

빠른 시작
1. 가상환경 활성화

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

2. `.env` 확인

```powershell
notepad config\.env
```

3. 드라이런 실행

```powershell
.\.venv\Scripts\python.exe scripts\main.py --dry-run --days 1 --pages 1
```

4. 실제 수집 실행

```powershell
.\.venv\Scripts\python.exe scripts\main.py --days 7
```

중요 설정 요약
- `ALIO_API_KEY`: 실제 ALIO API 호출에 사용
- `DETAIL_FETCH_WINDOW_DAYS`: 상세 수집 허용 기간
- `DETAIL_MAX_DETAIL_CALLS`: 상세 호출 상한
- `USER_INTERESTS`: 선택적 관심사 필터

도움말
- 루트에서 `python scripts/<script>.py` 형식으로 실행합니다.
- `config.py`는 `config/.env`와 루트 `.env`(있는 경우)를 자동으로 로드합니다.
