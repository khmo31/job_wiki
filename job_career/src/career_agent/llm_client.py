"""경량 LLM 클라이언트 — OpenAI/NVIDIA/Groq API 호출"""
from __future__ import annotations

import json
import os
import sys
from typing import Any


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

    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.0,
        "max_tokens": max_tokens,
    }

    try:
        import requests
        resp = requests.post(
            f"{cfg['base_url'].rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return content.strip()
    except Exception as e:
        _log(f"LLM call failed: {e}")
        return None


EXTRACT_KEYWORDS_SYSTEM = """You are a career keyword extraction assistant.
Given a user's career profile, extract the most relevant skill/domain keywords.
Match them against the existing ontology keywords if possible.
Output ONLY a JSON array of keyword strings, no other text.
Example: ["의료 행정 지식", "의료정보 보호", "문서 작성 및 관리"]"""


def extract_keywords(user_profile: str) -> list[str] | None:
    """LLM으로 사용자 프로필에서 wiki 키워드 추출. 실패 시 None 반환."""
    result = _call_llm(EXTRACT_KEYWORDS_SYSTEM, user_profile, max_tokens=256)
    if not result:
        return None

    try:
        # Parse JSON array
        parsed = json.loads(result)
        if isinstance(parsed, list):
            return [str(k).strip() for k in parsed if k]
    except json.JSONDecodeError:
        pass

    # Fallback: extract bracketed keywords
    import re
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
    result = _call_llm(CLASSIFY_SYSTEM, text[:2000], max_tokens=512)
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
    """공고 텍스트에서 기존 온톨로지에 없는 신규 키워드 제안."""
    existing_str = ", ".join(existing_skills) if existing_skills else "(none yet)"
    prompt = (
        f"Existing ontology skills: [{existing_str}]\n\n"
        f"Job posting text:\n{text[:2000]}\n\n"
        "Extract skill/domain keywords that are NOT in the existing list above. "
        "Output ONLY a JSON array of strings."
    )
    result = _call_llm(
        "You are an ontology expansion assistant. Find new skill keywords in the job text.",
        prompt,
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
