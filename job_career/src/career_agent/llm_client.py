"""경량 LLM 클라이언트 — OpenAI/NVIDIA/Groq API 호출"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from functools import lru_cache
from pathlib import Path
from typing import Any

# Groq 무료 티어 rate limit: 30 RPM → 2초 간격
_RATE_LIMITER_LAST_CALL: float = 0.0
_RATE_LIMITER_INTERVAL: float = 2.0  # seconds between requests

# Groq 모델 폴백 체인 (rate limit 도달 시 다음 모델로 자동 전환)
_GROQ_FALLBACK_MODELS = [
    os.getenv("LLM_EXTRACT_MODEL", "llama-3.3-70b-versatile"),
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "llama-3.1-8b-instant",
    "qwen/qwen3-32b",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
]

_FACET_ROOT = Path(__file__).resolve().parents[3] / "job_wiki" / "10_Wiki" / "Facets"
_FACET_INDEX_FILE = Path(__file__).resolve().parents[3] / "job_wiki" / "20_Meta" / "Facet_Index.json"
_FACET_CONTEXT_MAX_CHARS = 1600
_FACET_CONTEXT_MAX_PAGES = 4

_FACET_CATEGORY_PRIORITY = [
    "qualification",
    "hire_type",
    "region",
    "ncs",
    "preference",
    "recruitment_type",
    "education",
    "process",
]

_LLM_EXTRACT_MAX_TOKENS = int(os.getenv("LLM_EXTRACT_MAX_TOKENS", "8192"))
_LLM_REQUEST_TIMEOUT = int(os.getenv("LLM_REQUEST_TIMEOUT", "120"))


@lru_cache(maxsize=1)
def _load_facet_index_payload() -> dict[str, Any]:
    if not _FACET_INDEX_FILE.exists():
        return {}

    try:
        payload = json.loads(_FACET_INDEX_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        _log(f"failed to load facet index: {exc}")
        return {}

    return payload if isinstance(payload, dict) else {}


def _rate_limit() -> None:
    """Rate limiter: 30 RPM (2초 간격) 유지"""
    global _RATE_LIMITER_LAST_CALL
    now = time.time()
    elapsed = now - _RATE_LIMITER_LAST_CALL
    if elapsed < _RATE_LIMITER_INTERVAL:
        sleep_for = _RATE_LIMITER_INTERVAL - elapsed
        time.sleep(sleep_for)
    _RATE_LIMITER_LAST_CALL = time.time()


def _log(message: str) -> None:
    try:
        print(f"[llm_client] {message}", file=sys.stderr)
    except Exception:
        pass


def _detect_provider() -> str:
    if os.getenv("OPENCODE_API_KEY"):
        return "opencode-go"
    if os.getenv("GROQ_API_KEY"):
        return "groq"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("NVIDIA_API_KEY"):
        return "nvidia"
    return ""


def _provider_config(provider: str) -> dict[str, Any]:
    configs = {
        "opencode-go": {
            "endpoint": os.getenv("OPENCODE_BASE_URL", "https://opencode.ai/zen/go/v1/chat/completions"),
            "api_key": os.getenv("OPENCODE_API_KEY", ""),
            "model": os.getenv("LLM_EXTRACT_MODEL", "deepseek-v4-flash"),
        },
        "groq": {
            "base_url": os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
            "api_key": os.getenv("GROQ_API_KEY", ""),
            "model": os.getenv("LLM_EXTRACT_MODEL", "llama-3.3-70b-versatile"),
        },
        "openai": {
            "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            "api_key": os.getenv("OPENAI_API_KEY", ""),
            "model": os.getenv("LLM_EXTRACT_MODEL", "gpt-4o-mini"),
        },
        "nvidia": {
            "base_url": os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"),
            "api_key": os.getenv("NVIDIA_API_KEY", ""),
            "model": os.getenv("LLM_EXTRACT_MODEL", "deepseek-ai/deepseek-v4-flash"),
        },
    }
    return configs.get(provider, {})


def _call_llm(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 256,
) -> str | None:
    provider = _detect_provider()
    if not provider:
        _log("no LLM API key found in environment")
        return None

    cfg = _provider_config(provider)
    if not cfg or not cfg["api_key"]:
        return None

    # For Groq: try fallback models on rate limit
    models_to_try = [cfg["model"]]
    if provider == "groq":
        models_to_try = list(dict.fromkeys([cfg["model"]] + _GROQ_FALLBACK_MODELS))

    import requests

    for model_name in models_to_try:
        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
            "max_tokens": max_tokens,
        }
        try:
            _rate_limit()
            request_url = cfg["endpoint"] if provider == "opencode-go" else f"{cfg['base_url'].rstrip('/')}/chat/completions"
            resp = requests.post(
                request_url,
                headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
                json=payload,
                timeout=_LLM_REQUEST_TIMEOUT,
            )
            if resp.status_code == 429:
                _log(f"Groq rate limit hit for {model_name}, trying next model...")
                continue
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            if model_name != models_to_try[0]:
                _log(f"switched to fallback model: {model_name}")
            return content.strip()
        except requests.RequestException as e:
            if "429" in str(e) or "Too Many Requests" in str(e):
                _log(f"429 on {model_name}, trying fallback...")
                continue
            _log(f"LLM call failed ({model_name}): {e}")
            return None
        except Exception as e:
            _log(f"LLM call failed ({model_name}): {e}")
            return None

    _log("all Groq models exhausted (rate limited)")
    return None


@lru_cache(maxsize=16)
def _load_facet_context(query: str) -> str:
    """Load a small, query-relevant set of facet index markdown pages."""
    try:
        if not _FACET_ROOT.exists():
            return ""

        query_case = query.casefold().strip()
        query_terms = [term for term in re.findall(r"[가-힣A-Za-z0-9]{2,}", query_case) if term]
        root_index_path = _FACET_ROOT / "index.md"

        index_paths = [path for path in sorted(_FACET_ROOT.glob("*/index.md")) if path.is_file()]
        scored_paths: list[tuple[int, int, Path, str]] = []

        for priority, path in enumerate(index_paths):
            text = path.read_text(encoding="utf-8").strip()
            if not text:
                continue

            score = 0
            path_text_case = text.casefold()
            for term in query_terms:
                if term and term in path_text_case:
                    score += 1

            if path.parent.name in _FACET_CATEGORY_PRIORITY:
                score += len(_FACET_CATEGORY_PRIORITY) - _FACET_CATEGORY_PRIORITY.index(path.parent.name)

            scored_paths.append((score, priority, path, text))

        scored_paths.sort(key=lambda item: (-item[0], item[1], item[2].as_posix()))

        selected_paths: list[tuple[Path, str]] = []
        if root_index_path.is_file():
            selected_paths.append((root_index_path, root_index_path.read_text(encoding="utf-8").strip()))

        for _, _, path, text in scored_paths:
            if len(selected_paths) >= _FACET_CONTEXT_MAX_PAGES:
                break
            selected_paths.append((path, text))

        if len(selected_paths) == 1:
            for _, _, path, text in scored_paths:
                if len(selected_paths) >= _FACET_CONTEXT_MAX_PAGES:
                    break
                selected_paths.append((path, text))

        chunks: list[str] = []
        for path, text in selected_paths:
            if not text:
                continue

            if len(text) > _FACET_CONTEXT_MAX_CHARS:
                text = text[:_FACET_CONTEXT_MAX_CHARS].rstrip() + "\n..."

            relative_path = path.relative_to(_FACET_ROOT).as_posix()
            chunks.append(f"### {relative_path}\n{text}")

        return "\n\n".join(chunks)
    except Exception as e:
        _log(f"failed to load facet context: {e}")
        return ""


def _deduplicate_preserve_order(values: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()

    for value in values:
        cleaned = str(value).strip()
        if not cleaned:
            continue
        normalized = cleaned.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(cleaned)

    return ordered


def _parse_keyword_plan(result: str) -> dict[str, list[str]] | None:
    def _normalize_list(values: Any) -> list[str]:
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list):
            return []
        return _deduplicate_preserve_order([str(item).strip() for item in values if str(item).strip()])

    try:
        parsed = json.loads(result)
        if isinstance(parsed, dict):
            return {
                "core_keywords": _normalize_list(parsed.get("core_keywords")),
                "support_keywords": _normalize_list(parsed.get("support_keywords")),
                "follow_up_keywords": _normalize_list(parsed.get("follow_up_keywords")),
            }
        if isinstance(parsed, list):
            return {
                "core_keywords": [],
                "support_keywords": _normalize_list(parsed),
                "follow_up_keywords": [],
            }
    except json.JSONDecodeError:
        pass

    core_matches = re.findall(r'"core_keywords"\s*:\s*\[(.*?)\]', result, flags=re.DOTALL)
    support_matches = re.findall(r'"support_keywords"\s*:\s*\[(.*?)\]', result, flags=re.DOTALL)
    follow_up_matches = re.findall(r'"follow_up_keywords"\s*:\s*\[(.*?)\]', result, flags=re.DOTALL)
    if not (core_matches or support_matches or follow_up_matches):
        return None

    def _extract_list(raw_text: str) -> list[str]:
        return _deduplicate_preserve_order(re.findall(r'"([^"]+)"', raw_text))

    return {
        "core_keywords": _extract_list(core_matches[0]) if core_matches else [],
        "support_keywords": _extract_list(support_matches[0]) if support_matches else [],
        "follow_up_keywords": _extract_list(follow_up_matches[0]) if follow_up_matches else [],
    }


def extract_keyword_plan(user_profile: str) -> dict[str, list[str]] | None:
    """LLM으로 사용자 프로필의 핵심/보조 키워드 계획을 추출한다.

    Facet index md 파일들을 프롬프트에 포함시켜
    기존 facet 라벨 안에서만 핵심 의도와 보조 신호를 나누도록 유도한다.
    실패 시 None 반환.
    """
    facet_context = _load_facet_context(user_profile)

    system = (
        "You are a career keyword extraction assistant.\n"
        "Given a user's career profile, extract keyword groups from the facet index pages below.\n"
        "First, determine if the profile is related to job/career/employment at all.\n"
        "If the profile is NOT related to any career, job, or employment context, "
        'return {"core_keywords":[],"support_keywords":[],"follow_up_keywords":[]}\n'
        "Use only labels that appear in the facet pages; do not invent new labels.\n"
        "core_keywords must contain the single most important destination/domain labels.\n"
        "support_keywords must contain background or supporting labels that help refine the intent.\n"
        "follow_up_keywords must contain weaker contextual labels that should not dominate scoring.\n"
        "Prefer the most specific matching labels, avoid redundant variants, and keep the groups small.\n"
        "Output ONLY valid JSON with keys core_keywords, support_keywords, follow_up_keywords.\n"
        'Example: {"core_keywords":["보건.의료"],"support_keywords":["경영.회계.사무","경력"],"follow_up_keywords":["공공기관"]}'
    )

    user_prompt = f"User profile:\n{user_profile.strip()}"
    if facet_context:
        user_prompt = f"{user_prompt}\n\nFacet index pages:\n{facet_context}"

    result = _call_llm(
        system,
        user_prompt,
        max_tokens=_LLM_EXTRACT_MAX_TOKENS,
    )
    if not result:
        return None

    return _parse_keyword_plan(result)


def extract_keywords(user_profile: str) -> list[str] | None:
    """LLM으로 사용자 프로필에서 wiki 키워드 추출.

    호환성을 위해 핵심/보조/후속 키워드 계획을 병합한 리스트를 반환한다.
    실패 시 None 반환.
    """
    plan = extract_keyword_plan(user_profile)
    if not plan:
        return None

    merged = [*plan.get("core_keywords", []), *plan.get("support_keywords", []), *plan.get("follow_up_keywords", [])]
    return _deduplicate_preserve_order(merged)


CLASSIFY_SYSTEM = """You are a job classification assistant.
Given a job posting analysis, classify it into:
- job_nature: one of [연구/개발, 운영/관리, 설계, 실무/혼합]
- complexity: one of [low, medium, high]
- domain_context: short domain description
- skills: list of relevant skill keywords
- latent_skills: list of implied but not explicit skills

Output ONLY valid JSON with these keys."""


def classify_job_analysis(text: str) -> dict[str, Any] | None:
    """LLM으로 직무 분석 분류. 실패 시 None 반환."""
    result = _call_llm(CLASSIFY_SYSTEM, text[:1000], max_tokens=512)
    if not result:
        return None

    try:
        parsed = json.loads(result)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    return None


def suggest_ontology_keywords(text: str, existing_skills: list[str]) -> list[str] | None:
    """공고 텍스트에서 기존 facet 키워드에 없는 추가 키워드 제안.

    Facet index md 파일들을 컨텍스트로 제공하여
    중복 제안을 방지. Input token 절약을 위해 텍스트를 제한.
    """
    existing_str = ", ".join(existing_skills) if existing_skills else "(none yet)"
    facet_context = _load_facet_context(f"{text}\n{existing_str}")

    # Truncate job text to save input tokens (800 chars ≈ 320 tokens)
    truncated_text = text[:800].strip()

    prompt = (
        f"Existing facet skills: [{existing_str}]\n\n"
        f"Job posting text:\n{truncated_text}\n\n"
        "Extract skill/domain keywords that are NOT in any of the existing lists above (neither facet context nor existing_skills). "
        "If all relevant skills are already covered, output an empty array []."
        "Output ONLY a JSON array of strings."
    )

    full_prompt = prompt
    if facet_context:
        full_prompt = f"{prompt}\n\nFacet index pages:\n{facet_context}"

    result = _call_llm(
        "You are a facet expansion assistant. Find new skill keywords that do NOT exist in the provided facet index pages.",
        full_prompt,
        max_tokens=_LLM_EXTRACT_MAX_TOKENS,
    )
    if not result:
        return None

    try:
        parsed = json.loads(result)
        if isinstance(parsed, list):
            return [str(k).strip() for k in parsed if k]
    except json.JSONDecodeError:
        pass
    return None
