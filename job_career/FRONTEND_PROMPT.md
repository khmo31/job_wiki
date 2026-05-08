# 프론트엔드 UI 개발 - 통합 바이브코딩 프롬프트

## 📋 프로젝트 개요

**목표:** 커리어 판단 에이전트의 프론트엔드 UI 개발

**백엔드 정보:**
- Flask 서버: `http://localhost:5000`
- API 엔드포인트: `POST /api/analyze`
- 응답 형식: JSON
- 처리 시간: 30~50초 (LLM 호출 포함)

---

## 🏗️ 폴더/파일 구조

```
job_career/
├── server.py                    ← Flask 서버 (이미 생성됨)
├── frontend/                    ← 프론트엔드 디렉토리
│   ├── index.html               ← 기본 HTML (UI 디자인 대상)
│   ├── styles.css               ← 스타일시트 (UI 디자인 대상)
│   ├── script.js                ← JavaScript 로직 (UI 디자인 대상)
│   └── README.md                ← 프론트엔드 개발 가이드
├── API_SPEC.md                  ← API 스펙 문서
└── ...
```

---

## 📡 API 계약

### 요청
```javascript
POST /api/analyze
Content-Type: application/json

{
  "profile": "사용자 커리어 프로필 (자유 텍스트, 여러 줄 가능)"
}
```

### 응답 (성공, 200)
```javascript
{
  "status": "success",
  "data": {
    "recommended_institutions": [
      {
        "institution": "기관명",
        "file": "파일명.md",
        "score": 13,
        "matched_keywords": ["키워드1", "키워드2"]
      },
      // ... 최대 5개
    ]
  }
}
```

### 응답 (오류)
```javascript
{
  "status": "error",
  "error": "오류 메시지"
}
```

---

## 🎨 UI/UX 요구사항

### 1. 입력 영역
- **텍스트 에리어**: 커리어 프로필 입력 (여러 줄, 최소 200px 높이)
- **버튼**:
  - "분석하기" (비활성화: 입력 비어있을 때)
  - "초기화" (입력 초기화)
  - "예시 불러오기" (기본 예시 텍스트 자동 입력, 선택사항)
- **텍스트**: 입력 가이드 및 예시 표시

### 2. 결과 표시 영역
- **로딩 상태**:
  - 분석 중 표시 (스피너/프로그레스 바)
  - "분석 중입니다... (최대 60초)"
  
- **성공 결과**:
  - 추천 기관을 카드 형식으로 표시
  - 각 카드 정보:
    - 기관명 (굵음, 크게)
    - 점수 (숫자 또는 별 표시)
    - 매칭 키워드 (태그 형식)
    - 파일명 (작은 텍스트)
  - 카드 정렬: 점수 내림차순
  
- **오류 메시지**:
  - 빨간색 배경, 명확한 오류 텍스트
  - "다시 시도" 버튼

### 3. 반응형 디자인
- 데스크톱 (1200px+): 2열 또는 3열 카드 레이아웃
- 태블릿 (768px-1199px): 2열 카드
- 모바일 (<768px): 1열 카드

### 4. 추가 기능 (선택사항)
- **다크 모드** 토글
- **결과 저장** (JSON/CSV 다운로드)
- **결과 공유** (링크 복사, SNS 공유)
- **히스토리** (최근 검색 기록)

---

## 💻 프론트엔드 기술 스택 가이드

### 기본 구성 (권장)
- HTML5 + CSS3 + Vanilla JavaScript
- Fetch API (HTTP 통신)
- 선택: Tailwind CSS 또는 Bootstrap (스타일링)

### React 사용 시
```bash
npm create vite@latest frontend -- --template react
cd frontend
npm install axios
npm run dev
```

### Vue 사용 시
```bash
npm create vue@latest frontend
cd frontend
npm install axios
npm run dev
```

---

## 🔄 프론트엔드 개발 체크리스트

- [ ] HTML 구조 작성 (입력 폼, 결과 컨테이너)
- [ ] CSS 스타일 적용 (반응형 레이아웃)
- [ ] JavaScript 로직 구현
  - [ ] 입력 검증 (비어있음 체크)
  - [ ] "분석하기" 클릭 → API 호출
  - [ ] 로딩 상태 UI 업데이트
  - [ ] 응답 파싱 및 결과 렌더링
  - [ ] 오류 처리
- [ ] "초기화" 버튼 기능
- [ ] 반응형 테스트 (모바일, 태블릿, 데스크톱)
- [ ] 접근성 (ARIA 라벨, 키보드 네비게이션)

---

## 🚀 로컬 테스트 방법

### 1. 백엔드 시작
```bash
python server.py
# 출력: "서버 시작: http://localhost:5000"
```

### 2. 프론트엔드 개발 서버 시작 (선택)
```bash
cd frontend
npm run dev
# 또는 간단히 index.html을 브라우저에서 열기
```

### 3. 브라우저에서 테스트
```
http://localhost:5000  (Flask 서버가 static/index.html 제공)
또는
http://localhost:3000  (Vite 개발 서버, Vue/React 사용 시)
```

### 4. API 직접 테스트 (선택)
```bash
curl -X POST http://localhost:5000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"profile": "저는 병원에서 일했습니다."}'
```

---

## 📝 예시 프로필 (테스트용)

```
저는 3년 동안 병원에서 원무과 행정 직원으로 일했습니다. 환자 데이터를 다루다 보니 의료 행정 지식과 의료정보 보호 정책 수립 쪽에 관심이 생겼고, 관련 경험도 쌓았습니다. 공공기관 쪽으로 이직하고 싶습니다.
```

---

## 🎯 성공 기준

1. ✅ 프로필 입력 → "분석하기" 클릭 → 백엔드 API 호출
2. ✅ 로딩 중 UI 표시
3. ✅ 응답 수신 후 추천 기관 5개 카드로 표시
4. ✅ 모바일/태블릿/데스크톱 모두 반응형 표시
5. ✅ 오류 발생 시 친화적 오류 메시지 표시

---

## 📚 참고 자료

- API 스펙: `API_SPEC.md`
- 백엔드 코드: `src/career_agent/main.py`, `src/career_agent/main_batch.py`
- Flask 서버: `server.py`

---

## 💡 개발팁

- **CORS 문제 해결**: Flask 앱에서 `flask-cors` 설치 후 `CORS(app)` 추가 (필요 시)
- **로딩 시간**: API는 30~50초 걸리므로 UX에서 충분한 대기 피드백 제공
- **입력 유효성**: 프론트엔드에서 빈 입력 방지, 백엔드에서도 검증
- **응답 캐싱**: 동일 프로필 재분석 시 응답 캐싱 고려 (선택사항)

---

**준비 완료!**  
이 프롬프트를 다른 AI(웹 UI 전문가)에 전달하면 완전한 프론트엔드 UI를 개발할 수 있습니다.
