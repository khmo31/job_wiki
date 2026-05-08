from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from functools import lru_cache
from pathlib import Path
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field


PROJECT_ROOT = Path(__file__).resolve().parents[3]
WIKI_ANALYSIS_ROOT = PROJECT_ROOT.parent / "job_wiki" / "10_Wiki" / "Analysis"
META_ROOT = PROJECT_ROOT.parent / "job_wiki" / "20_Meta"


def _normalize_keyword(value: str) -> str:
    cleaned = value.strip()
    cleaned = cleaned.replace("[[", "").replace("]]", "")
    cleaned = re.sub(r"[^\w]", "", cleaned, flags=re.UNICODE)
    return cleaned.casefold()


def _wrap_keyword(value: str) -> str:
    return f"[[{value.strip()}]]"


def _is_group_keyword(value: str) -> bool:
    raw = value.strip().replace("[[", "").replace("]]", "")
    return (
        "/" in raw
        or "(" in raw
        or ")" in raw
        or "（" in raw
        or "）" in raw
        or "그룹" in raw
    )


def _deduplicate_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        key = _normalize_keyword(value)
        if not key or key in seen:
            continue
        seen.add(key)
        ordered.append(value.strip())
    return ordered


def _split_keywords(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []

    bracketed = re.findall(r"\[\[(.+?)\]\]", text)
    if bracketed:
        return bracketed

    if text.startswith("["):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list):
            return [str(item) for item in parsed if str(item).strip()]

    return [item.strip() for item in re.split(r"[,\n;|]+", text) if item.strip()]


@lru_cache(maxsize=1)
def _load_ontology_mappings() -> tuple[dict[str, list[str]], str | None]:
    ontology_file = META_ROOT / "Ontology_Map.json"
    if not ontology_file.exists():
        return {}, None

    try:
        payload = json.loads(ontology_file.read_text(encoding="utf-8"))
    except Exception:
        return {}, str(ontology_file)

    mappings = payload.get("mappings", {}) if isinstance(payload, dict) else {}
    if not isinstance(mappings, dict):
        return {}, str(ontology_file)

    normalized: dict[str, list[str]] = {}
    for standard_keyword, synonyms in mappings.items():
        if not isinstance(standard_keyword, str):
            continue
        synonym_list = [standard_keyword]
        if isinstance(synonyms, list):
            synonym_list.extend([syn for syn in synonyms if isinstance(syn, str)])
        normalized[standard_keyword] = synonym_list

    return normalized, str(ontology_file)


@lru_cache(maxsize=1)
def _load_wiki_index() -> tuple[dict[str, dict], str | None]:
    index_file = META_ROOT / "Wiki_Index.json"
    if not index_file.exists():
        return {}, None

    try:
        payload = json.loads(index_file.read_text(encoding="utf-8"))
    except Exception:
        return {}, str(index_file)

    entries = payload.get("entries", {}) if isinstance(payload, dict) else {}
    if not isinstance(entries, dict):
        return {}, str(index_file)

    normalized_entries: dict[str, dict] = {}
    for file_name, entry in entries.items():
        if isinstance(file_name, str) and isinstance(entry, dict):
            normalized_entries[file_name] = entry

    return normalized_entries, str(index_file)


# Simple in-memory cache for ontology checks to avoid repeated LLM/tool calls
# key -> (result_str, expire_ts)
_ONTOLOGY_CACHE: dict[str, tuple[str, float]] = {}
# TTL seconds for cache entries (environment override possible)
_ONTOLOGY_CACHE_TTL = int(float(os.getenv("ONTOLOGY_CHECK_CACHE_TTL", "60")))

# Persistent cache file and lock
_ONTOLOGY_CACHE_FILE = META_ROOT / "ontology_cache.json"
_ONTOLOGY_CACHE_LOCK = threading.Lock()


def _load_ontology_cache() -> None:
    try:
        if not _ONTOLOGY_CACHE_FILE.exists():
            return
        raw = json.loads(_ONTOLOGY_CACHE_FILE.read_text(encoding="utf-8"))
        now = time.time()
        with _ONTOLOGY_CACHE_LOCK:
            for k, v in raw.items():
                if not isinstance(v, list) or len(v) < 2:
                    continue
                result, expire_ts = v[0], float(v[1])
                if expire_ts >= now:
                    _ONTOLOGY_CACHE[k] = (result, expire_ts)
    except Exception:
        return


def _save_ontology_cache() -> None:
    try:
        with _ONTOLOGY_CACHE_LOCK:
            serializable = {k: [v[0], v[1]] for k, v in _ONTOLOGY_CACHE.items()}
        _ONTOLOGY_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _ONTOLOGY_CACHE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(serializable, ensure_ascii=False), encoding="utf-8")
        tmp.replace(_ONTOLOGY_CACHE_FILE)
    except Exception:
        return


# Load cache at import time
_load_ontology_cache()


def _find_wiki_file(file_name: str) -> Path | None:
    requested = file_name.strip()
    requested = requested.replace("[[", "").replace("]]", "")
    requested_name = Path(requested).name
    requested_stem = Path(requested_name).stem
    wiki_index, _ = _load_wiki_index()
    if not wiki_index:
        return None

    for indexed_file_name in wiki_index.keys():
        indexed_path = WIKI_ANALYSIS_ROOT / indexed_file_name
        if indexed_file_name.lower() == requested_name.lower() or indexed_path.stem.lower() == requested_stem.lower():
            if indexed_path.exists():
                return indexed_path

    return None


class WikiReadOnlyInput(BaseModel):
    file_name: str = Field(..., description="읽을 마크다운 파일명 또는 [[기관명]]")


class OntologyCheckInput(BaseModel):
    keywords: str = Field(..., description="검증할 키워드 문자열 또는 목록")


class WikiReadOnlyTool(BaseTool):
    name: str = "wiki_read_only_tool"
    description: str = "키워드를 입력하면 Wiki_Index.json을 빠르게 검색하여 관련 파일명 목록을 알려줍니다. 정확한 파일명(.md)을 입력하면 해당 파일의 핵심 섹션만 추출해 반환합니다."
    args_schema: Type[BaseModel] = WikiReadOnlyInput

    def _log(self, message: str) -> None:
        try:
            print(f"[WikiReadOnlyTool] {message}", file=sys.stderr)
        except Exception:
            pass

    def _extract_key_sections(self, content: str) -> str:
        """Extract key sections using simple string find() instead of regex."""
        dna_start = content.find("## 🧬 직무 DNA")
        conn_start = content.find("## 🌐 지식 그래프 연결")
        evid_start = content.find("## 📝 분석 근거")
        trace_start = content.find("## 🔗 Traceability")

        extracted_parts = []
        
        # 1. 직무 DNA 섹션 추출
        if dna_start != -1 and conn_start != -1:
            extracted_parts.append(content[dna_start:conn_start].strip())

        # 2. 분석 근거 섹션 추출
        if evid_start != -1 and trace_start != -1:
            extracted_parts.append(content[evid_start:trace_start].strip())

        # 결과 조립
        if extracted_parts:
            return "\n\n".join(extracted_parts)
        else:
            # 혹시라도 못 찾으면 앞부분 800자만 반환
            return content[:800] + "\n\n...(생략됨)..."

    def _run(self, file_name: str) -> str:
        query = file_name.strip().replace("[[", "").replace("]]", "")
        if not query:
            return "조회할 파일명 또는 키워드를 입력해 주세요."

        if query.lower().endswith(".md"):
            file_path = _find_wiki_file(query)
            if file_path is not None:
                full_content = file_path.read_text(encoding="utf-8", errors="ignore")
                # Extract only key sections
                extracted = self._extract_key_sections(full_content)
                self._log(f"exact file hit: {file_path.name}")
                return extracted
            self._log(f"exact file miss: {query}")
            return f"해당 파일명('{query}')을 위키에서 찾을 수 없습니다."

        wiki_index, _ = _load_wiki_index()
        if not wiki_index:
            return f"위키 색인에서 '{query}'에 해당하는 문서를 찾을 수 없습니다."

        search_terms = _split_keywords(query)
        if not search_terms:
            search_terms = [query]

        scored_entries: list[tuple[int, str, dict]] = []
        for file_name, entry in wiki_index.items():
            company = str(entry.get("company") or "")
            title = str(entry.get("title") or "")
            summary = str(entry.get("summary") or "")
            keywords = [str(keyword) for keyword in entry.get("keywords") or [] if str(keyword).strip()]

            company_cf = company.casefold()
            title_cf = title.casefold()
            summary_cf = summary.casefold()
            keyword_terms = [keyword.casefold() for keyword in keywords]

            score = 0
            for term in search_terms:
                normalized_term = term.casefold()
                if not normalized_term:
                    continue

                keyword_hit = any(
                    normalized_term == keyword or normalized_term in keyword or keyword in normalized_term
                    for keyword in keyword_terms
                )
                title_company_hit = normalized_term in title_cf or normalized_term in company_cf

                if keyword_hit:
                    score += 4
                if title_company_hit:
                    score += 3
                if (keyword_hit or title_company_hit) and normalized_term in summary_cf:
                    score += 1

            if score > 0:
                scored_entries.append((score, file_name, entry))

        if not scored_entries:
            return f"위키 색인에서 '{query}'에 해당하는 문서를 찾을 수 없습니다."

        lines = ["색인 검색 결과, 상위 3개 파일만 제공합니다. 상세 본문을 보려면 파일명(.md)을 다시 이 도구에 입력하세요."]
        scored_entries.sort(key=lambda item: (-item[0], item[1]))
        for index, (_, file_name, entry) in enumerate(scored_entries[:3], start=1):
            company = entry.get("company", "미상")
            summary = entry.get("summary", "요약 없음")
            lines.append(f"{index}. {file_name} (기관: {company}, 요약: {summary})")

        self._log(f"index search query='{query}' hits={len(scored_entries)}")

        return "\n".join(lines)


class OntologyCheckTool(BaseTool):
    name: str = "ontology_check_tool"
    description: str = "Validate candidate keywords against ../20_Meta/Ontology_Map.json and return only allowed [[keyword]] values."
    args_schema: Type[BaseModel] = OntologyCheckInput

    def _log(self, message: str) -> None:
        try:
            print(f"[OntologyCheckTool] {message}", file=sys.stderr)
        except Exception:
            pass

    def _run(self, keywords: str) -> str:
        candidate_keywords = _deduplicate_preserve_order(_split_keywords(keywords))
        # Build a cache key from normalized candidate keywords
        norm_keys = [k for k in ([_normalize_keyword(k) for k in candidate_keywords]) if k]
        cache_key = ",".join(norm_keys)
        # Check cache
        if cache_key:
            entry = _ONTOLOGY_CACHE.get(cache_key)
            if entry:
                result_str, expire_ts = entry
                if expire_ts >= time.time():
                    return result_str
                else:
                    # expired
                    _ONTOLOGY_CACHE.pop(cache_key, None)
        ontology_mappings, _ = _load_ontology_mappings()

        if not candidate_keywords or not ontology_mappings:
            self._log(f"input='{keywords}' matched=0")
            return "일치하는 온톨로지 키워드가 없습니다"

        matched: set[str] = set()
        for keyword in candidate_keywords:
            normalized_word = _normalize_keyword(keyword)
            if not normalized_word:
                continue

            for standard_keyword, synonyms in ontology_mappings.items():
                normalized_std = _normalize_keyword(standard_keyword)

                # 1) 표준키워드 정확 매칭
                if normalized_word == normalized_std:
                    matched.add(_wrap_keyword(standard_keyword))
                    continue

                # 2) 표준키워드 부분 매칭 (word in std_key or std_key in word)
                if normalized_word in normalized_std or normalized_std in normalized_word:
                    matched.add(_wrap_keyword(standard_keyword))
                    continue

                # 3) 유의어 정확/부분 매칭
                found_by_synonym = False
                for synonym in synonyms:
                    normalized_syn = _normalize_keyword(synonym)
                    if not normalized_syn:
                        continue
                    if (
                        normalized_word == normalized_syn
                        or normalized_word in normalized_syn
                        or normalized_syn in normalized_word
                    ):
                        matched.add(_wrap_keyword(standard_keyword))
                        found_by_synonym = True
                        break
                if found_by_synonym:
                    continue

        filtered = sorted([keyword for keyword in matched if not _is_group_keyword(keyword)])

        if not filtered:
            result = "일치하는 온톨로지 키워드가 없습니다"
        else:
            result = "\n".join(filtered)

        self._log(f"input='{keywords}' matched={len(filtered)}")

        # Store to cache with TTL
        if cache_key:
            try:
                _ONTOLOGY_CACHE[cache_key] = (result, time.time() + _ONTOLOGY_CACHE_TTL)
                # persist cache to disk (best-effort)
                _save_ontology_cache()
            except Exception:
                # Best-effort cache; do not fail on cache errors
                pass

        return result
