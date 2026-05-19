#!/usr/bin/env python3
"""Raw-only markdown formatter — no analysis, no ontology, just raw data."""

from typing import Dict


def render_markdown(job: Dict) -> str:
    """Render a job posting as simple markdown (raw data only, no analysis)."""
    def fm(value: object) -> str:
        return " ".join(str(value).split())

    title = job.get("title", "Untitled")
    company = job.get("company", "Unknown")
    date = job.get("posted_date", "")
    jid = job.get("id", "")
    description = (job.get("description") or "").strip()
    requirements = (job.get("requirements") or "").strip()

    raw = job.get("raw") if isinstance(job, dict) and job.get("raw") else job
    raw_list = raw.get("list", {}) if isinstance(raw, dict) else {}
    ncs_nm = raw_list.get("ncsCdNmLst") or job.get("ncsCdNmLst") or job.get("ncs_nm", "")
    hire_type = raw_list.get("hireTypeNmLst") or job.get("hireTypeNmLst", "")
    recrut_se = raw_list.get("recrutSeNm") or job.get("recrutSeNm", "")
    acbg_cond = raw_list.get("acbgCondNmLst") or job.get("acbgCondNmLst", "")
    work_region = raw_list.get("workRgnNmLst") or job.get("workRgnNmLst", "")
    apply_qual = raw_list.get("aplyQlfcCn") or job.get("aplyQlfcCn", "")
    pref_cond = raw_list.get("prefCondCn") or job.get("prefCondCn", "")
    pref_content = raw_list.get("prefCn") or job.get("prefCn", "")
    screen_method = raw_list.get("scrnprcdrMthdExpln") or job.get("scrnprcdrMthdExpln", "")

    front = ["---"]
    front.append(f"title: {title}")
    front.append(f"source: ALIO")
    front.append(f"date: {date}")
    front.append(f"company: {company}")
    if jid:
        front.append(f"id: {jid}")
    if hire_type:
        front.append(f"hireTypeNmLst: {fm(hire_type)}")
    if recrut_se:
        front.append(f"recrutSeNm: {fm(recrut_se)}")
    if acbg_cond:
        front.append(f"acbgCondNmLst: {fm(acbg_cond)}")
    if work_region:
        front.append(f"workRgnNmLst: {fm(work_region)}")
    if apply_qual:
        front.append(f"aplyQlfcCn: {fm(apply_qual)}")
    if pref_cond:
        front.append(f"prefCondCn: {fm(pref_cond)}")
    if pref_content:
        front.append(f"prefCn: {fm(pref_content)}")
    if screen_method:
        front.append(f"scrnprcdrMthdExpln: {fm(screen_method)}")
    if ncs_nm:
        front.append(f"ncs: {ncs_nm}")
    front.append("---")

    body = []
    body.append(f"# {title}")
    body.append("")

    if description:
        body.append("## 직무 내용")
        body.append(description)
        body.append("")

    if requirements:
        body.append("## 요구사항")
        body.append(requirements)
        body.append("")

    # Archive raw fields from ALIO payload

    raw_keys = [
        ("기관명", "instNm"),
        ("공고제목", "recrutPbancTtl"),
        ("고용형태", "hireTypeNmLst"),
        ("채용구분", "recrutSeNm"),
        ("학력조건", "acbgCondNmLst"),
        ("응시자격", "aplyQlfcCn"),
        ("우대사항", "prefCondCn"),
        ("우대내용", "prefCn"),
        ("공고시작", "pbancBgngYmd"),
        ("공고종료", "pbancEndYmd"),
        ("근무지역", "workRgnNmLst"),
        ("전형방법", "scrnprcdrMthdExpln"),
        ("원문URL", "srcUrl"),
        ("NCS카테고리", "ncsCdNmLst"),
    ]

    body.append("---")
    body.append("## 원본 공고")
    for label, key in raw_keys:
        try:
            val = raw_list.get(key) if isinstance(raw_list, dict) else None
            if not val:
                val = raw.get(key) if isinstance(raw, dict) else None
            if val:
                body.append(f"- {label}: {str(val).strip()}")
        except Exception:
            continue

    tag_source = {}
    if isinstance(raw_list, dict) and raw_list.get("raw_tags"):
        tag_source = raw_list.get("raw_tags") or {}
    elif isinstance(raw, dict) and raw.get("raw_tags"):
        tag_source = raw.get("raw_tags") or {}
    elif isinstance(job, dict) and job.get("raw_tags"):
        tag_source = job.get("raw_tags") or {}
    elif isinstance(raw_list, dict) and raw_list:
        tag_source = raw_list
    elif isinstance(raw, dict):
        tag_source = raw

    if isinstance(tag_source, dict) and tag_source:
        body.append("")
        body.append("### 추출 태그")
        for key in sorted(tag_source.keys()):
            if key == "raw_tags":
                continue
            val = tag_source.get(key)
            if val:
                body.append(f"- {key}: {fm(val)}")

    # Compact JSON dump
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
