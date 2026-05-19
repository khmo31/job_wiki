#!/usr/bin/env python3
"""Raw → Wiki 변환 파이프라인.

job_raw/00_Raw/ 에서 채용공고 분석 결과를 읽어
job_wiki/10_Wiki/Analysis/ 분석 파일 + Wiki_Index.json + 신규 키워드 제안 생성.

변경 사항 (feat/auto-ontology-feedback):
- analyzer에서 new_keywords를 추출하므로, wiki_generator는 이 값을
  바로 Suggested_Keywords.json에 저장 (별도 LLM 호출 최소화)
- 리인덱스 여부와 관계없이 모든 entry의 new_keywords를 수집
- _suggest_keywords()는 backward compat용 (analyzer가 없는 new_keywords 필드 처리)
"""
from __future__ import annotations

import json
import os
import re
import sys
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Project root detection
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_ROOT = PROJECT_ROOT / "job_raw" / "00_Raw"
WIKI_ANALYSIS_DIR = PROJECT_ROOT / "job_wiki" / "10_Wiki" / "Analysis"
WIKI_COMPANIES_DIR = PROJECT_ROOT / "job_wiki" / "10_Wiki" / "Entities" / "Companies"
WIKI_SKILLS_DIR = PROJECT_ROOT / "job_wiki" / "10_Wiki" / "Entities" / "Skills"
WIKI_FACETS_DIR = PROJECT_ROOT / "job_wiki" / "10_Wiki" / "Facets"
WIKI_META_DIR = PROJECT_ROOT / "job_wiki" / "20_Meta"
WIKI_INDEX_PATH = WIKI_META_DIR / "Wiki_Index.json"
FACET_INDEX_PATH = WIKI_META_DIR / "Facet_Index.json"
ONTOLOGY_PATH = WIKI_META_DIR / "Ontology_Map.json"
SUGGESTED_KEYWORDS_PATH = WIKI_META_DIR / "Suggested_Keywords.json"

# Ensure directories exist
for d in [WIKI_ANALYSIS_DIR, WIKI_COMPANIES_DIR, WIKI_SKILLS_DIR, WIKI_FACETS_DIR, WIKI_META_DIR]:
    d.mkdir(parents=True, exist_ok=True)

FACET_CATEGORY_LABELS = {
    "ncs": "NCS",
    "hire_type": "고용형태",
    "recruitment_type": "채용구분",
    "education": "학력",
    "region": "지역",
    "qualification": "응시자격",
    "preference": "우대사항",
    "process": "전형방법",
}

FACET_CATEGORY_ORDER = [
    "ncs",
    "hire_type",
    "recruitment_type",
    "education",
    "region",
    "qualification",
    "preference",
    "process",
]

QUALIFICATION_RULES = [
    ("학력무관", ("학력무관", "학력 및 경력 제한 없음", "학력 제한 없음", "학력·경력 제한 없음")),
    ("경력무관", ("경력무관", "경력 제한 없음", "경력 및 학력 제한 없음")),
    ("신입", ("신입",)),
    ("경력", ("경력",)),
    ("석사", ("석사",)),
    ("박사", ("박사",)),
    ("학사", ("학사", "대졸", "4년제")),
    ("보훈", ("보훈", "국가유공자", "취업지원대상자")),
    ("장애인", ("장애인",)),
    ("지역인재", ("지역인재", "이전지역인재")),
    ("청년", ("청년",)),
    ("병역", ("병역", "군복무", "전역")),
    ("자격증", ("자격증", "면허")),
    ("어학", ("어학", "토익", "토플", "오픽", "텝스", "아이엘츠")),
    ("전공", ("전공",)),
    ("연령제한", ("연령제한", "만 60세", "만 65세")),
]

PREFERENCE_RULES = [
    ("보훈", ("보훈", "국가유공자", "취업지원대상자")),
    ("장애인", ("장애인",)),
    ("지역인재", ("지역인재", "이전지역인재")),
    ("청년인턴", ("청년인턴",)),
    ("청년", ("청년",)),
    ("경력단절여성", ("경력단절 여성", "경력단절여성")),
    ("자격증", ("자격증", "면허")),
    ("어학", ("어학", "토익", "토플", "오픽", "텝스", "아이엘츠")),
    ("가점", ("가점",)),
]

PROCESS_RULES = [
    ("서류전형", ("서류전형", "서류심사")),
    ("면접전형", ("면접전형", "면접심사", "면접")),
    ("필기전형", ("필기전형", "필기")),
    ("실기전형", ("실기전형", "실기")),
    ("인성검사", ("인성검사", "인성")),
    ("적성검사", ("적성검사", "적성")),
    ("PT", ("PT", "프레젠테이션")),
    ("발표", ("합격자 발표", "발표")),
    ("결격사유조회", ("결격사유조회", "결격사유")),
    ("최종합격", ("최종합격",)),
]


def _log(msg: str) -> None:
    print(f"[wiki_generator] {msg}", file=sys.stderr)


def _load_index() -> dict[str, Any]:
    idx_path = RAW_ROOT / "index.json"
    if idx_path.exists():
        return json.loads(idx_path.read_text(encoding="utf-8"))
    return {}


def _load_wiki_index() -> dict[str, Any]:
    if WIKI_INDEX_PATH.exists():
        data = json.loads(WIKI_INDEX_PATH.read_text(encoding="utf-8"))
        return data.get("entries", {}) if isinstance(data, dict) else {}
    return {}


def _save_wiki_index(entries: dict[str, Any]) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        "entries": entries,
    }
    WIKI_INDEX_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"Wiki_Index.json updated: {len(entries)} entries")


def _load_suggested() -> list[dict[str, Any]]:
    if SUGGESTED_KEYWORDS_PATH.exists():
        return json.loads(SUGGESTED_KEYWORDS_PATH.read_text(encoding="utf-8"))
    return []


def _save_suggested(suggestions: list[dict[str, Any]]) -> None:
    SUGGESTED_KEYWORDS_PATH.write_text(
        json.dumps(suggestions, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _read_analysis_from_archive(alio_id: str) -> dict[str, Any] | None:
    """Read analysis from json_archive."""
    archive_path = RAW_ROOT / "json_archive" / f"{alio_id}.json"
    if not archive_path.exists():
        return None
    try:
        data = json.loads(archive_path.read_text(encoding="utf-8"))
        return data
    except Exception:
        return None


def _read_raw_markdown(alio_id: str, raw_index: dict) -> str | None:
    """Read raw markdown content from 00_Raw/."""
    entry = raw_index.get(alio_id)
    if isinstance(entry, dict):
        filename = entry.get("filename", "")
    elif isinstance(entry, str):
        filename = entry
    else:
        return None

    if not filename:
        return None

    md_path = RAW_ROOT / filename
    if md_path.exists():
        return md_path.read_text(encoding="utf-8")
    return None


def _parse_frontmatter(text: str) -> dict[str, Any]:
    """Extract YAML frontmatter from markdown (basic parsing)."""
    result: dict[str, Any] = {}
    match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return result

    front = match.group(1)
    for line in front.split("\n"):
        line = line.strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip('"')
        if key in ("skills", "objective_metadata"):
            continue
        result[key] = value

    return result


def _format_wiki_filename(alio_id: str, company: str, title: str, date_str: str | None = None) -> str:
    date_part = "unknown"
    if date_str:
        date_part = date_str.strip().replace("-", "")[:8]
    elif alio_id.startswith("ALIO-"):
        parts = alio_id.split("-")
        if len(parts) >= 2:
            date_part = parts[1][:8]

    clean_company = re.sub(r"[^가-힣A-Za-z0-9]", "", company)[:20] if company else "unknown"
    clean_alio = alio_id.replace("-", "_")
    return f"{date_part}_{clean_company}_{clean_alio}.md"


def _render_wiki_analysis(
    alio_id: str,
    company: str,
    title: str,
    domain: str,
    skills: list[str],
    latent_skills: list[str] | None,
    job_nature: str,
    complexity: str,
    core_logic: str,
    raw_filename: str | None,
    captured_at: str,
) -> str:
    skills_linked = "\n".join(f"- [[{s}]]" for s in (skills or []))
    if latent_skills:
        all_skills = (skills or []) + [s for s in latent_skills if s not in (skills or [])]
    else:
        all_skills = skills or []

    domain_tag = f"[[{domain}]]" if domain else ""

    lines = [
        "---",
        f"id: {alio_id.replace('-', '_')}",
        f"company: \"[[{company}]]\"" if company else "",
        f"domain: \"{domain_tag}\"" if domain else "",
        f"captured_at: {captured_at}",
        "---",
        "",
        f"# [[{company}]] - {title}" if company else f"# {title}",
        "",
        "## 🧬 직무 DNA (Job Analysis)",
        f"- **핵심 기술/역량:** {', '.join(f'[[{s}]]' for s in all_skills[:6])}",
        f"- **직무 성격:** `{job_nature}`",
        f"- **난이도:** `{complexity.capitalize()}`",
        "",
        "## 🌐 지식 그래프 연결 (Connectivity)",
        f"- **도메인 노드:** {domain_tag}",
    ]

    if all_skills:
        lines.append(f"- **기술 스택 노드:** {', '.join(f'[[{s}]]' for s in all_skills[:10])}")

    lines.extend([
        "",
        "## 📝 분석 근거 (Evidence)",
        f"- **핵심 로직:** {core_logic}",
    ])

    if raw_filename:
        lines.append(f"- **Source Raw:** [[00_Raw/{raw_filename}]]")

    lines.append("")
    return "\n".join(lines)


def _company_profile_filename(company: str) -> str:
    clean = re.sub(r"[^가-힣A-Za-z0-9]", "", company)[:30]
    return f"{clean}.md"


def _safe_filename_component(text: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', '', text).strip() or "unknown"


def _split_multi_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        merged: list[str] = []
        for item in value:
            merged.extend(_split_multi_value(item))
        return list(dict.fromkeys(merged))
    text = str(value).strip()
    if not text or text in ("-", "0", "null", "None"):
        return []
    parts = [part.strip() for part in text.split(",") if part.strip()]
    return list(dict.fromkeys(parts or [text]))


def _extract_signal_tags(text: str, rules: list[tuple[str, tuple[str, ...]]]) -> list[str]:
    if not text:
        return []
    cleaned = str(text).replace("\n", " ").replace("\r", " ")
    tags: list[str] = []
    for tag, keywords in rules:
        if any(keyword in cleaned for keyword in keywords):
            tags.append(tag)
    return list(dict.fromkeys(tags))


def _extract_facet_tags(raw_data: dict[str, Any]) -> dict[str, list[str]]:
    raw_list = raw_data.get("list", {}) if isinstance(raw_data, dict) else {}
    source = raw_list if isinstance(raw_list, dict) and raw_list else (raw_data if isinstance(raw_data, dict) else {})

    apply_text = str(source.get("aplyQlfcCn") or "")
    pref_text = "\n".join([
        str(source.get("prefCondCn") or ""),
        str(source.get("prefCn") or ""),
    ]).strip()
    process_text = str(source.get("scrnprcdrMthdExpln") or "")

    facets = {
        "ncs": _split_multi_value(source.get("ncsCdNmLst") or source.get("ncs_nm") or source.get("ncs") or ""),
        "hire_type": _split_multi_value(source.get("hireTypeNmLst") or ""),
        "recruitment_type": _split_multi_value(source.get("recrutSeNm") or ""),
        "education": _split_multi_value(source.get("acbgCondNmLst") or ""),
        "region": _split_multi_value(source.get("workRgnNmLst") or ""),
        "qualification": _extract_signal_tags(apply_text, QUALIFICATION_RULES),
        "preference": _extract_signal_tags(pref_text or apply_text, PREFERENCE_RULES),
        "process": _extract_signal_tags(process_text, PROCESS_RULES),
    }

    return facets


def _render_facet_page(category: str, tag: str, items: list[dict[str, Any]]) -> str:
    category_label = FACET_CATEGORY_LABELS.get(category, category)
    sorted_items = sorted(items, key=lambda x: (x.get("date", ""), x.get("company", ""), x.get("title", "")))
    lines = [
        "---",
        f'category: "{category}"',
        f'category_label: "{category_label}"',
        f'tag: "{tag}"',
        f'count: {len(sorted_items)}',
        "---",
        "",
        f"# {tag}",
        "",
        f"## {category_label} 공고",
    ]

    for item in sorted_items:
        raw_link = f"[[00_Raw/{item['raw_filename']}]]" if item.get("raw_filename") else ""
        analysis_link = f"[[Analysis/{item['analysis_filename']}]]" if item.get("analysis_filename") else ""
        link_bits = [bit for bit in (analysis_link, raw_link) if bit]
        link_text = " · ".join(link_bits)
        meta = " / ".join([part for part in (item.get("company", ""), item.get("title", "")) if part])
        date = item.get("date", "")
        prefix = f"{date} · " if date else ""
        lines.append(f"- {link_text} — {prefix}{meta}" if link_text else f"- {prefix}{meta}")

    lines.append("")
    return "\n".join(lines)


def _render_facet_index(facet_index: dict[str, Any]) -> str:
    categories = facet_index.get("categories", {}) if isinstance(facet_index, dict) else {}
    lines = [
        "---",
        'title: "Facet Index"',
        "---",
        "",
        "# 2차 분류 허브",
        "",
        "공고 원문 필드를 기반으로 자동 생성된 2차 분류 페이지입니다.",
        "",
    ]

    for category in FACET_CATEGORY_ORDER:
        tags = categories.get(category, {}) if isinstance(categories, dict) else {}
        if not tags:
            continue
        category_label = FACET_CATEGORY_LABELS.get(category, category)
        lines.append(f"## {category_label}")
        lines.append("")
        for tag, items in sorted(tags.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            page_name = _safe_filename_component(tag)
            lines.append(f"- [[{category}/{page_name}]] ({len(items)}건)")
        lines.append("")

    return "\n".join(lines)


def _rebuild_facet_pages(raw_index: dict[str, Any]) -> None:
    if WIKI_FACETS_DIR.exists():
        shutil.rmtree(WIKI_FACETS_DIR)
    WIKI_FACETS_DIR.mkdir(parents=True, exist_ok=True)

    facet_index: dict[str, Any] = {"generated_at": datetime.now(timezone.utc).isoformat(), "categories": {}}
    wiki_index = _load_wiki_index()

    for alio_id, raw_entry in raw_index.items():
        archive = _read_analysis_from_archive(str(alio_id))
        if not archive:
            continue

        raw_data = archive.get("raw", {}) if isinstance(archive, dict) else {}
        raw_list = raw_data.get("list", {}) if isinstance(raw_data, dict) else {}
        if not isinstance(raw_list, dict) or not raw_list:
            raw_list = raw_data if isinstance(raw_data, dict) else {}

        company = (raw_list.get("instNm") or raw_data.get("company") or "").strip()
        title = (raw_list.get("recrutPbancTtl") or raw_data.get("title") or "").strip()
        date_str = (raw_list.get("pbancBgngYmd") or raw_data.get("pbancBgngYmd") or "").strip()

        raw_filename = ""
        if isinstance(raw_entry, dict):
            raw_filename = raw_entry.get("filename", "")
        elif isinstance(raw_entry, str):
            raw_filename = raw_entry

        analysis_filename = _format_wiki_filename(str(alio_id), company, title, date_str=date_str)
        if not (WIKI_ANALYSIS_DIR / analysis_filename).exists():
            analysis_filename = ""

        item_meta = {
            "alio_id": str(alio_id),
            "company": company,
            "title": title,
            "date": date_str,
            "raw_filename": raw_filename,
            "analysis_filename": analysis_filename,
        }

        facets = _extract_facet_tags(raw_data)
        for category in FACET_CATEGORY_ORDER:
            tags = facets.get(category, [])
            if not tags:
                continue
            cat_bucket = facet_index["categories"].setdefault(category, {})
            for tag in tags:
                cat_bucket.setdefault(tag, []).append(item_meta)

    # Write category pages and per-tag pages
    for category in FACET_CATEGORY_ORDER:
        cat_tags = facet_index["categories"].get(category, {})
        if not cat_tags:
            continue
        category_dir = WIKI_FACETS_DIR / category
        category_dir.mkdir(parents=True, exist_ok=True)

        category_index_lines = [
            "---",
            f'category: "{category}"',
            f'category_label: "{FACET_CATEGORY_LABELS.get(category, category)}"',
            "---",
            "",
            f"# {FACET_CATEGORY_LABELS.get(category, category)}",
            "",
        ]

        for tag, items in sorted(cat_tags.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            page_name = _safe_filename_component(tag)
            page_path = category_dir / f"{page_name}.md"
            page_path.write_text(_render_facet_page(category, tag, items), encoding="utf-8")
            category_index_lines.append(f"- [[{category}/{page_name}]] ({len(items)}건)")

        category_index_lines.append("")
        (category_dir / "index.md").write_text("\n".join(category_index_lines), encoding="utf-8")

    facet_index["category_count"] = len(facet_index["categories"])
    facet_index["tag_count"] = sum(len(tags) for tags in facet_index["categories"].values())
    FACET_INDEX_PATH.write_text(json.dumps(facet_index, ensure_ascii=False, indent=2), encoding="utf-8")
    (WIKI_FACETS_DIR / "index.md").write_text(_render_facet_index(facet_index), encoding="utf-8")
    _log(f"facet pages rebuilt: {facet_index['tag_count']} tags across {facet_index['category_count']} categories")


def _render_company_profile(company: str, aliases: list[str], analysis_files: list[str], domain: str) -> str:
    aliases_list = "\n".join(f"  - \"{a}\"" for a in aliases) if aliases else "  -"
    analysis_links = "\n".join(f"  - [[Analysis/{f}]]" for f in analysis_files) if analysis_files else "  - (none yet)"

    return (
        "---\n"
        f"name: \"{company}\"\n"
        f"domain: \"[[{domain}]]\"\n"
        "aliases:\n"
        f"{aliases_list}\n"
        "---\n"
        "\n"
        f"# {company}\n"
        "\n"
        "## 관련 분석\n"
        f"{analysis_links}\n"
    )


def generate_wiki_entry(alio_id: str, raw_index: dict) -> bool:
    """Generate/update wiki entry for a single job posting."""
    archive = _read_analysis_from_archive(alio_id)
    raw_text = _read_raw_markdown(alio_id, raw_index)
    raw_entry = raw_index.get(alio_id, {})
    if isinstance(raw_entry, str):
        raw_entry = {"filename": raw_entry}
    raw_filename = raw_entry.get("filename", "")

    if not archive and not raw_text:
        return False

    analysis = archive.get("analysis", {}) if archive else {}
    raw_data = archive.get("raw", {}) if archive else {}
    raw_list = raw_data.get("list", {}) if isinstance(raw_data, dict) else {}

    if not analysis and raw_text:
        front = _parse_frontmatter(raw_text)
        analysis = {
            "skills_found": front.get("skills", "").split(", "),
        }

    company = (raw_list.get("instNm") or raw_data.get("company") or raw_data.get("instNm") or analysis.get("company") or "")
    title = (raw_list.get("recrutPbancTtl") or raw_data.get("title") or raw_data.get("recrutPbancTtl") or analysis.get("title") or "")
    captured_at = (raw_data.get("captured_at", "") or analysis.get("captured_at", datetime.now(timezone.utc).strftime("%Y-%m-%d")))

    domain = analysis.get("domain_context", "") or ""
    if not domain:
        ncs = raw_list.get("ncsCdNmLst") or raw_data.get("ncs_nm", "") or raw_data.get("ncs_nm", "") or ""
        if "의료" in ncs or "병원" in company:
            domain = "보건.의료"
        elif "연구" in ncs or "연구원" in company:
            domain = "연구"
        elif "도로" in company or "물류" in ncs:
            domain = "운전.운송"
        else:
            domain = "경영.회계.사무"

    skills = analysis.get("skills_found", []) or []
    if isinstance(skills, str):
        skills = [s.strip().replace("[[", "").replace("]]", "") for s in skills.split(",") if s.strip()]

    latent = analysis.get("latent_skills", [])
    if isinstance(latent, str):
        latent = [s.strip() for s in latent.split(",") if s.strip()]

    job_nature = analysis.get("job_nature", "실무/혼합")
    complexity = analysis.get("complexity", "medium")
    core_logic = analysis.get("core_logic", "주요 업무 로직")

    # Wiki index
    wiki_index = _load_wiki_index()
    date_str = raw_list.get("pbancBgngYmd") or raw_data.get("pbancBgngYmd") or ""
    wiki_filename = _format_wiki_filename(alio_id, company, title, date_str=date_str)

    if wiki_index.get(wiki_filename):
        _log(f"already indexed: {wiki_filename}")
        return False

    # Save analysis markdown
    analysis_md = _render_wiki_analysis(
        alio_id=alio_id, company=company, title=title, domain=domain,
        skills=skills, latent_skills=latent,
        job_nature=job_nature, complexity=complexity, core_logic=core_logic,
        raw_filename=raw_filename, captured_at=captured_at,
    )
    analysis_path = WIKI_ANALYSIS_DIR / wiki_filename
    analysis_path.write_text(analysis_md, encoding="utf-8")
    _log(f"created: {wiki_filename}")

    wiki_entry: dict[str, Any] = {
        "company": f"[[{company}]]" if company else "",
        "title": title,
        "keywords": [f"[[{s}]]" for s in skills[:8]],
        "summary": f"{domain} 분야의 {company} {job_nature} 채용 공고 분석.",
    }
    wiki_index[wiki_filename] = wiki_entry
    _save_wiki_index(wiki_index)

    # Company profile
    company_filename = _company_profile_filename(company) if company else None
    if company_filename:
        company_path = WIKI_COMPANIES_DIR / company_filename
        if not company_path.exists():
            company_md = _render_company_profile(
                company=company, aliases=[company],
                analysis_files=[wiki_filename], domain=domain,
            )
            company_path.write_text(company_md, encoding="utf-8")
            _log(f"company profile created: {company_filename}")

    return True


# ── 키워드 제안 (2가지 소스) ──

def _harvest_new_keywords_from_analysis() -> list[dict[str, Any]]:
    """json_archive 내 모든 analysis에서 new_keywords 필드를 수집.

    analyzer의 LLM extraction이 all_keywords와 new_keywords를
    analysis에 저장하므로, 여기서 바로 읽어서 Suggested_Keywords에 추가.
    별도 LLM 호출 불필요.
    """
    json_archive_dir = RAW_ROOT / "json_archive"
    if not json_archive_dir.exists():
        return []

    collected: list[dict[str, Any]] = []
    files_scanned = 0
    files_with_new_kw = 0
    for fpath in sorted(json_archive_dir.iterdir()):
        if not fpath.name.endswith(".json"):
            continue
        files_scanned += 1
        alio_id = fpath.stem
        try:
            data = json.loads(fpath.read_text(encoding="utf-8"))
            analysis = data.get("analysis", {})
            if not isinstance(analysis, dict):
                continue
            new_kws = analysis.get("new_keywords", [])
            if not new_kws or not isinstance(new_kws, list):
                continue
            files_with_new_kw += 1
            for kw in new_kws:
                if kw and isinstance(kw, str) and kw.strip():
                    collected.append({
                        "keyword": kw.strip(),
                        "source_alio_id": alio_id,
                        "discovered_at": datetime.now(timezone.utc).isoformat(),
                        "status": "suggested",
                    })
        except Exception:
            continue

    if collected:
        _log(f"harvested {len(collected)} new_keywords from {files_with_new_kw}/{files_scanned} archive files")
    return collected


def _merge_keywords_into_suggested(new_entries: list[dict[str, Any]]) -> int:
    """중복 제거하고 Suggested_Keywords.json에 추가."""
    if not new_entries:
        return 0

    existing = _load_suggested()
    seen_keywords = {s.get("keyword", "") for s in existing}

    added = 0
    for entry in new_entries:
        kw = entry.get("keyword", "")
        if kw and kw not in seen_keywords:
            existing.append(entry)
            seen_keywords.add(kw)
            added += 1

    if added > 0:
        _save_suggested(existing)
        _log(f"added {added} new keyword suggestions to Suggested_Keywords.json")
    else:
        _log("no new keyword suggestions (all duplicates)")

    return added


def _suggest_keywords_llm(alio_id: str, existing_skills: list[str], text: str) -> None:
    """Backward compat: LLM으로 키워드 제안 (analyzer가 new_keywords 없는 경우).

    참고: 새 analyzer는 new_keywords를 직접 저장하므로,
    이 함수는 기존 분석 결과(cache) 처리용 fallback.
    """
    if not text or len(text) < 50:
        return

    try:
        import importlib.util
        llm_path = PROJECT_ROOT / "job_career" / "src" / "career_agent" / "llm_client.py"
        spec = importlib.util.spec_from_file_location("llm_client", llm_path)
        if spec and spec.loader:
            llm_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(llm_mod)
            suggest_ontology_keywords = llm_mod.suggest_ontology_keywords
        else:
            return
    except Exception:
        return

    suggestions = suggest_ontology_keywords(text, existing_skills)
    if not suggestions:
        return

    existing = _load_suggested()
    seen_keywords = {s.get("keyword", "") for s in existing}
    new_entries = []
    for kw in suggestions:
        if kw not in seen_keywords:
            new_entries.append({
                "keyword": kw,
                "source_alio_id": alio_id,
                "discovered_at": datetime.now(timezone.utc).isoformat(),
                "status": "suggested",
            })
            seen_keywords.add(kw)
    if new_entries:
        existing.extend(new_entries)
        _save_suggested(existing)
        _log(f"LLM keyword suggestions: {[e['keyword'] for e in new_entries]}")


def main() -> int:
    raw_index = _load_index()

    # ── Step 1: Wiki entry 생성 (신규만) ──
    new_count = 0
    for alio_id, entry in raw_index.items():
        if isinstance(entry, dict) and entry.get("last_analyzed_at"):
            if generate_wiki_entry(str(alio_id), raw_index):
                new_count += 1
    _log(f"wiki generation complete: {new_count} new entries")

    # ── Step 1b: Raw 기반 2차 분류 허브 재생성 ──
    _rebuild_facet_pages(raw_index)

    # ── Step 2: new_keywords 수집 (모든 entry, 신규/기존 무관) ──
    # analyzer가 저장한 new_keywords → Suggested_Keywords.json
    from_analysis = _harvest_new_keywords_from_analysis()
    if from_analysis:
        _merge_keywords_into_suggested(from_analysis)

    # ── Step 3: (backward compat) 분석에 new_keywords 없는 entry만 LLM 제안 ──
    # legacy cache에서 new_keywords가 누락된 경우 대비
    llm_fallback_count = 0
    already_have_new_kw = 0
    for alio_id, entry in raw_index.items():
        if not (isinstance(entry, dict) and entry.get("last_analyzed_at")):
            continue
        alio_id_str = str(alio_id)
        archive = _read_analysis_from_archive(alio_id_str)
        if not archive:
            continue
        analysis = archive.get("analysis", {})
        if not isinstance(analysis, dict):
            continue
        # skip if new_keywords already exists in analysis
        if analysis.get("new_keywords"):
            already_have_new_kw += 1
            continue
        # fallback: use old LLM suggestion path
        existing_skills = analysis.get("skills_found", []) or []
        text_parts = []
        rd = archive.get("raw", {})
        if isinstance(rd, dict):
            rl = rd.get("list", {})
            for key in ("recrutPbancTtl", "aplyQlfcCn", "prefCondCn", "prefCn", "scrnprcdrMthdExpln"):
                val = rl.get(key) or rd.get(key, "")
                if val and isinstance(val, str):
                    text_parts.append(val)
        suggest_text = "\n".join(text_parts) if text_parts else ""
        if suggest_text:
            _suggest_keywords_llm(alio_id_str, existing_skills, suggest_text)
            llm_fallback_count += 1

    if already_have_new_kw > 0 or llm_fallback_count > 0:
        _log(f"keyword suggestions: {already_have_new_kw} entries already have new_keywords, "
             f"{llm_fallback_count} entries needed LLM fallback")

    return 0


if __name__ == "__main__":
    sys.exit(main())
