# Career Agent 워크플로우

## 매칭 파이프라인 상세

```
사용자 프로필 (자연어)
    │
    ├── Step 1: 키워드 추출
    │   ├── LLM 경로 (1순위)
    │   │   ├── Facet index md를 컨텍스트로 제공
    │   │   ├── Groq (llama-3.3-70b) → fallback 5개 모델
    │   │   └── JSON object(core/support/follow_up)로 응답 강제 (temperature=0, max_tokens=256)
    │   │
    │   └── Fallback 경로 (2순위)
    │       ├── regex: [가-힣A-Za-z0-9]{2,} 토큰 추출
    │       └── Facet label 직접 매칭 보강
    │
    ├── Step 2: 키워드 검증
    │   ├── facet label 정확/부분 매칭
    │   ├── raw 후보 키워드 보존
    │   └── "그룹" 키워드 필터링 제외
    │
    ├── Step 3: Facet/raw 검색 (WikiReadOnlyTool)
    │   ├── 1차 프로필 키워드로 후보 기관 선별
    │   ├── follow-up 선택 후 후보 기관 내 재점수화
    │   └── 점수화 (core 6배, support 3배, follow-up 1배, 정확/부분 매칭 강도 반영)
    │
    └── Step 4: 기관 추천 (상위 5개)
        ├── 동일 기관 중복 제거
        ├── 관련 파일 연결 (company_name 기준 그룹핑)
        └── 점수 내림차순 정렬
```

## LLM Rate Limit 정책

Groq 무료 티어: 30 RPM
- 요청 간 2초 간격 강제 (`_RATE_LIMITER_INTERVAL`)
- 429 응답 시 fallback 모델 자동 전환 (6개 체인)
- 모든 모델 소진 시 `None` 반환 → fallback 경로

## 스코어링 상세

| 조건 | 반영 방식 | 예시 |
|------|------|------|
| core 키워드 | term weight 6.0 적용 | 사용자의 최종 의도에 가장 가까운 facet 라벨 |
| support 키워드 | term weight 3.0 적용 | 핵심 의도를 보강하는 facet 라벨 |
| follow-up 키워드 | term weight 1.0 적용 | 2차 선택에서 고른 분류 키워드 |
| 매칭 강도 | exact/title/company/summary 강도로 곱산 | exact=1.0, title/company=0.8, summary=0.4 |

## 캐싱

- `OntologyCheckTool`: 인메모리 + 디스크 캐시 (`ontology_cache.json`, TTL 60초)
- `_load_wiki_index()`: `@lru_cache`로 영구 캐시 (Facet_Index 기반)
