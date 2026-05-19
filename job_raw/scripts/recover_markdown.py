#!/usr/bin/env python3
"""기존 json_archive에서 .md 파일 복구 스크립트.

analyze_objective_dna()가 save_markdown()보다 먼저 index를 업데이트하는 버그로 인해
00_Raw/에 .md 파일이 생성되지 않은 415개 json_archive를 읽어
마크다운 파일을 재생성하고 index.json의 filename 필드를 업데이트한다.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Paths
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "00_Raw"
INDEX_PATH = RAW_DIR / "index.json"
ARCHIVE_DIR = RAW_DIR / "json_archive"


def _log(msg: str) -> None:
    print(f"[recover] {msg}", file=sys.stderr)


def _render_markdown(rd: dict, raw_list: dict, analysis: dict, alio_id: str) -> str:
    """Render a markdown file from archive data, matching formatter.py layout."""
    company = raw_list.get("instNm") or rd.get("company") or "Unknown"
    title = raw_list.get("recrutPbancTtl") or rd.get("title") or "Untitled"
    date = raw_list.get("pbancBgngYmd") or rd.get("posted_date") or ""
    skills = analysis.get("skills_found", []) or []
    job_nature = analysis.get("job_nature", "실무/혼합")
    complexity = analysis.get("complexity", "medium")
    domain = analysis.get("domain_context", "")
    core_logic = analysis.get("core_logic", "")
    latent = analysis.get("latent_skills", []) or []

    front = ["---"]
    front.append(f"title: {title}")
    front.append("source: ALIO")
    front.append(f"date: {date}")
    front.append(f"company: {company}")
    if alio_id:
        front.append(f"id: {alio_id}")
    front.append("skills:")
    for s in skills:
        front.append(f'  - "[[{s}]]"')
    front.append("objective_metadata:")
    front.append("  skills_found:")
    for s in skills:
        front.append(f'    - "[[{s}]]"')
    front.append(f'  job_nature: "{job_nature}"')
    front.append(f'  complexity: "{complexity}"')
    if domain:
        front.append(f'  domain_context: "{domain}"')
    front.append("---")

    body = [f"# {title}", "", "## 요약"]
    desc = raw_list.get("aplyQlfcCn") or rd.get("description", "")
    body.append(desc.strip() if desc else "")
    body.append("")
    body.append("## Matching Reasoning")
    for s in skills:
        body.append(f"- [[{s}]]: 공고에서 명시적 또는 추론적으로 관찰됨")

    body.extend(["", "## Objective Summary (자동분석)"])
    if core_logic:
        body.append(f"- 핵심 로직: {core_logic}")
    if domain:
        body.append(f"- 도메인 컨텍스트: {domain}")
    if latent:
        body.append(f"- 잠재적 필요 기술: {', '.join(latent)}")

    body.extend(["", "---", "## 원본 공고(아카이브)"])
    raw_keys = [
        ("기관명", "instNm"), ("공고제목", "recrutPbancTtl"), ("채용구분", "recrutSeNm"),
        ("응시자격", "aplyQlfcCn"), ("우대사항", "prefCondCn"), ("우대내용", "prefCn"),
        ("요건", "requirements"), ("공고시작", "pbancBgngYmd"), ("공고종료", "pbancEndYmd"),
        ("근무지역", "workRgnNmLst"), ("전형방법", "scrnprcdrMthdExpln"),
        ("원문URL", "srcUrl"), ("NCS카테고리", "ncsCdNmLst"),
    ]
    for label, key in raw_keys:
        val = raw_list.get(key) or rd.get(key)
        if val:
            body.append(f"- {label}: {str(val).strip()}")

    body.extend(["", "### Raw JSON", "```json",
                 json.dumps(rd, ensure_ascii=False, indent=2), "```"])
    return "\n".join(front + [""] + body)


def _safe_filename(text: str) -> str:
    """Clean string for use in filename."""
    text = re.sub(r'[<>:"/\\|?*]+', "", text)
    text = re.sub(r"\s+", "_", text)
    return text


def _filename(alio_id: str, company: str, title: str, date_str: str) -> str:
    date_key = date_str.replace("-", "")[:8] if date_str else "unknown"
    clean_company = _safe_filename(company)[:20] if company else "unknown"
    clean_title = _safe_filename(title)[:30] if title else "untitled"
    clean_id = alio_id.replace("-", "_")
    return f"{date_key}_{clean_id}_{clean_company}_{clean_title}.md"


def main() -> int:
    # Load existing index
    if INDEX_PATH.exists():
        index = json.loads(INDEX_PATH.read_text(encoding="utf-8") or "{}")
    else:
        index = {}
    _log(f"index entries: {len(index)}")

    # Load all json_archives
    archives = sorted(ARCHIVE_DIR.glob("*.json"))
    _log(f"json_archives found: {len(archives)}")

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    recovered = 0
    skipped_exist = 0
    errors = 0

    for ap in archives:
        alio_id = ap.stem
        try:
            data = json.loads(ap.read_text(encoding="utf-8"))
        except Exception as e:
            _log(f"  ERROR reading {ap.name}: {e}")
            errors += 1
            continue

        rd = data.get("raw", {})
        if not isinstance(rd, dict):
            rd = {}
        analysis = data.get("analysis", {})

        # Support three raw data formats:
        # 1. Nested: {"list": {"instNm": ...}, "detail": {...}}  (detail-fetched ALIO)
        # 2. Flat: {"instNm": ..., "recrutPbancTtl": ...}        (list-only ALIO)
        # 3. Empty: {}
        raw_list = rd.get("list", {}) if isinstance(rd.get("list"), dict) else {}
        is_flat = bool(not raw_list and rd)
        src = raw_list if raw_list else rd  # Use nested list or flat data

        # Check if truly empty (no identifiable fields at all)
        has_content = bool(src.get("instNm") or src.get("recrutPbancTtl") or src.get("company"))
        if not has_content:
            _log(f"  SKIP {alio_id}: empty raw data")
            if alio_id not in index:
                index[alio_id] = {
                    "filename": "",
                    "content_hash": analysis.get("content_hash", ""),
                    "last_analyzed_at": analysis.get("analyzed_at", ""),
                }
            continue

        company = src.get("instNm") or rd.get("company") or "unknown"
        title = src.get("recrutPbancTtl") or rd.get("title") or "untitled"
        date_str = src.get("pbancBgngYmd") or rd.get("posted_date") or ""

        filename = _filename(alio_id, company, title, date_str)
        md_path = RAW_DIR / filename

        if md_path.exists():
            skipped_exist += 1
            continue

        # Render markdown
        md = _render_markdown(rd, src, analysis, alio_id)
        md_path.write_text(md, encoding="utf-8")
        recovered += 1

        # Update index
        entry = index.get(alio_id)
        if isinstance(entry, str):
            entry = {"filename": entry}
        elif entry is None:
            entry = {}
        entry["filename"] = filename
        if analysis.get("analyzed_at"):
            entry["last_analyzed_at"] = analysis.get("analyzed_at")
        index[alio_id] = entry

        if recovered % 50 == 0:
            _log(f"  progress: {recovered} recovered...")

    # Save updated index
    INDEX_PATH.write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    _log(f"\nComplete: recovered={recovered}, skipped_exist={skipped_exist}, errors={errors}")
    _log(f"index now has {len(index)} entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
