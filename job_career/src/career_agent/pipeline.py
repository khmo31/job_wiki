"""로컬 매칭 파이프라인 - 사용자 프로필 기반 추천 기관 점수화"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from .tools import OntologyCheckTool, WikiReadOnlyTool
from .tools.custom_tool import (
    _is_group_keyword,
    _load_ontology_mappings,
    _load_wiki_index,
    _normalize_keyword,
)


def _log(message: str) -> None:
    try:
        print(f"[career_pipeline] {message}", file=sys.stderr)
    except Exception:
        pass


def _extract_candidate_keywords(user_profile: str) -> list[str]:
    profile = user_profile.strip()
    if not profile:
        return []

    ontology_mappings, _ = _load_ontology_mappings()
    profile_case = profile.casefold()

    candidates: list[str] = []
    candidates.extend(re.findall(r"[가-힣A-Za-z0-9]{2,}", profile))

    for standard_keyword, synonyms in ontology_mappings.items():
        terms = [standard_keyword, *synonyms]
        if any(term and term.casefold() in profile_case for term in terms):
            candidates.append(standard_keyword)

    ordered: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        cleaned = candidate.strip()
        if len(cleaned) < 2 or _is_group_keyword(cleaned):
            continue
        normalized = _normalize_keyword(cleaned)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(cleaned)

    return ordered[:25]


def _extract_validated_keywords(candidate_keywords: list[str]) -> list[str]:
    if not candidate_keywords:
        return []

    validation_input = ", ".join(candidate_keywords)
    ontology_tool = OntologyCheckTool()
    validated_text = ontology_tool._run(validation_input)

    validated_keywords = [
        line.strip()
        for line in validated_text.splitlines()
        if line.strip().startswith("[[")
    ]

    if validated_keywords:
        return validated_keywords

    return [keyword for keyword in candidate_keywords if len(keyword.strip()) >= 2 and not _is_group_keyword(keyword)]


def _extract_candidate_files(search_output: str) -> list[str]:
    candidate_files: list[str] = []
    for line in search_output.splitlines():
        line = line.strip()
        if not line:
            continue
        match = re.match(r"^\d+\.\s+([^\s(]+)", line)
        if match:
            candidate_files.append(match.group(1))
    return candidate_files


def _strip_brackets(value: str) -> str:
    return value.strip().replace("[[", "").replace("]]", "")


def _build_scoring_fragments(keyword: str) -> list[str]:
    fragments: list[str] = []
    seen: set[str] = set()

    def add(fragment: str) -> None:
        cleaned = fragment.strip()
        if len(cleaned) < 3:
            return
        normalized = _normalize_keyword(cleaned)
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        fragments.append(cleaned)

    add(keyword)
    for part in re.split(r"[\s/(),]+", keyword):
        add(part)

    return fragments


def _company_name(entry: dict[str, Any], file_name: str) -> str:
    company_field = str(entry.get("company") or "").strip()
    if company_field:
        match = re.search(r"\[\[(.+?)\]\]", company_field)
        if match:
            return match.group(1)
        return company_field

    parts = Path(file_name).stem.split("_")
    if len(parts) > 1:
        return parts[1]
    return Path(file_name).stem


def _collect_company_files(wiki_index: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for file_name, entry in wiki_index.items():
        company_name = _company_name(entry, file_name)
        company_key = _normalize_keyword(company_name)
        if not company_key:
            continue
        grouped.setdefault(company_key, []).append(file_name)
    return grouped


def _attach_related_files(recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    wiki_index, _ = _load_wiki_index()
    company_files = _collect_company_files(wiki_index)

    enriched: list[dict[str, Any]] = []
    for item in recommendations:
        if not isinstance(item, dict):
            continue

        enriched_item = dict(item)
        institution = str(enriched_item.get("institution") or enriched_item.get("company") or "").strip()
        if not institution:
            continue

        company_key = _normalize_keyword(institution)
        related_files = list(company_files.get(company_key, []))

        primary_file = str(enriched_item.get("file") or enriched_item.get("file_name") or "").strip()
        if primary_file:
            if primary_file in related_files:
                related_files = [primary_file] + [file_name for file_name in related_files if file_name != primary_file]
            else:
                related_files = [primary_file] + related_files

        deduplicated_files: list[str] = []
        seen_files: set[str] = set()
        for file_name in related_files:
            clean_file = str(file_name).strip()
            if not clean_file or clean_file in seen_files:
                continue
            seen_files.add(clean_file)
            deduplicated_files.append(clean_file)

        enriched_item["institution"] = institution
        enriched_item["file"] = primary_file or (deduplicated_files[0] if deduplicated_files else "")
        enriched_item["files"] = deduplicated_files
        enriched.append(enriched_item)

    return enriched


def _score_index_entries(
    wiki_index: dict[str, dict[str, Any]],
    validated_keywords: list[str],
    candidate_files: list[str],
) -> list[dict[str, Any]]:
    def score_scope(file_scope: set[str]) -> list[tuple[int, str, str, list[str]]]:
        scored_scope: list[tuple[int, str, str, list[str]]] = []
        for file_name, entry in wiki_index.items():
            if file_scope and file_name not in file_scope:
                continue

            company_field = str(entry.get("company") or "")
            title_field = str(entry.get("title") or "").casefold()
            summary_field = str(entry.get("summary") or "").casefold()
            entry_keywords = [str(keyword).strip() for keyword in entry.get("keywords") or [] if str(keyword).strip()]
            entry_keywords_norm = [_normalize_keyword(keyword) for keyword in entry_keywords if _normalize_keyword(keyword)]

            score = 0
            matched_keywords: list[str] = []

            for keyword in validated_keywords:
                clean_keyword = _strip_brackets(keyword)
                if not clean_keyword:
                    continue

                fragments = _build_scoring_fragments(clean_keyword)

                matched = False
                company_case = company_field.casefold()

                for fragment in fragments:
                    fragment_case = fragment.casefold()
                    fragment_norm = _normalize_keyword(fragment)

                    fragment_keyword_hit = False
                    fragment_title_company_hit = False

                    if fragment_norm and any(
                        fragment_norm == field_norm or fragment_norm in field_norm or field_norm in fragment_norm
                        for field_norm in entry_keywords_norm
                    ):
                        score += 5
                        matched = True
                        fragment_keyword_hit = True

                    if fragment_case in title_field or fragment_case in company_case:
                        score += 4
                        matched = True
                        fragment_title_company_hit = True

                    if (fragment_keyword_hit or fragment_title_company_hit) and fragment_case in summary_field:
                        score += 1
                        matched = True

                if matched:
                    matched_keywords.append(clean_keyword)

            if score > 0:
                scored_scope.append((score, file_name, _company_name(entry, file_name), matched_keywords))

        return scored_scope

    scored = score_scope(set(candidate_files) if candidate_files else set())
    if candidate_files and len(scored) < 5:
        seen = {file_name for _, file_name, _, _ in scored}
        expanded = score_scope(set(wiki_index.keys()))
        for item in expanded:
            if item[1] in seen:
                continue
            scored.append(item)

    scored.sort(key=lambda item: (-item[0], item[2], item[1]))

    unique: dict[str, dict[str, Any]] = {}
    for score, file_name, company_name, matched_keywords in scored:
        if score <= 0:
            continue
        if company_name in unique:
            continue
        unique[company_name] = {
            "institution": company_name,
            "file": file_name,
            "score": score,
            "matched_keywords": sorted({keyword for keyword in matched_keywords if keyword}),
        }
        if len(unique) >= 5:
            break

    return list(unique.values())


def build_fallback_report(user_profile: str) -> dict[str, Any]:
    candidate_keywords = _extract_candidate_keywords(user_profile)
    _log(f"fallback candidate keywords: {candidate_keywords}")

    validated_keywords = _extract_validated_keywords(candidate_keywords)
    _log(f"fallback validated keywords: {validated_keywords}")

    wiki_tool = WikiReadOnlyTool()
    search_query = ", ".join(_strip_brackets(keyword) for keyword in validated_keywords)
    search_output = wiki_tool._run(search_query or user_profile)
    candidate_files = _extract_candidate_files(search_output)
    _log(f"fallback candidate files: {candidate_files}")

    wiki_index, _ = _load_wiki_index()
    recommendations = _attach_related_files(_score_index_entries(wiki_index, validated_keywords, candidate_files))
    _log(f"fallback recommendations: {[item['institution'] for item in recommendations]}")

    return {"recommended_institutions": recommendations}


def generate_report(user_profile: str) -> dict[str, Any]:
    """사용자 프로필 기반 추천 기관 보고서 생성.
    
    1순위: LLM 키워드 추출 → Ontology 검증 → Wiki 스코어링
    2순위: 순수 로컬 (regex + Ontology + Wiki 스코어링)
    """
    # Try LLM-powered keyword extraction first
    try:
        from .llm_client import extract_keywords as llm_extract
        llm_keywords = llm_extract(user_profile)
        if llm_keywords and len(llm_keywords) >= 2:
            _log(f"LLM extracted keywords: {llm_keywords}")
            validated = _extract_validated_keywords(llm_keywords)
            if validated:
                _log(f"LLM path validated keywords: {validated}")
                wiki_tool = WikiReadOnlyTool()
                search_query = ", ".join(_strip_brackets(k) for k in validated)
                search_output = wiki_tool._run(search_query)
                candidate_files = _extract_candidate_files(search_output)
                wiki_index, _ = _load_wiki_index()
                recommendations = _attach_related_files(
                    _score_index_entries(wiki_index, validated, candidate_files)
                )
                if recommendations:
                    return {"recommended_institutions": recommendations}
    except Exception as exc:
        _log(f"LLM keyword path failed: {exc}")

    # Fallback to pure local matching
    _log("falling back to local matching")
    return build_fallback_report(user_profile)
