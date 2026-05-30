"""로컬 매칭 파이프라인 - 사용자 프로필 기반 추천 기관 점수화"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from functools import lru_cache

from .tools import WikiReadOnlyTool
from .tools.custom_tool import (
    _is_group_keyword,
    _load_wiki_index,
    _normalize_keyword,
)


FACET_INDEX_FILE = Path(__file__).resolve().parents[3] / "job_wiki" / "20_Meta" / "Facet_Index.json"
FOLLOW_UP_CATEGORY_ORDER = [
    "education",
    "hire_type",
    "preference",
    "region",
    "qualification",
    "recruitment_type",
    "process",
    "ncs",
]

FOLLOW_UP_CATEGORY_LABELS = {
    "ncs": "NCS",
    "education": "학력",
    "hire_type": "고용형태",
    "preference": "우대/선호",
    "region": "지역",
    "qualification": "자격요건",
    "recruitment_type": "채용유형",
    "process": "전형",
}

PROFILE_TERM_WEIGHT = 3.0
CORE_PROFILE_TERM_WEIGHT = 6.0
SUPPORT_PROFILE_TERM_WEIGHT = 3.0
FOLLOW_UP_PROFILE_TERM_WEIGHT = 1.0
SUPPLEMENTAL_TERM_WEIGHT = 1.0
MATCH_RATE_THRESHOLD = 50
FOLLOW_UP_NONE_LABEL = "상관없음"
FOLLOW_UP_NONE_VALUE = "__none__"


@lru_cache(maxsize=1)
def _load_facet_keywords() -> list[str]:
    if not FACET_INDEX_FILE.exists():
        return []

    try:
        payload = json.loads(FACET_INDEX_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

    categories = payload.get("categories", {}) if isinstance(payload, dict) else {}
    if not isinstance(categories, dict):
        return []

    keywords: list[str] = []
    seen: set[str] = set()

    for category_key, label_map in categories.items():
        if not isinstance(category_key, str) or not isinstance(label_map, dict):
            continue

        for facet_label, items in label_map.items():
            if not isinstance(facet_label, str) or not isinstance(items, list):
                continue

            for candidate in (category_key, facet_label):
                normalized = _normalize_keyword(candidate)
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                keywords.append(candidate)

    return keywords


@lru_cache(maxsize=1)
def _load_facet_catalog() -> dict[str, list[dict[str, Any]]]:
    if not FACET_INDEX_FILE.exists():
        return {}

    try:
        payload = json.loads(FACET_INDEX_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

    categories = payload.get("categories", {}) if isinstance(payload, dict) else {}
    if not isinstance(categories, dict):
        return {}

    catalog: dict[str, list[dict[str, Any]]] = {}
    for category_key, label_map in categories.items():
        if not isinstance(category_key, str) or not isinstance(label_map, dict):
            continue

        label_entries: list[dict[str, Any]] = []
        for facet_label, items in label_map.items():
            if not isinstance(facet_label, str) or not isinstance(items, list):
                continue

            item_count = 0
            sample_titles: list[str] = []
            sample_companies: list[str] = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                item_count += 1
                title = str(item.get("title") or "").strip()
                company = str(item.get("company") or "").strip()
                if title and title not in sample_titles:
                    sample_titles.append(title)
                if company and company not in sample_companies:
                    sample_companies.append(company)

            label_entries.append(
                {
                    "label": facet_label,
                    "count": item_count,
                    "sample_titles": sample_titles[:2],
                    "sample_companies": sample_companies[:2],
                }
            )

        label_entries.sort(key=lambda item: (-int(item.get("count") or 0), str(item.get("label") or "")))
        catalog[category_key] = label_entries

    return catalog


def _log(message: str) -> None:
    try:
        print(f"[career_pipeline] {message}", file=sys.stderr)
    except Exception:
        pass


def _extract_candidate_keywords(user_profile: str) -> list[str]:
    profile = user_profile.strip()
    if not profile:
        return []

    facet_keywords = _load_facet_keywords()
    profile_case = profile.casefold()

    candidates: list[str] = []
    candidates.extend(re.findall(r"[가-힣A-Za-z0-9]{2,}", profile))

    for keyword in facet_keywords:
        if keyword and keyword.casefold() in profile_case:
            candidates.append(keyword)

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

    facet_keywords = _load_facet_keywords()
    facet_norms = {_normalize_keyword(keyword) for keyword in facet_keywords if _normalize_keyword(keyword)}

    validated: list[str] = []
    seen: set[str] = set()

    for keyword in candidate_keywords:
        clean_keyword = keyword.strip()
        if len(clean_keyword) < 2 or _is_group_keyword(clean_keyword):
            continue

        normalized = _normalize_keyword(clean_keyword)
        if not normalized or normalized in seen:
            continue

        if facet_norms and not any(
            normalized == facet_norm or normalized in facet_norm or facet_norm in normalized
            for facet_norm in facet_norms
        ):
            continue

        seen.add(normalized)
        validated.append(clean_keyword)

    return validated[:12]


def _merge_keywords(*keyword_groups: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()

    for keyword_group in keyword_groups:
        for keyword in keyword_group:
            clean_keyword = str(keyword).strip()
            if len(clean_keyword) < 2:
                continue
            normalized = _normalize_keyword(clean_keyword)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(clean_keyword)

    return merged


def _parse_supplemental_selections(
    supplemental_selections: dict[str, list[str]] | None,
) -> tuple[dict[str, list[str]], set[str]]:
    if not supplemental_selections or not isinstance(supplemental_selections, dict):
        return {}, set()

    supplemental_terms_by_category: dict[str, list[str]] = {}
    neutral_categories: set[str] = set()

    for category, values in supplemental_selections.items():
        category_key = str(category).strip()
        if not category_key:
            continue

        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list):
            continue

        clean_values = [str(value).strip() for value in values if str(value).strip()]
        if not clean_values:
            continue

        if any(value == FOLLOW_UP_NONE_LABEL or value == FOLLOW_UP_NONE_VALUE for value in clean_values):
            neutral_categories.add(category_key)
            continue

        category_terms: list[str] = []
        seen: set[str] = set()
        for clean_value in clean_values:
            if len(clean_value) < 2:
                continue
            normalized = _normalize_keyword(clean_value)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            category_terms.append(clean_value)

        if category_terms:
            supplemental_terms_by_category[category_key] = category_terms

    return supplemental_terms_by_category, neutral_categories


def _build_weighted_scoring_terms(
    profile_terms: list[str],
    supplemental_weighted_terms: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    weighted_terms: list[dict[str, Any]] = []

    for keyword in profile_terms:
        clean_keyword = str(keyword).strip()
        if len(clean_keyword) < 2:
            continue
        weighted_terms.append({"keyword": clean_keyword, "source": "profile", "category": "profile", "weight": PROFILE_TERM_WEIGHT})

    weighted_terms.extend(supplemental_weighted_terms)

    return weighted_terms


def _extract_profile_keyword_plan(user_profile: str) -> dict[str, list[str]] | None:
    try:
        from .llm_client import extract_keyword_plan as llm_extract_plan

        plan = llm_extract_plan(user_profile)
        if plan:
            _log(
                "LLM keyword plan: "
                f"core={plan.get('core_keywords', [])}, "
                f"support={plan.get('support_keywords', [])}, "
                f"follow_up={plan.get('follow_up_keywords', [])}"
            )
        return plan
    except Exception as exc:
        _log(f"LLM keyword plan failed: {exc}")
        return None


def _build_profile_weighted_term_groups(
    profile_plan: dict[str, list[str]] | None,
    fallback_keywords: list[str] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    grouped_terms: dict[str, list[dict[str, Any]]] = {
        "core": [] ,
        "support": [],
        "follow_up": [],
    }
    seen: set[str] = set()

    def append_terms(target_group: str, keywords: list[str], weight: float, source: str) -> None:
        for keyword in keywords:
            clean_keyword = str(keyword).strip()
            if len(clean_keyword) < 2 or _is_group_keyword(clean_keyword):
                continue
            normalized = _normalize_keyword(clean_keyword)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            grouped_terms[target_group].append(
                {
                    "keyword": clean_keyword,
                    "source": source,
                    "category": source,
                    "weight": weight,
                }
            )

    if profile_plan:
        append_terms("core", list(profile_plan.get("core_keywords", [])), CORE_PROFILE_TERM_WEIGHT, "profile_core")
        append_terms("support", list(profile_plan.get("support_keywords", [])), SUPPORT_PROFILE_TERM_WEIGHT, "profile_support")
        append_terms("follow_up", list(profile_plan.get("follow_up_keywords", [])), FOLLOW_UP_PROFILE_TERM_WEIGHT, "profile_follow_up")

    if not any(grouped_terms.values()) and fallback_keywords:
        append_terms("core", list(fallback_keywords), PROFILE_TERM_WEIGHT, "profile")

    return grouped_terms


def _build_profile_weighted_terms(
    profile_plan: dict[str, list[str]] | None,
    fallback_keywords: list[str] | None = None,
) -> list[dict[str, Any]]:
    grouped_terms = _build_profile_weighted_term_groups(profile_plan, fallback_keywords)
    return [*grouped_terms["core"], *grouped_terms["support"], *grouped_terms["follow_up"]]


def _log_weighted_term_groups(weighted_terms: list[dict[str, Any]]) -> None:
    grouped: dict[str, list[tuple[str, float]]] = {}
    for term in weighted_terms:
        keyword = str(term.get("keyword") or "").strip()
        if not keyword:
            continue
        source = str(term.get("source") or "").strip() or "unknown"
        grouped.setdefault(source, []).append((keyword, float(term.get("weight") or 0.0)))

    for source in ("profile_core", "profile_support", "profile_follow_up", "profile", "supplemental"):
        if source not in grouped:
            continue
        _log(f"{source} terms: {grouped[source]}")

    other_sources = sorted(source for source in grouped.keys() if source not in {"profile_core", "profile_support", "profile_follow_up", "profile", "supplemental"})
    for source in other_sources:
        _log(f"{source} terms: {grouped[source]}")


def _load_category_labels(category_key: str) -> list[str]:
    catalog = _load_facet_catalog()
    label_entries = catalog.get(category_key, [])
    if not label_entries:
        return []

    labels: list[str] = []
    seen: set[str] = set()
    for entry in label_entries:
        label = str(entry.get("label") or "").strip()
        if not label:
            continue
        normalized = _normalize_keyword(label)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        labels.append(label)

    return labels


def _build_supplemental_weighted_terms(
    supplemental_terms_by_category: dict[str, list[str]],
    neutral_categories: set[str],
) -> list[dict[str, Any]]:
    weighted_terms: list[dict[str, Any]] = []

    category_keys = sorted(set(supplemental_terms_by_category.keys()) | set(neutral_categories))
    for category_key in category_keys:
        selected_terms = list(supplemental_terms_by_category.get(category_key, []))
        if category_key in neutral_categories:
            selected_terms = _load_category_labels(category_key)

        unique_terms: list[str] = []
        seen: set[str] = set()
        for term in selected_terms:
            clean_term = str(term).strip()
            if len(clean_term) < 2:
                continue
            normalized = _normalize_keyword(clean_term)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            unique_terms.append(clean_term)

        if not unique_terms:
            continue

        term_weight = SUPPLEMENTAL_TERM_WEIGHT / len(unique_terms)
        for term in unique_terms:
            weighted_terms.append(
                {
                    "keyword": term,
                    "source": "supplemental",
                    "category": category_key,
                    "weight": term_weight,
                }
            )

    return weighted_terms


def _match_strength_for_entry(
    entry_keywords_norm: list[str],
    title_field: str,
    company_field: str,
    summary_field: str,
    keyword: str,
) -> float:
    fragments = _build_scoring_fragments(keyword)
    if not fragments:
        return 0.0

    best_strength = 0.0
    company_case = company_field.casefold()

    for fragment in fragments:
        fragment_case = fragment.casefold()
        fragment_norm = _normalize_keyword(fragment)

        keyword_hit = bool(
            fragment_norm
            and any(
                fragment_norm == field_norm or fragment_norm in field_norm or field_norm in fragment_norm
                for field_norm in entry_keywords_norm
            )
        )
        title_company_hit = fragment_case in title_field or fragment_case in company_case
        summary_hit = (keyword_hit or title_company_hit) and fragment_case in summary_field

        if keyword_hit:
            best_strength = max(best_strength, 1.0)
        elif title_company_hit:
            best_strength = max(best_strength, 0.8)
        elif summary_hit:
            best_strength = max(best_strength, 0.4)

    return best_strength


def _extract_candidate_files(search_output: str) -> list[str]:
    candidate_files: list[str] = []
    for line in search_output.splitlines():
        line = line.strip()
        if not line:
            continue
        match = re.match(r"^\d+\.\s+(.+?)\s+\(기관:", line)
        if not match:
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
        if len(cleaned) < 2:
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


def _display_category_name(category_key: str) -> str:
    return FOLLOW_UP_CATEGORY_LABELS.get(category_key, category_key.replace("_", " ").title())


def _detect_supported_categories(profile_text: str, scoring_keywords: list[str]) -> set[str]:
    catalog = _load_facet_catalog()
    if not catalog:
        return set()

    profile_case = profile_text.casefold()
    normalized_texts = [
        _normalize_keyword(profile_text),
        *(_normalize_keyword(keyword) for keyword in scoring_keywords),
    ]
    normalized_texts = [text for text in normalized_texts if text]

    supported: set[str] = set()
    for category_key, labels in catalog.items():
        category_norm = _normalize_keyword(category_key)
        if category_norm and (
            category_norm in profile_case or any(category_norm in text or text in category_norm for text in normalized_texts)
        ):
            supported.add(category_key)
            continue

        for label_entry in labels:
            label = str(label_entry.get("label") or "").strip()
            if not label:
                continue
            label_norm = _normalize_keyword(label)
            if not label_norm:
                continue
            if label.casefold() in profile_case or any(
                label_norm == text or label_norm in text or text in label_norm
                for text in normalized_texts
            ):
                supported.add(category_key)
                break

    return supported


def _build_follow_up_questions(profile_text: str, scoring_keywords: list[str]) -> list[dict[str, Any]]:
    catalog = _load_facet_catalog()
    if not catalog:
        return []

    supported_categories = _detect_supported_categories(profile_text, scoring_keywords)

    follow_up_questions: list[dict[str, Any]] = []
    for category_key in FOLLOW_UP_CATEGORY_ORDER:
        if category_key in supported_categories:
            continue

        label_entries = catalog.get(category_key, [])
        if not label_entries:
            continue

        options: list[dict[str, Any]] = []
        for entry in label_entries[:4]:
            label = str(entry.get("label") or "").strip()
            if not label:
                continue
            options.append(
                {
                    "value": label,
                    "label": label,
                    "count": int(entry.get("count") or 0),
                }
            )

        if not options:
            continue

        options = [
            {
                "value": FOLLOW_UP_NONE_VALUE,
                "label": FOLLOW_UP_NONE_LABEL,
                "count": 0,
            },
            *options,
        ]

        follow_up_questions.append(
            {
                "category": category_key,
                "title": _display_category_name(category_key),
                "multi_select": category_key in {"preference", "ncs"},
                "prompt": f"{_display_category_name(category_key)} 정보를 선택해 주세요.",
                "options": options,
            }
        )

    return follow_up_questions


def _attach_related_files(
    recommendations: list[dict[str, Any]],
    file_match_rates: dict[str, int] | None = None,
    minimum_match_rate: int = MATCH_RATE_THRESHOLD,
) -> list[dict[str, Any]]:
    wiki_index, _ = _load_wiki_index()
    company_files = _collect_company_files(wiki_index)
    file_match_rates = file_match_rates or {}

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
            if int(file_match_rates.get(clean_file, 0) or 0) < minimum_match_rate:
                continue
            seen_files.add(clean_file)
            deduplicated_files.append(clean_file)

        enriched_item["institution"] = institution
        enriched_item["file"] = primary_file or (deduplicated_files[0] if deduplicated_files else "")
        enriched_item["files"] = deduplicated_files
        enriched.append(enriched_item)

    return enriched


def _score_index_entries_with_file_scores(
    wiki_index: dict[str, dict[str, Any]],
    weighted_terms: list[dict[str, Any]],
    candidate_files: list[str],
    limit: int | None = 5,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    def score_scope(file_scope: set[str]) -> list[tuple[int, float, str, str, list[str]]]:
        scored_scope: list[tuple[int, float, str, str, list[str]]] = []

        for file_name, entry in wiki_index.items():
            if file_scope and file_name not in file_scope:
                continue

            company_field = str(entry.get("company") or "")
            title_field = str(entry.get("title") or "").casefold()
            summary_field = str(entry.get("summary") or "").casefold()
            entry_keywords = [str(keyword).strip() for keyword in entry.get("keywords") or [] if str(keyword).strip()]
            entry_keywords_norm = [_normalize_keyword(keyword) for keyword in entry_keywords if _normalize_keyword(keyword)]

            matched_keywords: list[str] = []
            weighted_score = 0.0
            total_possible_weight = 0.0

            for term in weighted_terms:
                keyword = str(term.get("keyword") or "").strip()
                clean_keyword = _strip_brackets(keyword)
                if not clean_keyword:
                    continue

                term_weight = float(term.get("weight") or 0.0)
                if term_weight <= 0:
                    continue

                total_possible_weight += term_weight

                match_strength = _match_strength_for_entry(
                    entry_keywords_norm,
                    title_field,
                    company_field,
                    summary_field,
                    clean_keyword,
                )
                if match_strength <= 0:
                    continue

                weighted_score += term_weight * match_strength
                matched_keywords.append(clean_keyword)

            if total_possible_weight <= 0:
                continue

            match_rate = int(round(min(weighted_score / total_possible_weight, 1.0) * 100))
            if match_rate <= 0:
                continue

            scored_scope.append((match_rate, weighted_score, file_name, _company_name(entry, file_name), matched_keywords))

        return scored_scope

    scored = score_scope(set(candidate_files) if candidate_files else set())

    scored.sort(key=lambda item: (-item[1], -item[0], item[3], item[2]))

    file_match_rates: dict[str, int] = {}
    for match_rate, _, file_name, _, _ in scored:
        previous = file_match_rates.get(file_name, 0)
        if match_rate > previous:
            file_match_rates[file_name] = match_rate

    unique: dict[str, dict[str, Any]] = {}
    for match_rate, weighted_score, file_name, company_name, matched_keywords in scored:
        if match_rate <= 0:
            continue
        if company_name in unique:
            continue
        unique[company_name] = {
            "institution": company_name,
            "file": file_name,
            "score": match_rate,
            "match_rate": match_rate,
            "raw_score": round(weighted_score, 2),
            "matched_keywords": sorted({keyword for keyword in matched_keywords if keyword}),
        }
        if limit is not None and len(unique) >= limit:
            break

    return list(unique.values()), file_match_rates


def _collect_candidate_files_from_terms(
    wiki_index: dict[str, dict[str, Any]],
    weighted_terms: list[dict[str, Any]],
    source_files: list[str] | None = None,
) -> list[str]:
    if source_files is not None and not source_files:
        return []

    scored_recommendations, _ = _score_index_entries_with_file_scores(wiki_index, weighted_terms, [] if source_files is None else source_files)
    company_files = _collect_company_files(wiki_index)

    candidate_files: list[str] = []
    seen_files: set[str] = set()

    for recommendation in scored_recommendations:
        institution = str(recommendation.get("institution") or "").strip()
        if not institution:
            continue

        company_key = _normalize_keyword(institution)
        related_files = list(company_files.get(company_key, []))
        primary_file = str(recommendation.get("file") or "").strip()

        ordered_files = [primary_file, *related_files] if primary_file else related_files
        for file_name in ordered_files:
            clean_file = str(file_name).strip()
            if not clean_file or clean_file in seen_files:
                continue
            seen_files.add(clean_file)
            candidate_files.append(clean_file)

    return candidate_files


def _collect_staged_candidate_files(
    wiki_index: dict[str, dict[str, Any]],
    profile_groups: dict[str, list[dict[str, Any]]],
) -> tuple[list[str], list[str], str | None]:
    core_terms = list(profile_groups.get("core", []))
    support_terms = list(profile_groups.get("support", []))

    stage1_files = _collect_candidate_files_from_terms(wiki_index, core_terms)
    if not stage1_files:
        return [], [], "core"

    stage2_files = stage1_files
    if support_terms:
        stage2_files = _collect_candidate_files_from_terms(wiki_index, support_terms, stage1_files)
        if not stage2_files:
            return stage1_files, [], "support"

    return stage1_files, stage2_files, None


def _build_no_match_report(
    user_profile: str,
    weighted_terms: list[dict[str, Any]],
    profile_plan: dict[str, list[str]] | None,
    analysis_phase: str,
    reason: str,
) -> dict[str, Any]:
    supported_categories = sorted(_detect_supported_categories(user_profile, [str(term.get("keyword") or "") for term in weighted_terms]))
    missing_categories = [
        category_key
        for category_key in FOLLOW_UP_CATEGORY_ORDER
        if category_key not in supported_categories and category_key in _load_facet_catalog()
    ]

    stage_label = {
        "core": "1차(core) 분류",
        "support": "2차(support) 분류",
        "follow_up": "3차(follow) 분류",
    }.get(reason, "분류")

    _log(f"{stage_label} 결과가 0개라서 전체 확장 없이 종료합니다.")

    return {
        "recommended_institutions": [],
        "detected_keywords": [str(term.get("keyword") or "") for term in weighted_terms],
        "detected_categories": supported_categories,
        "missing_categories": missing_categories,
        "follow_up_questions": [],
        "match_message": f"{stage_label} 기준으로는 아직 맞는 기업을 찾지 못했습니다. 핵심 조건을 조금 넓혀 다시 시도해 보세요.",
        "match_threshold": MATCH_RATE_THRESHOLD,
    }


def _build_staged_recommendation_report(
    user_profile: str,
    profile_plan: dict[str, list[str]] | None,
    fallback_keywords: list[str] | None,
    supplemental_weighted_terms: list[dict[str, Any]],
    analysis_phase: str,
    show_follow_up_questions: bool,
) -> dict[str, Any]:
    profile_groups = _build_profile_weighted_term_groups(profile_plan, fallback_keywords)
    profile_weighted_terms = [*profile_groups["core"], *profile_groups["support"], *profile_groups["follow_up"]]
    _log_weighted_term_groups([*profile_weighted_terms, *supplemental_weighted_terms])

    wiki_index, _ = _load_wiki_index()
    stage1_files, stage2_files, exhausted_stage = _collect_staged_candidate_files(wiki_index, profile_groups)
    _log(f"staged candidate files: stage1={stage1_files}, stage2={stage2_files}")

    if exhausted_stage:
        return _build_no_match_report(
            user_profile,
            [*profile_weighted_terms, *supplemental_weighted_terms],
            profile_plan,
            analysis_phase,
            exhausted_stage,
        )

    stage2_terms = [*profile_groups["core"], *profile_groups["support"]]
    stage2_scored, stage2_file_match_rates = _score_index_entries_with_file_scores(
        wiki_index,
        stage2_terms,
        stage2_files,
        limit=None,
    )
    _log(f"stage2 scored recommendations ({len(stage2_scored)}): {[(item.get('institution'), item.get('raw_score')) for item in stage2_scored[:10]]}")

    if not stage2_scored:
        return _build_no_match_report(
            user_profile,
            stage2_terms,
            profile_plan,
            analysis_phase,
            "support",
        )

    if len(stage2_scored) <= 5:
        return _build_report_payload(
            user_profile,
            stage2_terms,
            stage2_files,
            include_follow_up_questions=False,
            analysis_phase=analysis_phase,
            profile_plan=profile_plan,
            scored_recommendations=stage2_scored,
            file_match_rates=stage2_file_match_rates,
            defer_recommendations=False,
        )

    normalized_phase = str(analysis_phase or "initial").strip() or "initial"
    if normalized_phase == "initial":
        return _build_report_payload(
            user_profile,
            stage2_terms,
            stage2_files,
            include_follow_up_questions=show_follow_up_questions,
            analysis_phase=analysis_phase,
            profile_plan=profile_plan,
            scored_recommendations=stage2_scored,
            file_match_rates=stage2_file_match_rates,
            defer_recommendations=True,
        )

    final_terms = [*stage2_terms, *profile_groups["follow_up"], *supplemental_weighted_terms]
    final_scored, final_file_match_rates = _score_index_entries_with_file_scores(
        wiki_index,
        final_terms,
        stage2_files,
        limit=5,
    )
    _log(f"follow scored recommendations ({len(final_scored)}): {[(item.get('institution'), item.get('raw_score')) for item in final_scored[:10]]}")

    if not final_scored:
        return _build_no_match_report(
            user_profile,
            final_terms,
            profile_plan,
            analysis_phase,
            "follow_up",
        )

    return _build_report_payload(
        user_profile,
        final_terms,
        stage2_files,
        include_follow_up_questions=False,
        analysis_phase=analysis_phase,
        profile_plan=profile_plan,
        scored_recommendations=final_scored,
        file_match_rates=final_file_match_rates,
        defer_recommendations=False,
    )


def _score_index_entries(
    wiki_index: dict[str, dict[str, Any]],
    weighted_terms: list[dict[str, Any]],
    candidate_files: list[str],
) -> list[dict[str, Any]]:
    recommendations, _ = _score_index_entries_with_file_scores(wiki_index, weighted_terms, candidate_files)
    return recommendations


def _build_report_payload(
    user_profile: str,
    weighted_terms: list[dict[str, Any]],
    candidate_files: list[str],
    include_follow_up_questions: bool = True,
    analysis_phase: str = "initial",
    profile_plan: dict[str, list[str]] | None = None,
    scored_recommendations: list[dict[str, Any]] | None = None,
    file_match_rates: dict[str, int] | None = None,
    defer_recommendations: bool | None = None,
) -> dict[str, Any]:
    wiki_index, _ = _load_wiki_index()
    if profile_plan:
        _log(
            "profile keyword plan -> "
            f"core={profile_plan.get('core_keywords', [])}, "
            f"support={profile_plan.get('support_keywords', [])}, "
            f"follow_up={profile_plan.get('follow_up_keywords', [])}"
        )

    if weighted_terms:
        _log(
            "weighted terms -> "
            f"{[(str(term.get('keyword') or ''), float(term.get('weight') or 0.0), str(term.get('source') or ''), str(term.get('category') or '')) for term in weighted_terms]}"
        )

    if candidate_files:
        _log(f"candidate files ({len(candidate_files)}): {candidate_files}")

    if scored_recommendations is None:
        scored_recommendations, file_match_rates = _score_index_entries_with_file_scores(wiki_index, weighted_terms, candidate_files)
    else:
        file_match_rates = file_match_rates or {}
    if scored_recommendations:
        _log(
            "scored recommendations -> "
            f"{[(item.get('institution'), item.get('match_rate'), item.get('raw_score'), item.get('matched_keywords')) for item in scored_recommendations[:10]]}"
        )
    recommendations = _attach_related_files(scored_recommendations, file_match_rates=file_match_rates)
    follow_up_questions = []
    if include_follow_up_questions:
        follow_up_questions = _build_follow_up_questions(user_profile, [str(term.get("keyword") or "") for term in weighted_terms])

    filtered_recommendations = [item for item in recommendations if int(item.get("score") or 0) > MATCH_RATE_THRESHOLD]
    filtered_recommendations.sort(key=lambda item: (-float(item.get("raw_score") or 0.0), -int(item.get("match_rate") or 0), str(item.get("institution") or ""), str(item.get("file") or "")))
    filtered_recommendations = filtered_recommendations[:5]

    for index, item in enumerate(filtered_recommendations, start=1):
        item["rank"] = index

    normalized_phase = str(analysis_phase or "initial").strip() or "initial"
    should_defer_recommendations = defer_recommendations if defer_recommendations is not None else (normalized_phase == "initial" and bool(follow_up_questions))
    if should_defer_recommendations:
        filtered_recommendations = []

    if filtered_recommendations:
        _log(
            "final recommendations -> "
            f"{[(item.get('rank'), item.get('institution'), item.get('match_rate'), item.get('raw_score'), item.get('matched_keywords')) for item in filtered_recommendations]}"
        )
    else:
        _log("final recommendations -> []")

    supported_categories = sorted(_detect_supported_categories(user_profile, [str(term.get("keyword") or "") for term in weighted_terms]))
    missing_categories = [
        category_key
        for category_key in FOLLOW_UP_CATEGORY_ORDER
        if category_key not in supported_categories and category_key in _load_facet_catalog()
    ]

    match_message = ""
    if should_defer_recommendations:
        match_message = "확정되지 않은 분류를 먼저 선택한 뒤 최종 추천을 제공합니다."
    if not filtered_recommendations:
        match_message = match_message or "조건에 맞는 추천 공고를 아직 찾지 못했습니다. 핵심 조건을 조금 넓혀 다시 시도해 주세요."

    return {
        "recommended_institutions": filtered_recommendations,
        "detected_keywords": [str(term.get("keyword") or "") for term in weighted_terms],
        "detected_categories": supported_categories,
        "missing_categories": missing_categories,
        "follow_up_questions": follow_up_questions,
        "match_message": match_message,
        "match_threshold": MATCH_RATE_THRESHOLD,
    }


def build_fallback_report(
    user_profile: str,
    supplemental_selections: dict[str, list[str]] | None = None,
    analysis_phase: str = "initial",
) -> dict[str, Any]:
    profile_plan = _extract_profile_keyword_plan(user_profile)
    candidate_keywords = _extract_candidate_keywords(user_profile)
    _log(f"fallback candidate keywords: {candidate_keywords}")

    validated_keywords = _extract_validated_keywords(candidate_keywords)
    _log(f"fallback validated keywords: {validated_keywords}")

    supplemental_terms_by_category, neutral_categories = _parse_supplemental_selections(supplemental_selections)
    supplemental_weighted_terms = _build_supplemental_weighted_terms(supplemental_terms_by_category, neutral_categories)
    if supplemental_weighted_terms:
        _log(
            "fallback supplemental terms: "
            f"{[(item['category'], item['keyword'], item['weight']) for item in supplemental_weighted_terms]}"
        )
    if neutral_categories:
        _log(f"fallback neutral categories: {sorted(neutral_categories)}")
    return _build_staged_recommendation_report(
        user_profile=user_profile,
        profile_plan=profile_plan,
        fallback_keywords=validated_keywords,
        supplemental_weighted_terms=supplemental_weighted_terms,
        analysis_phase=analysis_phase,
        show_follow_up_questions=not bool(supplemental_selections),
    )


def generate_report(
    user_profile: str,
    supplemental_selections: dict[str, list[str]] | None = None,
    analysis_phase: str = "initial",
) -> dict[str, Any]:
    """사용자 프로필 기반 추천 기관 보고서 생성.
    
    1순위: LLM 키워드 추출 → facet 검증 → facet 스코어링
    2순위: 순수 로컬 (regex + facet + facet 스코어링)
    """
    supplemental_terms_by_category, neutral_categories = _parse_supplemental_selections(supplemental_selections)
    supplemental_weighted_terms = _build_supplemental_weighted_terms(supplemental_terms_by_category, neutral_categories)
    if supplemental_weighted_terms:
        _log(
            "supplemental terms: "
            f"{[(item['category'], item['keyword'], item['weight']) for item in supplemental_weighted_terms]}"
        )
    if neutral_categories:
        _log(f"neutral categories: {sorted(neutral_categories)}")

    normalized_phase = str(analysis_phase or "initial").strip() or "initial"

    if normalized_phase != "initial":
        _log("final recommendation phase: python-only matching")
        return build_fallback_report(
            user_profile,
            supplemental_selections=supplemental_selections,
            analysis_phase=normalized_phase,
        )

    # Initial phase: use LLM keywords only to prepare follow-up questions.
    profile_plan = _extract_profile_keyword_plan(user_profile)

    candidate_keywords = _extract_candidate_keywords(user_profile)
    validated_keywords = _extract_validated_keywords(candidate_keywords)
    if not validated_keywords:
        validated_keywords = candidate_keywords

    return _build_staged_recommendation_report(
        user_profile=user_profile,
        profile_plan=profile_plan,
        fallback_keywords=validated_keywords,
        supplemental_weighted_terms=supplemental_weighted_terms,
        analysis_phase=normalized_phase,
        show_follow_up_questions=not bool(supplemental_selections),
    )
