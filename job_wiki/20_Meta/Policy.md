# Policy — 보상 함수 및 운영 규칙

초기 설정:

- `initial_R`: 0.85
- `weights`:
  - `novelty`: 0.40
  - `connectivity`: 0.35
  - `conflict_resolution`: 0.25

설명:
- `initial_R`는 Reasoning Log의 기본 신뢰도입니다. 현재는 0.85로 설정되어 있습니다.
- 가중치는 합성 판단 시 사용하는 보상 함수의 시작값입니다. 운영 중 데이터에 따라 조정됩니다.

운영 규칙:
- 충돌 발생 시(예: 연봉·스택 불일치) 원본을 아카이빙하고 `20_Meta/Graph_State.json`과 이 파일에 기록하세요.
- 가중치 변경은 변경 사유 및 날짜를 함께 기록해야 합니다.