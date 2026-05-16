#!/usr/bin/env python3
"""Suggested_Keywords.json → Ontology_Map.json 자동 병합

GitHub Actions에서 수집→Wiki 변환 후 실행.
Suggested_Keywords.json에서 status="suggested"인 키워드를
Ontology_Map.json에 신규 표준 키워드로 자동 등록한다.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WIKI_META_DIR = PROJECT_ROOT / "job_wiki" / "20_Meta"
WIKI_SKILLS_DIR = PROJECT_ROOT / "job_wiki" / "10_Wiki" / "Entities" / "Skills"
ONTOLOGY_PATH = WIKI_META_DIR / "Ontology_Map.json"
SUGGESTED_PATH = WIKI_META_DIR / "Suggested_Keywords.json"


def _log(msg: str) -> None:
    print(f"[merge_ontology] {msg}", file=sys.stderr)


def _load_json(path: Path) -> dict[str, Any] | list | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        _log(f"failed to load {path.name}: {e}")
        return None


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"saved: {path.name}")


def _normalize_keyword(kw: str) -> str:
    """Normalize keyword for comparison."""
    cleaned = kw.strip().replace("[[", "").replace("]]", "")
    cleaned = re.sub(r"[^\w]", "", cleaned)
    return cleaned.casefold()


def _generate_skill_pages(mappings: dict[str, list[str]]) -> None:
    """Ontology 키워드 → Entities/Skills/ 페이지 자동 생성.

    Ontology_Map.json의 각 표준 키워드에 대해
    Entities/Skills/{키워드}.md 파일이 없으면 생성한다.
    """
    WIKI_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    generated = 0

    for std_keyword in mappings:
        # Determine domain from keyword prefix heuristics
        domain = "일반"
        if "의료" in std_keyword or "보건" in std_keyword:
            domain = "보건.의료"
        elif "연구" in std_keyword:
            domain = "연구"
        elif "재무" in std_keyword or "예산" in std_keyword:
            domain = "경영.회계.사무"
        elif "운전" in std_keyword or "경로" in std_keyword:
            domain = "운전.운송"
        elif "안전" in std_keyword:
            domain = "안전.관리"

        # Clean filename: remove special chars
        safe_name = re.sub(r'[\\/:*?"<>|]', '', std_keyword).strip()
        if not safe_name:
            continue

        skill_path = WIKI_SKILLS_DIR / f"{safe_name}.md"
        if skill_path.exists():
            continue

        # Get related ontology keywords (synonyms from the mapping)
        synonyms = mappings.get(std_keyword, [])
        related_links = ""
        if synonyms:
            syn_lines = "\n".join(f"  - [[{syn}]]" for syn in synonyms if syn != std_keyword)
            if syn_lines:
                related_links = f"\n## 동의어\n{syn_lines}"

        page_content = (
            f"---\n"
            f"name: \"{std_keyword}\"\n"
            f"domain: \"[[{domain}]]\"\n"
            f"---\n"
            f"\n"
            f"# {std_keyword}\n"
            f"\n"
            f"자동 생성된 역량/기술 페이지입니다.\n"
            f"{related_links}\n"
        )

        skill_path.write_text(page_content, encoding="utf-8")
        generated += 1
        _log(f"created skill page: {safe_name}.md (domain={domain})")

    if generated == 0:
        _log("no new skill pages needed")


def _keyword_exists_in_ontology(kw: str, mappings: dict[str, list[str]]) -> bool:
    """Check if keyword already exists as standard key or synonym."""
    nk = _normalize_keyword(kw)
    # Check as standard key
    for std_key in mappings:
        if _normalize_keyword(std_key) == nk:
            return True
        # Check as synonym
        for syn in mappings[std_key]:
            if _normalize_keyword(syn) == nk:
                return True
    return False


def main() -> int:
    # Load ontology
    ontology = _load_json(ONTOLOGY_PATH)
    if ontology is None:
        ontology = {
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "version": "v1",
            "mappings": {},
        }
    mappings: dict[str, list[str]] = ontology.get("mappings", {})
    if not isinstance(mappings, dict):
        mappings = {}

    # Load suggested keywords
    suggested = _load_json(SUGGESTED_PATH)
    if not suggested or not isinstance(suggested, list):
        _log("no suggested keywords to merge")
        return 0

    new_entries = 0
    duplicates = 0
    updated_suggestions: list[dict[str, Any]] = []

    for entry in suggested:
        if not isinstance(entry, dict):
            updated_suggestions.append(entry)
            continue

        status = entry.get("status", "suggested")
        keyword = entry.get("keyword", "").strip()
        if not keyword:
            updated_suggestions.append(entry)
            continue

        # Skip already processed entries
        if status in ("merged", "duplicate", "skipped"):
            updated_suggestions.append(entry)
            continue

        # Check if already exists in ontology
        if _keyword_exists_in_ontology(keyword, mappings):
            entry["status"] = "duplicate"
            entry["merged_at"] = datetime.now(timezone.utc).isoformat()
            duplicates += 1
            _log(f"duplicate (already in ontology): {keyword}")
        else:
            # Add as new standard keyword with empty synonyms
            mappings[keyword] = []
            entry["status"] = "merged"
            entry["merged_at"] = datetime.now(timezone.utc).isoformat()
            new_entries += 1
            _log(f"merged new keyword: {keyword}")

        updated_suggestions.append(entry)

    # Save updated ontology
    ontology["mappings"] = mappings
    ontology["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    _save_json(ONTOLOGY_PATH, ontology)

    # Save updated suggestions
    _save_json(SUGGESTED_PATH, updated_suggestions)

    # Generate Skill pages for newly added keywords
    if new_entries > 0:
        _generate_skill_pages(mappings)

    _log(f"merge complete: {new_entries} new, {duplicates} duplicates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
