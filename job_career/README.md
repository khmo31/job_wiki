# Career Agent (간단 요약)

간단 설명
- 목적: 사용자 프로필에서 핵심 직무 키워드를 도출하고, 로컬 위키 색인(`job_wiki/20_Meta/Wiki_Index.json`) 기반으로 추천 기관을 점수화하여 JSON으로 반환합니다.

주요 흐름
1. 사용자 자연어 입력
2. 빠른 LLM이 키워드 후보 생성 → `OntologyCheckTool`로 검증(쉼표 구분, `src/career_agent/tools/custom_tool.py`)
3. 최종 평가관(Agent B)으로 전달
4. LLM이 색인/도구 호출 지시(예: `WikiReadOnlyTool`) — 색인 조회는 도구 내부에서 처리
5. 색인 기반 점수 산정(로컬, `Wiki_Index.json` 사용)
6. 단일 JSON 출력: `recommended_institutions` (기관명, 예시파일, 점수, 매칭 키워드)

로컬 처리(토큰 비용 없음)
- `OntologyCheckTool` : 온톨로지 매핑 + 인메모리/파일 캐시 (`20_Meta/ontology_cache.json`)
- `WikiReadOnlyTool` : `Wiki_Index.json` 색인 검색(상위 후보) 및 정확 파일명 입력 시 핵심 섹션 추출
- `main.py` 후처리: 도구 호출로 종료될 때 색인 기반 점수화 및 복구 경로 제공

LLM 호출(원격, 토큰/지연 발생)
- 위치: `src/career_agent/crew.py` 및 `config/agents.yaml` (프롬프트)
- 역할: 키워드 추출, 도구 호출 지시, (선택적) 최종 합성
- 운영 방침: 전역 세마포어로 동시성 제한, 타임아웃/로깅(`20_Meta/llm_calls.csv`)

실행 방법
```bash
python src/career_agent/main.py
```

프로그램 실행 후:
1. 본인의 커리어 프로필 입력 프롬프트가 나타남
2. 자유롭게 입력 (여러 줄 가능)
3. 엔터 두 번 입력하여 완료
4. 입력이 없으면 기본 예시로 진행

**예시 입력:**
```
저는 3년 동안 병원에서 원무과 행정 직원으로 일했습니다. 
환자 데이터를 다루다 보니 의료 행정 지식과 의료정보 보호 정책 수립 쪽에 관심이 생겼고, 관련 경험도 쌓았습니다. 
공공기관 쪽으로 이직하고 싶습니다.
```

폴백/복구
- LLM 타임아웃 또는 함수 호출로 종료될 경우 `main.py`가 로컬 색인 기반 점수화를 실행하여 항상 JSON을 출력합니다.

설정/조정 포인트
- 색인 기반 가중치 및 동작은 `job_wiki/20_Meta/Wiki_Index.json`의 메타필드(`company`, `title`, `summary`, `keywords`)를 이용하도록 구현되었습니다.
- LLM 동작(모델, 토큰 제한)은 `src/career_agent/crew.py`와 환경변수로 조정 가능합니다.

권장 다음 단계
- 운영자가 조정 가능한 `config/scoring.yaml` 추가(가중치 관리), 또는 안전 LLM 합성 경로(세마포어+타임아웃)를 별도로 구현.

파일 참조
- 엔트리 포인트: `src/career_agent/main.py`
- 도구 구현: `src/career_agent/tools/custom_tool.py`
- 크루/에이전트: `src/career_agent/crew.py`

궁금하시면 README에 더 자세한 예시(출력 예, 가중치 설명)를 추가해 드리겠습니다.
