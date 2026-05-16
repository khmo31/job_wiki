"""경량 LLM 클라이언트 — OpenAI/NVIDIA/Groq API 호출"""
from __future__ import annotations

import json
import os
import re
import sys
import time
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
    if os.getenv("GROQ_API_KEY"):
        return "groq"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("NVIDIA_API_KEY"):
        return "nvidia"
    return ""


def _provider_config(provider: str) -> dict[str, Any]:
    configs = {
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


def _call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 256) -> str | None:
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
            resp = requests.post(
                f"{cfg['base_url'].rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"},
                json=payload,
                timeout=30,
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


def _load_ontology_keywords() -> list[str]:
    """Load the full list of standard ontology keywords from Ontology_Map.json."""
    try:
        # Locate project root relative to this file
        root = Path(__file__).resolve().parents[3]
        ontology_path = root / "job_wiki" / "20_Meta" / "Ontology_Map.json"
        if not ontology_path.exists():
            return []
        data = json.loads(ontology_path.read_text(encoding="utf-8"))
        mappings = data.get("mappings", {}) if isinstance(data, dict) else {}
        if not isinstance(mappings, dict):
            return []
        return list(mappings.keys())
    except Exception as e:
        _log(f"failed to load ontology: {e}")
        return []


def _build_ontology_context(max_keywords: int = 15) -> str:
    """Build an ontology keyword list string for inclusion in prompts.
    Limits to max_keywords to save input tokens.
    """
    keywords = _load_ontology_keywords()
    if not keywords:
        return ""
    if len(keywords) > max_keywords:
        keywords = keywords[:max_keywords]
    return "\nAvailable ontology keywords (match these if possible):\n" + "\n".join(f"- {kw}" for kw in keywords)


def extract_keywords(user_profile: str) -> list[str] | None:
    """LLM으로 사용자 프로필에서 wiki 키워드 추출.

    Ontology_Map.json의 표준 키워드 목록을 프롬프트에 포함시켜
    LLM이 기존 온톨로지 키워드와 매칭하도록 유도.
    실패 시 None 반환.
    """
    ontology_context = _build_ontology_context(max_keywords=15)

    system = (
        "You are a career keyword extraction assistant.\n"
        "Given a user's career profile, extract the most relevant skill/domain keywords.\n"
        "PRIORITIZE matching against the available ontology keywords below.\n"
        "Only suggest NEW keywords if no ontology keyword adequately covers the skill.\n"
        "Output ONLY a JSON array of keyword strings, no other text.\n"
        'Example: ["의료 행정 지식", "의료정보 보호", "문서 작성 및 관리"]'
    )

    user_prompt = user_profile
    if ontology_context:
        user_prompt = f"{user_profile}\n\n{ontology_context}"

    result = _call_llm(system, user_prompt, max_tokens=256)
    if not result:
        return None

    try:
        parsed = json.loads(result)
        if isinstance(parsed, list):
            return [str(k).strip() for k in parsed if k]
    except json.JSONDecodeError:
        pass

    matches = re.findall(r'"([^"]+)"', result)
    if matches:
        return [m.strip() for m in matches if m.strip()]

    return None


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
    """공고 텍스트에서 기존 온톨로지에 없는 신규 키워드 제안.

    Ontology_Map.json의 전체 표준 키워드 목록을 컨텍스트로 제공하여
    중복 제안을 방지. Input token 절약을 위해 텍스트와 온톨로지를 제한.
    """
    ontology_context = _build_ontology_context(max_keywords=15)
    existing_str = ", ".join(existing_skills) if existing_skills else "(none yet)"

    # Truncate job text to save input tokens (800 chars ≈ 320 tokens)
    truncated_text = text[:800].strip()

    prompt = (
        f"Existing ontology skills: [{existing_str}]\n\n"
        f"Job posting text:\n{truncated_text}\n\n"
        "Extract skill/domain keywords that are NOT in any of the existing lists above (neither ontology nor existing_skills). "
        "If all relevant skills are already covered, output an empty array []."
        "Output ONLY a JSON array of strings."
    )

    full_prompt = prompt
    if ontology_context:
        full_prompt = f"{prompt}\n\n{ontology_context}"

    result = _call_llm(
        "You are an ontology expansion assistant. (Input) Find new skill keywords that do NOT exist in the provided ontology.",
        full_prompt,
        max_tokens=256,
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
