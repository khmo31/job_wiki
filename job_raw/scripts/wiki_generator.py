#!/usr/bin/env python3
"""Raw → Wiki 변환 파이프라인.

job_raw/00_Raw/ 에서 신규 채용공고 분석 결과를 읽어
job_wiki/10_Wiki/Analysis/ 분석 파일 + Wiki_Index.json + 신규 키워드 제안 생성.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Project root detection
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_ROOT = PROJECT_ROOT / "job_raw" / "00_Raw"
WIKI_ANALYSIS_DIR = PROJECT_ROOT / "job_wiki" / "10_Wiki" / "Analysis"
WIKI_COMPANIES_DIR = PROJECT_ROOT / "job_wiki" / "10_Wiki" / "Entities" / "Companies"
WIKI_SKILLS_DIR = PROJECT_ROOT / "job_wiki" / "10_Wiki" / "Entities" / "Skills"
WIKI_META_DIR = PROJECT_ROOT / "job_wiki" / "20_Meta"
WIKI_INDEX_PATH = WIKI_META_DIR / "Wiki_Index.json"
ONTOLOGY_PATH = WIKI_META_DIR / "Ontology_Map.json"
SUGGESTED_KEYWORDS_PATH = WIKI_META_DIR / "Suggested_Keywords.json"

# Ensure directories exist
for d in [WIKI_ANALYSIS_DIR, WIKI_COMPANIES_DIR, WIKI_SKILLS_DIR, WIKI_META_DIR]:
    d.mkdir(parents=True, exist_ok=True)


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


def _load_ontology_mappings() -> dict[str, list[str]]:
    if ONTOLOGY_PATH.exists():
        data = json.loads(ONTOLOGY_PATH.read_text(encoding="utf-8"))
        mappings = data.get("mappings", {}) if isinstance(data, dict) else {}
        return mappings if isinstance(mappings, dict) else {}
    return {}


def _save_ontology_mappings(mappings: dict[str, list[str]]) -> None:
    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        "version": "v1",
        "mappings": mappings,
    }
    ONTOLOGY_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_suggested() -> list[dict[str, Any]]:
    if SUGGESTED_KEYWORDS_PATH.exists():
        return json.loads(SUGGESTED_KEYWORDS_PATH.read_text(encoding="utf-8"))
    return []


def _save_suggested(suggestions: list[dict[str, Any]]) -> None:
    SUGGESTED_KEYWORDS_PATH.write_text(
        json.dumps(suggestions, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _alio_id_from_job_file(filename: str) -> str | None:
    """Extract ALIO ID from a raw markdown file's YAML frontmatter."""
    return None  # Will be extracted from JSON archive


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
        # Handle nested keys like skills: - "[[키워드]]"
        if key in ("skills", "objective_metadata"):
            continue  # Skip complex nested fields
        result[key] = value

    return result


def _format_wiki_filename(alio_id: str, company: str, title: str, date_str: str | None = None) -> str:
    """Generate wiki analysis filename matching existing convention.

    Uses pbancBgngYmd (date_str) if available, otherwise falls back to ALIO ID prefix.
    """
    # Extract date from pbancBgngYmd or ALIO ID
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
    """Render a wiki analysis markdown file matching the existing Obsidian format."""
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


def _render_skill_profile(
    skill_name: str, related_skills: list[str], parent_domain: str
) -> str:
    related_links = "\n".join(f"  - [[{s}]]" for s in related_skills) if related_skills else "  -"

    return (
        "---\n"
        f"name: \"{skill_name}\"\n"
        f"domain: \"[[{parent_domain}]]\"\n"
        "related:\n"
        f"{related_links}\n"
        "---\n"
        "\n"
        f"# {skill_name}\n"
        "\n"
        "관련 역량 및 기술.\n"
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

    # Extract metadata
    analysis = archive.get("analysis", {}) if archive else {}
    raw_data = archive.get("raw", {}) if archive else {}

    # Fallback: parse from raw markdown YAML frontmatter
    if not analysis and raw_text:
        front = _parse_frontmatter(raw_text)
        analysis = {
            "skills_found": front.get("skills", "").split(", "),
        }

    company = raw_data.get("company") or raw_data.get("instNm") or analysis.get("company") or ""
    title = raw_data.get("title") or raw_data.get("recrutPbancTtl") or analysis.get("title") or ""
    captured_at = raw_data.get("captured_at", "") or analysis.get("captured_at", datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    # Determine domain
    domain = analysis.get("domain_context", "") or ""
    if not domain:
        # Try to infer from NCS or company type
        ncs = raw_data.get("ncs_nm", "") or ""
        if "의료" in ncs or "병원" in company:
            domain = "보건.의료"
        elif "연구" in ncs or "연구원" in company:
            domain = "연구"
        elif "도로" in company or "물류" in ncs:
            domain = "운전.운송"
        else:
            domain = "경영.회계.사무"

    # Skills
    skills = analysis.get("skills_found", []) or []
    if isinstance(skills, str):
        skills = [s.strip().replace("[[", "").replace("]]", "") for s in skills.split(",") if s.strip()]

    latent = analysis.get("latent_skills", [])
    if isinstance(latent, str):
        latent = [s.strip() for s in latent.split(",") if s.strip()]

    # Job nature & complexity
    job_nature = analysis.get("job_nature", "실무/혼합")
    complexity = analysis.get("complexity", "medium")
    core_logic = analysis.get("core_logic", "주요 업무 로직")

    # Wiki index entry
    wiki_index = _load_wiki_index()
    date_str = raw_data.get("pbancBgngYmd") or ""
    wiki_filename = _format_wiki_filename(alio_id, company, title, date_str=date_str)
    existing = wiki_index.get(wiki_filename)

    if existing:
        _log(f"already indexed: {wiki_filename}")
        return False

    # Render and save analysis markdown
    analysis_md = _render_wiki_analysis(
        alio_id=alio_id,
        company=company,
        title=title,
        domain=domain,
        skills=skills,
        latent_skills=latent,
        job_nature=job_nature,
        complexity=complexity,
        core_logic=core_logic,
        raw_filename=raw_filename,
        captured_at=captured_at,
    )

    analysis_path = WIKI_ANALYSIS_DIR / wiki_filename
    analysis_path.write_text(analysis_md, encoding="utf-8")
    _log(f"created: {wiki_filename}")

    # Update Wiki_Index
    wiki_entry: dict[str, Any] = {
        "company": f"[[{company}]]" if company else "",
        "title": title,
        "keywords": [f"[[{s}]]" for s in skills[:8]],
        "summary": f"{domain} 분야의 {company} {job_nature} 채용 공고 분석.",
    }
    wiki_index[wiki_filename] = wiki_entry
    _save_wiki_index(wiki_index)

    # Update company profile
    company_filename = _company_profile_filename(company) if company else None
    if company_filename:
        company_path = WIKI_COMPANIES_DIR / company_filename
        existing_analyses: list[str] = []
        if company_path.exists():
            # Read existing to find current analysis files
            existing_analyses = [wiki_filename]
        else:
            company_md = _render_company_profile(
                company=company,
                aliases=[company],
                analysis_files=[wiki_filename],
                domain=domain,
            )
            company_path.write_text(company_md, encoding="utf-8")
            _log(f"company profile created: {company_filename}")

    # Suggest new ontology keywords
    suggest_text = raw_text or ""
    if not suggest_text or len(suggest_text) < 100:
        # Fallback: read from json_archive raw data
        archive = _read_analysis_from_archive(alio_id)
        if archive:
            rd = archive.get("raw", {})
            if isinstance(rd, dict):
                parts = []
                for key in ("recrutPbancTtl", "aplyQlfcCn", "prefCondCn", "prefCn", "scrnprcdrMthdExpln"):
                    val = rd.get(key, "")
                    if val and isinstance(val, str):
                        parts.append(val)
                if parts:
                    suggest_text = "\n".join(parts)
    _suggest_keywords(alio_id, skills, suggest_text)

    return True


def _suggest_keywords(alio_id: str, existing_skills: list[str], text: str) -> None:
    """Use LLM to suggest new ontology keywords, save for manual review."""
    try:
        import importlib.util
        llm_path = PROJECT_ROOT / "job_career" / "src" / "career_agent" / "llm_client.py"
        spec = importlib.util.spec_from_file_location("llm_client", llm_path)
        if spec and spec.loader:
            llm_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(llm_mod)
            suggest_ontology_keywords = llm_mod.suggest_ontology_keywords
        else:
            _log("llm_client module not found")
            return
    except Exception:
        _log("llm_client not available for keyword suggestions")
        return

    if not text or len(text) < 50:
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
        _log(f"new keyword suggestions: {[e['keyword'] for e in new_entries]}")


def main() -> int:
    raw_index = _load_index()
    new_count = 0

    for alio_id, entry in raw_index.items():
        if isinstance(entry, dict) and entry.get("last_analyzed_at"):
            if generate_wiki_entry(str(alio_id), raw_index):
                new_count += 1

    _log(f"wiki generation complete: {new_count} new entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
