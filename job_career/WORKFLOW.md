# 전체 워크플로우 흐름도

이 문서는 현재 프로젝트의 실제 실행 흐름을 한 장으로 정리한 것입니다. 핵심은 브라우저 요청이 Flask 서버를 거쳐 CrewAI 파이프라인으로 전달되고, 그 결과가 다시 JSON으로 정리되어 UI에 렌더링된다는 점입니다.

## 1. 전체 흐름

```mermaid
flowchart TD
    A[사용자 프로필 입력\n브라우저 UI] --> B[Flask 서버\nPOST /api/analyze]
    B --> C[main_batch.py 실행\nsubprocess]
    C --> D[generate_report(user_profile)]
    D --> E[CrewAI Crew 실행\n2개 에이전트]

    E --> F[Agent A\n커리어 엔티티 매퍼]
    F --> G[OntologyCheckTool]
    G --> H[검증된 표준 키워드 생성]

    E --> I[Agent B\n최종 평가관]
    I --> J[WikiReadOnlyTool]
    J --> K[Wiki_Index.json 기반 검색]
    K --> L[정확한 파일명 본문 조회]

    H --> M[추천 기관 스코어링]
    L --> M
    M --> N[recommended_institutions 5개 정리]

    E --> O{Crew 결과 정상?}
    O -- 예 --> P[최종 JSON 반환]
    O -- 아니오 --> Q[로컬 폴백 경로]
    Q --> R[키워드 추출]
    R --> S[OntologyCheckTool 검증]
    S --> T[WikiReadOnlyTool 색인 검색]
    T --> U[Wiki_Index.json 점수화]
    U --> P

    P --> V[Flask 응답 JSON]
    V --> W[브라우저 카드 렌더링]
```

## 2. 실제 실행 단계

1. 사용자가 브라우저에서 커리어 프로필을 입력합니다.
2. 프론트엔드는 `POST /api/analyze`로 프로필을 Flask 서버에 보냅니다.
3. Flask 서버는 `src/career_agent/main_batch.py`를 subprocess로 실행합니다.
4. `main_batch.py`는 `generate_report(user_profile)`를 호출합니다.
5. `generate_report`가 CrewAI 파이프라인을 시작합니다.
6. Agent A가 후보 키워드를 만들고 `OntologyCheckTool`로 검증합니다.
7. Agent B가 `WikiReadOnlyTool`로 `Wiki_Index.json`을 검색하고, 후보 파일의 정확한 본문을 읽습니다.
8. 결과를 점수화하여 `recommended_institutions` 5개를 정리합니다.
9. Crew 결과가 비정상적이면 `pipeline.py`의 로컬 폴백이 같은 도구와 인덱스를 사용해 JSON을 보정합니다.
10. Flask 서버는 최종 JSON을 클라이언트로 반환하고, 프론트엔드는 카드 형태로 렌더링합니다.

## 3. 파일별 역할

- [server.py](server.py): 브라우저 요청을 받아 subprocess로 배치 엔트리포인트를 실행하고 JSON을 응답합니다.
- [src/career_agent/main.py](src/career_agent/main.py): CLI 대화형 실행 진입점입니다.
- [src/career_agent/main_batch.py](src/career_agent/main_batch.py): Flask가 호출하는 배치 진입점입니다.
- [src/career_agent/pipeline.py](src/career_agent/pipeline.py): CrewAI 실행, 폴백, 결과 병합을 담당합니다.
- [src/career_agent/crew.py](src/career_agent/crew.py): Agent A/B와 LLM 설정, 동시성 제어, 로깅을 담당합니다.
- [src/career_agent/tools/custom_tool.py](src/career_agent/tools/custom_tool.py): `OntologyCheckTool`, `WikiReadOnlyTool`의 실제 구현입니다.

## 4. 데이터와 도구

- `job_wiki/20_Meta/Wiki_Index.json`: 위키 색인과 메타필드 회사명, 제목, 요약, 키워드를 제공합니다.
- `job_wiki/20_Meta/Ontology_Map.json`: 표준 키워드와 동의어 매핑을 제공합니다.
- `job_wiki/20_Meta/ontology_cache.json`: 온톨로지 검증 결과 캐시입니다.
- `job_wiki/20_Meta/llm_calls.csv`: LLM 호출 로그입니다.

## 5. 안정화 포인트

- stdout에는 순수 JSON만 남기고, 실행 로그는 stderr로 분리합니다.
- Crew 결과가 비거나 불완전하면 폴백이 `Wiki_Index.json` 기반으로 5개 추천을 채웁니다.
- 최종 응답은 프론트엔드가 바로 렌더링할 수 있도록 `recommended_institutions` 배열 형태를 유지합니다.

## 6. 한 줄 요약

브라우저 입력 → Flask → `main_batch.py` → CrewAI 2단계 에이전트 → 도구 검증/색인 검색 → 스코어링/폴백 → JSON 응답 → UI 렌더링 순서로 동작합니다.
