#!/usr/bin/env python3
"""Suggested_Keywords.json → Ontology_Map.json 자동 병합 (의미 기반)

변경 사항:
- 기존 exact match + 정규화 비교
- **추가** n-gram 유사도 (character-level trigrams)
- **추가** Levenshtein edit distance 정규화
- **추가** 신규 키워드가 기존 키워드와 유사하면 synonyms에 등록
- **추가** analyzer의 analysis.new_keywords 필드도 자동 수집 (wiki_generator가 생성한 Suggested와 별도)
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


# ── 정규화 ──
def _normalize_keyword(kw: str) -> str:
    """정규화: 특수문자 제거, casefold."""
    cleaned = kw.strip().replace("[[", "").replace("]]", "")
    cleaned = re.sub(r"[^\w가-힣]", "", cleaned)
    return cleaned.casefold()


# ── n-gram 유사도 ──
def _ngrams(s: str, n: int = 3) -> set[str]:
    """Character-level n-gram set."""
    return {s[i:i + n] for i in range(len(s) - n + 1)}


def _ngram_similarity(a: str, b: str) -> float:
    """n-gram Jaccard similarity (character trigrams)."""
    a_norm = _normalize_keyword(a)
    b_norm = _normalize_keyword(b)
    if not a_norm or not b_norm:
        return 0.0
    a_grams = _ngrams(a_norm, 3)
    b_grams = _ngrams(b_norm, 3)
    if not a_grams or not b_grams:
        return 0.0
    intersection = a_grams & b_grams
    union = a_grams | b_grams
    return len(intersection) / len(union)


# ── Levenshtein 유사도 ──
def _levenshtein_similarity(a: str, b: str) -> float:
    """Normalized edit distance similarity (1 - edit_distance / max_len)."""
    a_norm = _normalize_keyword(a)
    b_norm = _normalize_keyword(b)
    if not a_norm and not b_norm:
        return 1.0
    if not a_norm or not b_norm:
        return 0.0

    # iterative DP
    m, n = len(a_norm), len(b_norm)
    if m > n:
        a_norm, b_norm = b_norm, a_norm
        m, n = n, m

    prev = list(range(n + 1))
    for i in range(1, m + 1):
        curr = [i] + [0] * n
        for j in range(1, n + 1):
            cost = 0 if a_norm[i - 1] == b_norm[j - 1] else 1
            curr[j] = min(
                prev[j] + 1,
                curr[j - 1] + 1,
                prev[j - 1] + cost,
            )
        prev = curr
    edit_dist = prev[n]
    return 1.0 - (edit_dist / max(m, n))


# ── 복합 유사도 ──
def _combined_similarity(a: str, b: str) -> float:
    """n-gram + Levenshtein 가중 평균."""
    ngram = _ngram_similarity(a, b)
    lev = _levenshtein_similarity(a, b)
    # n-gram이 짧은 문자열에서 더 좋고, Levenshtein이 긴 문자열 보완
    return max(ngram, lev) * 0.7 + min(ngram, lev) * 0.3


def _best_ontology_match(new_kw: str, existing_standards: list[str],
                         existing_synonyms: list[str]) -> tuple[str | None, float]:
    """신규 키워드와 가장 유사한 기존 키워드 찾기.

    Returns (best_match_standard_keyword, similarity).
    - best_match가 None이면 완전 신규
    """
    all_candidates = list(dict.fromkeys(existing_standards + existing_synonyms))
    best_match: str | None = None
    best_sim = 0.0

    for candidate in all_candidates:
        sim = _combined_similarity(new_kw, candidate)
        if sim > best_sim:
            best_sim = sim
            best_match = candidate

    return best_match, best_sim


def _keyword_exists_in_ontology(kw: str, mappings: dict[str, list[str]]) -> bool:
    """Check if keyword already exists as standard key or synonym."""
    nk = _normalize_keyword(kw)
    for std_key in mappings:
        if _normalize_keyword(std_key) == nk:
            return True
        for syn in mappings[std_key]:
            if _normalize_keyword(syn) == nk:
                return True
    return False


def _generate_skill_pages(mappings: dict[str, list[str]]) -> None:
    """Ontology 키워드 → Entities/Skills/ 페이지 자동 생성."""
    WIKI_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
    generated = 0

    for std_keyword in mappings:
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

        safe_name = re.sub(r'[\\/:*?"<>|]', '', std_keyword).strip()
        if not safe_name:
            continue

        skill_path = WIKI_SKILLS_DIR / f"{safe_name}.md"
        if skill_path.exists():
            continue

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


# ── 분석 결과에서 new_keywords 수집 ──
def _collect_new_keywords_from_analysis(raw_root: Path) -> list[dict[str, Any]]:
    """json_archive 내 모든 analysis 파일을 스캔하여 new_keywords 필드 수집.

    analyzer가 analysis["new_keywords"]에 저장한 신규 키워드를
    Suggested_Keywords.json 포맷으로 변환하여 반환.
    """
    json_archive_dir = raw_root / "json_archive"
    if not json_archive_dir.exists():
        return []

    collected: list[dict[str, Any]] = []
    for fpath in sorted(json_archive_dir.iterdir()):
        if not fpath.name.endswith(".json"):
            continue
        alio_id = fpath.stem
        try:
            data = json.loads(fpath.read_text(encoding="utf-8"))
            analysis = data.get("analysis", {})
            if not isinstance(analysis, dict):
                continue
            new_kws = analysis.get("new_keywords", [])
            if not new_kws or not isinstance(new_kws, list):
                continue
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

    return collected


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

    # ── 1) Suggested_Keywords.json 병합 ──
    suggested = _load_json(SUGGESTED_PATH)
    all_new_entries = []
    if suggested and isinstance(suggested, list):
        all_new_entries.extend(suggested)

    # ── 2) 분석 결과에서 new_keywords 수집 ──
    raw_root = PROJECT_ROOT / "job_raw" / "00_Raw"
    analysis_new = _collect_new_keywords_from_analysis(raw_root)
    if analysis_new:
        _log(f"collected {len(analysis_new)} new keywords from analysis results")
        all_new_entries.extend(analysis_new)

    if not all_new_entries:
        _log("no suggested keywords to merge")
        # Still save ontology if empty
        _save_json(ONTOLOGY_PATH, ontology)
        return 0

    # ── 기존 표준 키워드 + 동의어 목록 ──
    existing_standards = list(mappings.keys())
    existing_synonyms = []
    for syns in mappings.values():
        existing_synonyms.extend(syns)

    new_entries = 0
    duplicates = 0
    merged_as_synonym = 0
    updated_suggestions: list[dict[str, Any]] = []

    # Similarity thresholds
    EXACT_SIM_THRESHOLD = 0.85   # synonym 등록
    WEAK_SIM_THRESHOLD = 0.60    # 여전히 유사하지만 synonym 등록은 보류 → 수동 검토 플래그

    for entry in all_new_entries:
        if not isinstance(entry, dict):
            updated_suggestions.append(entry)
            continue

        status = entry.get("status", "suggested")
        keyword = entry.get("keyword", "").strip()
        if not keyword:
            updated_suggestions.append(entry)
            continue

        # Skip already processed
        if status in ("merged", "duplicate", "skipped"):
            updated_suggestions.append(entry)
            continue

        # 1st pass: exact match (fast)
        if _keyword_exists_in_ontology(keyword, mappings):
            entry["status"] = "duplicate"
            entry["merged_at"] = datetime.now(timezone.utc).isoformat()
            duplicates += 1
            _log(f"exact duplicate: {keyword}")
            updated_suggestions.append(entry)
            continue

        # 2nd pass: semantic similarity
        best_match, best_sim = _best_ontology_match(keyword, existing_standards, existing_synonyms)

        if best_match and best_sim >= EXACT_SIM_THRESHOLD:
            # Very similar → add as synonym to the best matching standard keyword
            std_key = best_match
            # Check if best_match is a synonym -> map to its standard key
            for sk, syns in mappings.items():
                if best_match in syns:
                    std_key = sk
                    break
                if _normalize_keyword(best_match) == _normalize_keyword(sk):
                    std_key = sk
                    break

            if keyword not in mappings[std_key]:
                mappings[std_key].append(keyword)
            entry["status"] = "merged"
            entry["merged_at"] = datetime.now(timezone.utc).isoformat()
            entry["synonym_of"] = std_key
            merged_as_synonym += 1
            _log(f"merged as synonym: \"{keyword}\" → \"{std_key}\" (sim={best_sim:.2f})")

        elif best_match and best_sim >= WEAK_SIM_THRESHOLD:
            # Somewhat similar → flag for review, add as weak synonym
            entry["status"] = "suggested"
            entry["similarity"] = round(best_sim, 3)
            entry["similar_to"] = best_match
            entry["note"] = "유사하지만 불확실 — 수동 검토 필요"
            _log(f"weak match: \"{keyword}\" ~ \"{best_match}\" (sim={best_sim:.2f}) — needs review")
            updated_suggestions.append(entry)
            continue

        else:
            # Completely new keyword
            mappings[keyword] = []
            existing_standards.append(keyword)
            entry["status"] = "merged"
            entry["merged_at"] = datetime.now(timezone.utc).isoformat()
            new_entries += 1
            _log(f"merged new keyword: {keyword}")

        updated_suggestions.append(entry)

    # ── Save ──
    ontology["mappings"] = mappings
    ontology["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    _save_json(ONTOLOGY_PATH, ontology)

    _save_json(SUGGESTED_PATH, updated_suggestions)

    if new_entries + merged_as_synonym > 0:
        _generate_skill_pages(mappings)

    _log(
        f"merge complete: {new_entries} new standards, "
        f"{merged_as_synonym} as synonyms, {duplicates} exact duplicates"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
