# 프론트엔드 개발 가이드

## 📁 파일 구조

```
frontend/
├── index.html          # 메인 HTML (멀티뷰 SPA)
├── styles.css          # 스타일시트 (라이트/다크 모드)
├── script.js           # JavaScript 로직
└── README.md           # 이 파일
```

## 🚀 빠른 시작

### 1. 백엔드 서버 시작

```bash
cd job_career
python server.py
```

출력: `서버 시작: http://localhost:5000`

### 2. 브라우저에서 접속

```
http://localhost:5000
```

---

## 🛠️ 기술 스택

- **HTML5**: 멀티뷰 SPA 구조 (4개 뷰: home/analyze/followup/result)
- **Tailwind CSS v3**: 유틸리티 클래스 (CDN)
- **Lucide Icons**: SVG 아이콘 라이브러리 (CDN)
- **Vanilla JavaScript**: Fetch API로 백엔드 통신
- **CSS 커스텀 속성**: 라이트/다크 모드 대응

---

## 🎨 디자인 시스템

### 색상 팔레트 (CSS 변수)

```css
--navy: #0f172a;       /* 진한 네이비 */
--blue: #1d4ed8;       /* 주 포인트 */
--line: #e2e8f0;       /* 테두리 */
--muted: #64748b;      /* 보조 텍스트 */
```

### 다크 모드

시스템 설정(`prefers-color-scheme: dark`)을 자동 감지하여 전체 UI가 어두운 테마로 전환됩니다. 별도 토글 불필요.

### 접근성

- `prefers-reduced-motion` 지원 — 모션 민감 사용자용 애니메이션 제거
- 모달 ESC 닫기 지원
- 스크롤 복원 (세션 스토리지 기반)

---

## 💡 JavaScript 주요 함수

### 뷰 관리
```javascript
showPage(pageName)          // home/analyze/followup/result 전환
beginNewAnalysisSession()   // 새 분석 세션 시작
resetAnalysisView(msg)      // 분석 뷰 초기화
```

### API 통신
```javascript
requestAnalysis({ phase, supplementalSelections })
  // POST /api/analyze 호출 (AbortController로 60s 타임아웃)
openArchiveModal(file, institution)
  // POST /api/archive 호출 (원문 모달)
```

### UI 상태
```javascript
showLoading(isLoading)      // 로딩 + 5단계 프로그레스 바
showError(message)          // 오류 메시지 + 자동 스크롤
setActiveStep(step)         // 워크플로우 1/2/3단계 표시
```

### 결과 렌더링
```javascript
renderResults(report)               // 추천 카드 + 비교표 + 요약
renderFollowUpQuestions(questions)  // follow-up 질문 카드
updateSelectedSummary()             // 선택한 조건 실시간 요약
```

### 유틸리티
```javascript
escapeHtml(value)           // XSS 방지 HTML 이스케이프
escapeAttr(value)           // 속성값 이스케이프
getMatchRate(item)          // 매칭률 정규화 (0-100)
buildRecommendationReasons() // 추천 이유 자동 생성
```

---

## 🔌 API 연결

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/analyze` | POST | 분석 실행 (프로필 + 선택 조건) |
| `/api/archive` | POST | 원문 공고 불러오기 |

### 요청 예시
```json
POST /api/analyze
{
  "profile": "저는 병원 직원입니다...",
  "supplemental_selections": { "region": ["서울"] },
  "analysis_session_id": "uuid",
  "analysis_phase": "initial"
}
```

### 응답 예시
```json
{
  "status": "success",
  "data": {
    "recommended_institutions": [
      { "institution": "국립암센터", "match_rate": 96, "matched_keywords": [...], "files": [...] }
    ],
    "follow_up_questions": [
      { "category": "region", "prompt": "...", "options": [...] }
    ]
  }
}
```

---

## 📱 반응형 디자인

| 브레이크포인트 | 대상 | 레이아웃 |
|--------------|------|---------|
| < 640px | 모바일 | 1열, 버튼 전체 너비 |
| 640-1023px | 태블릿 | 1-2열 혼합 |
| 1024px+ | 데스크톱 | 2-3열 그리드 |

---

## 🔒 보안

- 모든 동적 콘텐츠 `escapeHtml()` 처리 (XSS 방지)
- 모달 외부 클릭/ESC 닫기
- 네트워크 요청 60초 타임아웃 (AbortController)
- Follow-up 세션 5분 자동 타임아웃

---

## 🧪 테스트

```bash
# API 단일 테스트
curl -X POST http://localhost:5000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"profile": "저는 병원 직원입니다.", "analysis_phase": "initial"}'
```

---

**개발 완료!** 🎉
