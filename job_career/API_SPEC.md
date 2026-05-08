# 커리어 판단 에이전트 - API 스펙

## 서버 시작

```bash
pip install flask
python server.py
```

서버는 `http://localhost:5000`에서 실행됩니다.

---

## API 엔드포인트

### 1. 분석 요청
**엔드포인트:** `POST /api/analyze`

**요청 헤더:**
```
Content-Type: application/json
```

**요청 본문:**
```json
{
  "profile": "사용자 커리어 프로필 텍스트 (여러 줄 가능)"
}
```

**요청 예시:**
```json
{
  "profile": "저는 3년 동안 병원에서 원무과 행정 직원으로 일했습니다. 환자 데이터를 다루다 보니 의료 행정 지식과 의료정보 보호 정책 수립 쪽에 관심이 생겼고, 관련 경험도 쌓았습니다. 공공기관 쪽으로 이직하고 싶습니다."
}
```

**응답 (성공, 200):**
```json
{
  "status": "success",
  "data": {
    "recommended_institutions": [
      {
        "institution": "충남대학교병원",
        "file": "20260429_충남대학교병원_299968.md",
        "score": 13,
        "matched_keywords": ["의료", "행정"]
      },
      {
        "institution": "한국어촌어항공단",
        "file": "20260428_한국어촌어항공단_299981.md",
        "score": 5,
        "matched_keywords": ["행정", "공공기관"]
      }
    ]
  }
}
```

**응답 (오류, 400-500):**
```json
{
  "status": "error",
  "error": "오류 메시지"
}
```

---

### 2. 헬스 체크
**엔드포인트:** `GET /api/health`

**응답 (200):**
```json
{
  "status": "ok"
}
```

---

## 응답 필드 설명

| 필드 | 타입 | 설명 |
|------|------|------|
| `recommended_institutions` | 배열 | 추천 기관 목록 (최대 5개) |
| `institution` | 문자열 | 기관명 |
| `file` | 문자열 | 분석에 사용된 위키 문서 파일명 |
| `score` | 정수 | 매칭 점수 (높을수록 좋음) |
| `matched_keywords` | 배열 | 매칭된 키워드 목록 (근거) |

---

## 에러 코드

| 상태코드 | 설명 |
|---------|------|
| 400 | 잘못된 요청 (프로필 비어있음) |
| 500 | 서버 오류 / 분석 실패 |
| 504 | 타임아웃 (분석 시간 초과: 2분) |

---

## 라이브 테스트

### curl 예시:
```bash
curl -X POST http://localhost:5000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "profile": "저는 병원에서 행정 직원으로 일했습니다. 공공기관으로 이직하고 싶습니다."
  }'
```

### JavaScript 예시 (fetch):
```javascript
fetch("http://localhost:5000/api/analyze", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    profile: "사용자 프로필..."
  })
})
.then(res => res.json())
.then(data => console.log(data))
.catch(err => console.error(err));
```
