# Flask 서버 설정 및 실행 가이드

## 📦 필수 패키지 설치

### 방법 1: pip 직접 설치

```bash
pip install flask flask-cors
```

### 방법 2: pyproject.toml 재설치

```bash
# 가상환경 활성화
.venv\Scripts\activate

# 패키지 재설치 (최신 의존성 포함)
pip install -e .
```

---

## 🚀 서버 실행

### 기본 실행

```bash
python server.py
```

### 출력 예시

```
================================================================================
커리어 판단 에이전트 - Flask 서버
================================================================================

서버 시작: http://localhost:5000
프론트엔드: http://localhost:5000/static/index.html

 API: POST /api/analyze
================================================================================
```

---

## 🌐 브라우저 접속

| 주소 | 설명 |
|------|------|
| `http://localhost:5000/` | 프론트엔드 UI (권장) |
| `http://localhost:5000/static/index.html` | 정적 HTML 직접 접속 |
| `http://localhost:5000/api/health` | 헬스 체크 |

---

## 🧪 API 테스트

### curl로 테스트

```bash
curl -X POST http://localhost:5000/api/analyze \
  -H "Content-Type: application/json" \
  -d "{\"profile\": \"저는 병원에서 일했습니다.\"}"
```

### PowerShell에서 테스트

```powershell
$body = @{profile = "저는 병원에서 일했습니다."} | ConvertTo-Json
Invoke-WebRequest -Uri "http://localhost:5000/api/analyze" `
  -Method POST `
  -Headers @{"Content-Type" = "application/json"} `
  -Body $body
```

### 응답 예시

```json
{
  "status": "success",
  "data": {
    "recommended_institutions": [
      {
        "institution": "경북대학교병원",
        "file": "20260429_경북대학교병원_299972.md",
        "score": 13,
        "matched_keywords": ["의료 행정 지식", "의료정보 보호"]
      }
    ]
  }
}
```

---

## ⚙️ 서버 설정

### server.py 주요 설정

```python
# 정적 파일 디렉토리
static_folder = "frontend"

# CORS 허용 도메인
CORS(app)  # 모든 도메인 허용 (개발 용도)

# 포트 및 호스트
app.run(debug=True, host="0.0.0.0", port=5000)
```

### 배포 시 변경 사항

```python
# CORS 제한
CORS(app, resources={
    r"/api/*": {"origins": ["https://your-domain.com"]}
})

# 디버그 모드 비활성화
app.run(debug=False, host="0.0.0.0", port=5000)
```

---

## 🐛 문제 해결

### "Address already in use" 오류

포트 5000이 이미 사용 중입니다.

```bash
# 다른 포트 사용
python server.py --port 5001

# 또는 server.py 마지막 줄 수정:
app.run(debug=True, host="0.0.0.0", port=5001)
```

### "Module 'flask' not found" 오류

Flask가 설치되지 않았습니다.

```bash
pip install flask flask-cors
```

### CORS 오류 ("No 'Access-Control-Allow-Origin'" header)

Flask 서버에서 CORS가 활성화되지 않았습니다.

```bash
pip install flask-cors
```

그리고 `server.py`에서 `CORS(app)` 확인.

### 프론트엔드 CSS/JS 로드 안 됨

정적 파일 경로 확인:

```
frontend/
├── index.html
├── styles.css      ← 필수
└── script.js       ← 필수
```

---

## 📊 로그 확인

### 분석 로그 위치

```
20_Meta/llm_calls.csv
```

각 LLM 호출 기록:
- 타임스탬프
- 모델명
- 호출 타입
- 처리 시간
- 토큰 사용량

---

## 🔄 재시작

### 서버 중지

```
Ctrl + C
```

### 서버 재시작

```bash
python server.py
```

---

## 📝 로깅 추가

### Python logging으로 상세 로그 기록

```python
# server.py에 추가
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@app.route("/api/analyze", methods=["POST"])
def analyze():
    logger.info(f"분석 요청: {len(profile)} 자")
    # ...
```

---

## 🚀 프로덕션 배포

### WSGI 서버 사용 (Gunicorn)

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 server:app
```

### Docker 배포

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE 5000

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "server:app"]
```

---

## ✅ 체크리스트

- [ ] Flask 및 flask-cors 설치 완료
- [ ] `python server.py` 실행 가능
- [ ] `http://localhost:5000` 접속 가능
- [ ] 프론트엔드 UI 로드됨
- [ ] API 테스트 성공
- [ ] 프로필 입력 → 분석 결과 표시 확인

---

**준비 완료!** 🎉
