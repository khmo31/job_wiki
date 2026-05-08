P-Reinforce Harvester Prototype

이 저장소는 공공기관 채용 API(ALIO)로부터 채용공고를 수집해
원본 JSON 아카이브와 함께 YAML frontmatter가 포함된 마크다운을 `00_Raw/`에 저장하고,
경량 규칙과 LLM 분석을 결합해 직무 속성(예: `core_logic`, `latent_skills`)을 추출·정리하는 파이프라인입니다.

**주요 목적**
- **수집**: ALIO 공공데이터에서 공고 메타·본문을 수집
- **정규화**: 텍스트 정리 및 기술 키워드 추출(Obsidian-style 링크 `[[기술명]]` 사용)
- **분석**: LLM(주: NVIDIA Integrate / 대체: OpenAI)으로 직무 DNA(객관적 속성) 산출
- **아카이빙**: 원본+분석 결과를 `00_Raw/json_archive/`에 보관
- **저장**: `{date_key}_{alio_id}_{company}_{title}.md` 형식으로 마크다운 저장(충돌 방지)

이 저장소의 문서는 `docs/README.md`로 이동했습니다.

주요 문서는 [docs/README.md](docs/README.md) 를 확인하세요.
```powershell

Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned