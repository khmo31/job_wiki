# 프론트엔드 개발 가이드

## 📁 파일 구조

```
frontend/
├── index.html          # 메인 HTML (UI 구조)
├── styles.css          # 스타일시트
├── script.js           # JavaScript 로직
└── README.md           # 이 파일
```

## 🚀 빠른 시작

### 1. 백엔드 서버 시작

```bash
python server.py
```

출력: `서버 시작: http://localhost:5000`

### 2. 브라우저에서 접속

```
http://localhost:5000
```

또는

```
http://localhost:5000/static/index.html
```

---

## 🛠️ 기술 스택

- **HTML5**: 구조 (시맨틱 요소)
- **CSS3**: 반응형 그리드 레이아웃
- **Vanilla JavaScript**: Fetch API로 백엔드 통신

---

## 💡 JavaScript 주요 함수

### API 통신
```javascript
handleAnalyze()  // "분석하기" 클릭 → POST /api/analyze 호출
```

### UI 상태
```javascript
showLoading()       // 로딩 상태 표시
hideLoading()       // 로딩 상태 숨김
showError(message)  // 오류 메시지 표시
showResults(data)   // 결과 카드 렌더링
```

### 입력 처리
```javascript
handleInput()       // 입력 길이 제한 (5000자)
updateAnalyzeButtonState()  // 버튼 활성화/비활성화
```

---

## 🎨 스타일 커스터마이징

### 색상 변수 (CSS 루트)
```css
--primary-color: #007bff;       /* 주 색상 */
--success-color: #28a745;       /* 성공 (점수 배지) */
--danger-color: #dc3545;        /* 오류 */
--warning-color: #ffc107;       /* 경고 */
--light-bg: #f8f9fa;            /* 밝은 배경 */
```

### 반응형 브레이크포인트
- 데스크톱: 1200px+
- 태블릿: 768px - 1199px
- 모바일: < 768px

---

## 🔌 API 연결

### 기본 경로 (localhost)
```javascript
const API_URL = '/api/analyze';
```

### 원격 서버 연결 (필요 시)
```javascript
const API_URL = 'https://your-domain.com/api/analyze';
```

---

## 🧪 테스트

### 1. 입력 유효성 테스트
- 빈 입력 → "분석하기" 버튼 비활성화
- 5000자 초과 입력 → 자동 제한

### 2. API 호출 테스트 (curl)
```bash
curl -X POST http://localhost:5000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"profile": "저는 병원 직원입니다."}'
```

### 3. 결과 표시 테스트
- 결과 카드 5개 표시 확인
- 키워드 태그 표시 확인
- 점수 배지 표시 확인

---

## 📱 반응형 테스트

### 데스크톱 (F12 → Toggle device toolbar)
```
화면 너비: 1200px+
예상: 2열 그리드 (입력/결과 나란히)
```

### 태블릿
```
화면 너비: 768px - 1199px
예상: 1열 스택 (입력 위, 결과 아래)
```

### 모바일
```
화면 너비: < 768px
예상: 1열 스택, 버튼 세로 정렬
```

---

## 🔒 보안

### XSS 방지
```javascript
escapeHtml(text)  // HTML 특수문자 이스케이프
```

모든 동적 콘텐츠는 이 함수로 처리됨.

### CORS
Flask 서버에서 `flask-cors` 사용하여 모든 도메인 허용 (개발 용도).
배포 시 도메인 제한 필요.

---

## 🐛 디버깅 팁

### 브라우저 콘솔 열기
```
F12 또는 Ctrl+Shift+I
```

### API 응답 확인
```javascript
// script.js의 fetch() 부분에 console.log 추가
console.log('응답:', data);
```

### 네트워크 탭
```
F12 → Network → "분석하기" 클릭
→ POST /api/analyze 확인
```

---

## 📝 예시 프로필

```
저는 3년 동안 병원에서 원무과 행정 직원으로 일했습니다. 환자 데이터를 다루다 보니 의료 행정 지식과 의료정보 보호 정책 수립 쪽에 관심이 생겼고, 관련 경험도 쌓았습니다. 공공기관 쪽으로 이직하고 싶습니다.
```

---

## 🚀 프로덕션 배포

### 1. Flask 정적 파일 위치 확인
```
frontend/index.html
frontend/styles.css
frontend/script.js
```

모두 `frontend/` 디렉토리에 있어야 함.

### 2. CORS 설정
```python
# server.py
CORS(app, resources={
    r"/api/*": {"origins": ["https://your-domain.com"]}
})
```

### 3. 환경 변수
```python
API_URL = os.getenv('API_URL', '/api/analyze')
```

---

## 📚 참고 자료

- [API 스펙](../API_SPEC.md)
- [Flask 문서](https://flask.palletsprojects.com/)
- [MDN Web Docs](https://developer.mozilla.org/)

---

**개발 완료!** 🎉
