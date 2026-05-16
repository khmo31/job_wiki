# Career Agent (로컬 매칭 엔진)

사용자 프로필에서 핵심 직무 키워드를 도출하고, 로컬 위키 색인(`job_wiki/20_Meta/Wiki_Index.json`) 기반으로 추천 기관을 점수화합니다.

**특징:** LLM 불필요, 순수 로컬 매칭 (Ontology + 키워드 스코어링)

## 구조

```
job_career/
├── pyproject.toml
├── src/career_agent/
│   ├── __init__.py
│   ├── pipeline.py    # 매칭 파이프라인
│   └── tools/
│       ├── __init__.py
│       └── custom_tool.py  # OntologyCheckTool, WikiReadOnlyTool
```

## 사용

```python
from career_agent import generate_report

result = generate_report("저는 3년 동안 병원 원무과에서 일했습니다...")
print(result)
```

## 의존성

Python 표준 라이브러리만 사용 (추가 패키지 불필요).
