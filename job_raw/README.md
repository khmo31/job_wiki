P-Reinforce Harvester Prototype

이 저장소는 공공기관 채용 API(ALIO)로부터 채용공고를 수집해
원본 JSON 아카이브와 함께 YAML frontmatter가 포함된 마크다운을 `00_Raw/`에 저장하고,
원문 태그를 그대로 보존해 2차 분류용 facet 위키를 만드는 파이프라인입니다.

**주요 목적**
- **수집**: ALIO 공공데이터에서 공고 메타·본문을 수집
- **정규화**: 원문 필드를 태그로 정리
- **아카이빙**: 원본 JSON을 `00_Raw/json_archive/`에 보관
- **저장**: `{date_key}_{alio_id}_{company}_{title}.md` 형식으로 마크다운 저장(충돌 방지)

이 저장소의 문서는 [docs/README.md](docs/README.md)로 정리했습니다.

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned