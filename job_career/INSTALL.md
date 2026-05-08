# 설치 가이드 (간단)

이 문서는 이 저장소를 빠르게 로컬에서 실행하기 위한 최소 설치/환경설정 절차를 정리합니다. 주로 Python 가상환경 생성, 필수 패키지(예: `crewai`) 설치, 환경변수 예시를 다룹니다.

## 요구사항

- Python 3.12 이상
- Git
- (선택) Conda / (대체) venv
- (선택) Node.js — 프론트엔드 정적 서버 테스트용

## 가상환경 생성

### Conda (권장)

```powershell
conda create -n job_career python=3.12 -y
conda activate job_career
```

### venv (Windows PowerShell 예시)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

## 의존성 설치

프로젝트 루트에서 다음을 실행하면 `pyproject.toml`에 정의된 의존성이 설치됩니다:

```powershell
pip install -e .
```

또는 최소한 직접 필요한 패키지들만 설치하려면:

```powershell
pip install crewai langchain-community flask flask-cors pyyaml
```

> 참고: `crewai`가 사내/프라이빗 패키지인 경우 내부 패키지 인덱스 또는 로컬 경로를 사용하여 설치하세요.

## 프론트엔드 (선택)

간단히 정적 파일을 서비스하려면:

```powershell
# npm 또는 간단한 정적 서버를 사용
npm install -g http-server
cd frontend
http-server -p 5000
```

또는 기존 Flask 서버(`python server.py`)를 그대로 실행해도 프론트엔드가 서빙됩니다.

## 필수 환경변수 (예시)

루트에 `.env` 파일을 만들어 환경변수를 관리하거나, OS 환경변수로 설정하세요. **실제 키 값은 안전하게 보관**하시기 바랍니다.

```
# LLM 제공자 키
GROQ_API_KEY=your_groq_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
NVIDIA_API_KEY=your_nvidia_api_key_here

# 모델/토큰/타임아웃/동시성 설정 (기본값은 코드에서 정의됨)
CAREER_AGENT_FAST_MODEL=groq/llama-3.3-70b-versatile
CAREER_AGENT_SMART_MODEL=deepseek-ai/deepseek-v4-pro
CAREER_AGENT_MAX_TOKENS=128
CAREER_AGENT_FAST_TIMEOUT=20
CAREER_AGENT_CONCURRENCY_WAIT=20
CAREER_AGENT_MAX_CONCURRENCY=1
CAREER_AGENT_USE_SMART_EVALUATOR=0
CAREER_AGENT_ALLOW_MODEL_OVERRIDE=0

# (선택) 로그/데이터 경로 환경변수
# JOB_WIKI_DIR=./job_wiki
```

코드에서 사용되는 주요 환경변수(참고):

- `GROQ_API_KEY`, `OPENAI_API_KEY`, `NVIDIA_API_KEY` — API 키
- `CAREER_AGENT_FAST_MODEL`, `CAREER_AGENT_SMART_MODEL` — 기본 모델 이름
- `CAREER_AGENT_MAX_TOKENS`, `CAREER_AGENT_FAST_TIMEOUT` 등 — 호출 제한/타임아웃
- `CAREER_AGENT_MAX_CONCURRENCY`, `CAREER_AGENT_CONCURRENCY_WAIT` — 동시성 제어
- `CAREER_AGENT_USE_SMART_EVALUATOR` — 스마트 평가자 사용 여부

## 데이터/색인

- 색인 파일: `job_wiki/20_Meta/Wiki_Index.json` (필수)
- 원본 아카이브: `job_wiki/00_Raw/` 디렉토리

이 파일들이 없으면 도구(예: `WikiReadOnlyTool`)가 정상 동작하지 않을 수 있습니다.

## 서버 실행

```powershell
python server.py
# 또는 (프로젝트 패키지로 설치했다면)
# job-career
```

실행 후 기본적으로 `http://localhost:5000/` 에 프론트엔드와 API가 열립니다.

## 자주 발생하는 문제 및 해결 팁

- LLM RateLimit / TPM 제한: 더 작은 모델을 사용하거나 `CAREER_AGENT_MAX_TOKENS` 값을 낮추세요.
- JSON 파싱 실패(표준출력에 로그 섞임): `main_batch.py`는 로그를 `stderr`로 보내고, `stdout`에는 마지막 JSON 블랍만 남기도록 구성되어 있습니다. `python server.py`로 실행하면 서버 쪽에서 안전하게 처리합니다.
- `crewai` 등 사내 패키지가 설치되지 않을 경우 내부 PyPI 또는 로컬 wheel 파일을 사용하세요.

## 추가 참고

- 의존성 목록: `pyproject.toml`의 `[project].dependencies` 항목을 따릅니다.
- 로그: `job_wiki/20_Meta/llm_calls.csv` 에 LLM 호출 기록이 쌓입니다.

---

필요하시면 이 설치 가이드를 `SETUP_GUIDE.md`에 병합하거나, `requirements.txt` 또는 Dockerfile/CI 설정을 추가해 드리겠습니다.
