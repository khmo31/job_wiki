from typing import List, Dict, Optional


def render_markdown(job: Dict, skills: List[str], reasoning: Dict[str, str], analysis: Optional[Dict] = None, interests: List[str] | None = None) -> str:
    title = job.get("title", "Untitled")
    company = job.get("company", "Unknown")
    date = job.get("posted_date", "")
    jid = job.get("id", "")

    front = ["---"]
    front.append(f"title: {title}")
    front.append(f"source: ALIO")
    front.append(f"date: {date}")
    front.append(f"company: {company}")
    if jid:
        front.append(f"id: {jid}")
    # existing skill list
    front.append("skills:")
    for s in skills:
        front.append(f"  - \"[[{s}]]\"")

    # Objective Metadata (analysis) - keep it optional and machine-friendly
    if analysis:
        front.append("objective_metadata:")
        # skills_found
        sks = analysis.get("skills_found") or []
        front.append("  skills_found:")
        for s in sks:
            front.append(f"    - \"[[{s}]]\"")
        # job_nature, complexity
        if analysis.get("job_nature") is not None:
            front.append(f"  job_nature: \"{analysis.get('job_nature')}\"")
        if analysis.get("complexity") is not None:
            front.append(f"  complexity: \"{analysis.get('complexity')}\"")
        # small summary fields
        if analysis.get("domain_context"):
            dc = str(analysis.get("domain_context")).replace('\n', ' ')
            front.append(f"  domain_context: \"{dc}\"")
    front.append("---")

    body = []
    body.append(f"# {title}")
    body.append("")
    body.append("## 요약")
    # prefer description, then short summary fields
    body.append((job.get("description") or job.get("summary") or "").strip())
    body.append("")
    body.append("## Matching Reasoning")
    for s in skills:
        insight = reasoning.get(s, "관련 근거가 발견되었습니다.")
        body.append(f"- [[{s}]]: {insight}")

    # include a short Objective Summary if analysis present
    if analysis:
        body.append("")
        body.append("## Objective Summary (자동분석)")
        if analysis.get("core_logic"):
            body.append(f"- 핵심 로직: {analysis.get('core_logic')}")
        if analysis.get("domain_context"):
            body.append(f"- 도메인 컨텍스트: {analysis.get('domain_context')}")
        if analysis.get("latent_skills"):
            body.append(f"- 잠재적 필요 기술: {', '.join(analysis.get('latent_skills'))}")

    # Archive original important fields from raw payload for later re-analysis
    body.append("")
    body.append("---")
    body.append("## 원본 공고(아카이브)")
    raw = job.get("raw") if isinstance(job, dict) and job.get("raw") else job
    # Data may be nested under 'list' (ALIO) or flat (legacy)
    raw_list = raw.get("list", {}) if isinstance(raw, dict) else {}
    # list of common ALIO raw fields to preserve
    raw_keys = [
        ("기관명", "instNm"),
        ("공고제목", "recrutPbancTtl"),
        ("채용구분", "recrutSeNm"),
        ("응시자격", "aplyQlfcCn"),
        ("우대사항", "prefCondCn"),
        ("우대내용(prefCn)", "prefCn"),
        ("요건/requirements", "requirements"),
        ("공고시작", "pbancBgngYmd"),
        ("공고종료", "pbancEndYmd"),
        ("근무지역", "workRgnNmLst"),
        ("전형방법", "scrnprcdrMthdExpln"),
        ("원문URL", "srcUrl"),
        ("NCS카테고리", "ncsCdNmLst"),
    ]
    for label, key in raw_keys:
        try:
            val = raw_list.get(key) if isinstance(raw_list, dict) else None
            if not val:
                val = raw.get(key) if isinstance(raw, dict) else None
            if val:
                body.append(f"- {label}: {str(val).strip()}")
        except Exception:
            continue

    # fallback: include a compact JSON dump of raw for full context (last resort)
    try:
        import json as _json

        compact = _json.dumps(raw, ensure_ascii=False, indent=2)
        body.append("")
        body.append("### Raw JSON")
        body.append("```json")
        body.append(compact)
        body.append("```")
    except Exception:
        pass

    return "\n".join(front + [""] + body)
