import re
import os
import json
import time
import hashlib
import datetime
from typing import List, Tuple, Dict, Optional, Set
import html
import requests
import random
from pathlib import Path

import config
from writer import get_index_entry, save_json_archive, update_index_entry

# ── Ontology 로딩 (단일 진실 공급원) ──
# 실행 시점에 Ontology_Map.json을 읽어 키워드 집합을 구성한다.
# 더 이상 SKILL_PATTERNS 하드코딩 dict는 사용하지 않음.
_ONTOLOGY_KEYWORDS: List[str] = []
_ONTOLOGY_KEYWORD_SET: Set[str] = set()
_ONTOLOGY_SYNONYM_MAP: Dict[str, str] = {}  # synonym → standard_keyword
_ONTOLOGY_LOADED: bool = False

# Cache invalidation: 이 값을 올리면 모든 기존 analysis가 재실행됨
# v1 = regex+heuristic (old), v2 = ontology+llm (new)
ANALYSIS_SCHEMA_VERSION = 2


def _load_ontology(pjroot: Optional[Path] = None) -> None:
    """Ontology_Map.json에서 표준 키워드 + 동의어 목록을 로드."""
    global _ONTOLOGY_KEYWORDS, _ONTOLOGY_KEYWORD_SET, _ONTOLOGY_SYNONYM_MAP, _ONTOLOGY_LOADED
    if _ONTOLOGY_LOADED:
        return
    try:
        if pjroot is None:
            pjroot = Path(__file__).resolve().parents[1]
        onto_path = pjroot / "job_wiki" / "20_Meta" / "Ontology_Map.json"
        if not onto_path.exists():
            print(f"[analyzer] ontology file not found: {onto_path}", file=sys.stderr)
            _ONTOLOGY_LOADED = True
            return
        data = json.loads(onto_path.read_text(encoding="utf-8"))
        mappings = data.get("mappings", {}) if isinstance(data, dict) else {}
        if not isinstance(mappings, dict):
            mappings = {}
        keywords = []
        synonym_map = {}
        for std_key, syns in mappings.items():
            keywords.append(std_key)
            for syn in syns:
                if syn and syn != std_key:
                    keywords.append(syn)
                    synonym_map[syn] = std_key
        _ONTOLOGY_KEYWORDS = keywords
        _ONTOLOGY_KEYWORD_SET = set(keywords)
        _ONTOLOGY_SYNONYM_MAP = synonym_map
        _ONTOLOGY_LOADED = True
        print(f"[analyzer] ontology loaded: {len(keywords)} keywords ({len(mappings)} standards)", file=sys.stderr)
    except Exception as e:
        print(f"[analyzer] ontology load failed: {e}", file=sys.stderr)
        _ONTOLOGY_LOADED = True


import sys  # noqa: E402 (needed for print to stderr)
_ONTOLOGY_LOADED = False  # force reload on import


def _normalize_for_match(kw: str) -> str:
    """키워드 비교용 정규화: 공백/특수문자 제거, 소문자 변환."""
    return re.sub(r"[^\w가-힣]", "", kw).strip().lower()


def _match_ontology_keywords(text: str) -> List[str]:
    """텍스트에서 온톨로지 키워드를 substring 매칭으로 찾는다.

    우선순위: 긴 키워드 우선 (ex: "소프트웨어 개발 및 유지보수"가
    "소프트웨어"보다 먼저 매칭되도록).
    """
    _load_ontology()
    if not _ONTOLOGY_KEYWORDS:
        return []
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = html.unescape(cleaned)
    cleaned_lower = cleaned.lower()

    # 긴 키워드 우선 정렬 (longest first for greedy matching)
    sorted_kw = sorted(_ONTOLOGY_KEYWORDS, key=lambda k: (-len(k), k))

    found = []
    seen = set()
    for kw in sorted_kw:
        nk = _normalize_for_match(kw)
        if nk in seen:
            continue

        # 1) direct substring match
        if nk in cleaned_lower or kw.lower() in cleaned_lower:
            std = _ONTOLOGY_SYNONYM_MAP.get(kw, kw)
            norm_std = _normalize_for_match(std)
            if norm_std not in seen:
                found.append(std)
                seen.add(norm_std)
            continue

        # 2) word-level partial match (보조)
        #    "간호사" (kw word) matches "간호" (text word) via containment
        #    조건: 최소 3글자, 포함 비율 50% 이상, stopword 제외
        _STOPWORDS = {"관리", "시스템", "운영", "기술", "지원", "업무", "평가", "검사", "개발",
                      "교육", "능력", "처리", "계획", "정보", "분석", "기반", "이해", "조직"}
        kw_words = nk.split()
        if not kw_words:
            continue
        text_words = [w for w in cleaned_lower.split()
                      if len(w) >= 3 and w not in _STOPWORDS]
        if not text_words:
            continue
        matched = False
        for kw_word in kw_words:
            if len(kw_word) < 3 or kw_word in _STOPWORDS:
                continue
            for tw in text_words:
                if len(tw) < 3 or tw in _STOPWORDS:
                    continue
                # proportion check: the containER must be >= 50% longer than containEE
                if kw_word in tw:
                    ratio = len(kw_word) / len(tw)
                elif tw in kw_word:
                    ratio = len(tw) / len(kw_word)
                else:
                    continue
                if ratio >= 0.5:
                    std = _ONTOLOGY_SYNONYM_MAP.get(kw, kw)
                    norm_std = _normalize_for_match(std)
                    if norm_std not in seen:
                        found.append(std)
                        seen.add(norm_std)
                    matched = True
                    break
            if matched:
                break

    return found


def preprocess_text(text: str) -> str:
    if not text:
        return ""
    # remove HTML tags and unescape entities
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    # normalize whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# ── Fallback heuristic (LLM 장애 시만 사용) ──
def _heuristic_analysis(text: str, ontology_matched: List[str], ncs_text: str = "") -> Dict:
    """Fallback deterministic analysis when LLM is unavailable.

    Ontology 매칭 결과 + NCS 기반으로 최소한의 정보만 생성.
    """
    text = preprocess_text(text)

    # job_nature guess
    if re.search(r"연구|연구원|R&D|개발", text, flags=re.I):
        job_nature = "연구/개발"
    elif re.search(r"운영|운용|관리|운영자", text, flags=re.I):
        job_nature = "운영/관리"
    elif re.search(r"설계|디자인|설계자", text, flags=re.I):
        job_nature = "설계"
    else:
        job_nature = "실무/혼합"

    k = len(ontology_matched)
    if k >= 6:
        complexity = "high"
    elif k >= 3:
        complexity = "medium"
    else:
        complexity = "low"

    core_logic = "; ".join(re.findall(r"(모니터링|스케줄링|스케줄|제어|최적화|시뮬레이션|검증|테스트)", text, flags=re.I)[:3]) or "주요 업무 로직이 공고에 명시되어있음"

    domain_context = ncs_text if ncs_text else "일반"

    return {
        "core_logic": core_logic,
        "domain_context": domain_context,
        "job_nature": job_nature,
        "complexity": complexity,
    }


# ── LLM extraction (메인) ──
def _build_ontology_context(max_keywords: int = 30) -> str:
    """프롬프트용 온톨로지 컨텍스트 문자열 생성."""
    _load_ontology()
    if not _ONTOLOGY_KEYWORDS:
        return ""
    # standard keywords만 (synonym 제외) 보여줌
    std_set = set()
    result = []
    for kw in _ONTOLOGY_KEYWORDS:
        std = _ONTOLOGY_SYNONYM_MAP.get(kw, kw)
        if std not in std_set:
            std_set.add(std)
            result.append(f"  - {std}")
    if not result:
        return ""
    return (
        "\nCurrent ontology standard keywords (use these for matching where possible):\n"
        + "\n".join(result[:max_keywords])
        + ("\n  ... (truncated)" if len(result) > max_keywords else "")
    )


def _call_llm_for_dna(text: str, ontology_matched: List[str],
                      ncs_text: Optional[str] = None) -> Tuple[Optional[dict], int, float]:
    """Call external LLM for exhaustive keyword extraction.

    Returns (parsed_json, tokens_estimate, cost_estimate).
    If provider key not present or a call fails, returns (None, 0, 0.0).
    """
    provider = getattr(config, "LLM_PROVIDER", os.getenv("LLM_PROVIDER", "opencode-go")).lower()

    ontology_ctx = _build_ontology_context(max_keywords=30)

    system = (
        "You are a comprehensive job-posting analyzer. Given a job posting excerpt, "
        "extract ALL skill/domain keywords present in the text exhaustively.\n\n"
        "Rules:\n"
        "1. Output ONLY valid JSON — no commentary, no markdown wrappers.\n"
        "2. Extract every relevant keyword without filtering against any predefined list. "
        "If a skill/domain term appears in the text, capture it.\n"
        "3. new_keywords: terms that are NOT covered by the provided ontology keywords.\n"
        "4. Be specific — prefer '경마 운영·관리' over generic '운영/관리'.\n"
        "5. domain_context: single concise phrase describing the job domain "
        "(e.g., '경마/레저', '보건.의료', '제조/자동화', 'IT/소프트웨어').\n"
        "6. core_logic: '분야 / 대상에 대한 행위' format (e.g., '경마장/시설 및 마필 관리에 대한 운영적 행위').\n\n"
        "JSON keys:\n"
        "  - core_logic: string\n"
        "  - domain_context: string\n"
        "  - all_keywords: array of strings (ALL keywords found, include ontology matches and new ones)\n"
        "  - new_keywords: array of strings (keywords NOT in the ontology list above)\n"
        "  - job_nature: one of '연구/개발', '운영/관리', '설계', '실무/혼합'\n"
        "  - complexity: 'low', 'medium', or 'high'\n\n"
        "Return valid JSON only."
    )

    domain_hint_text = f"NCS_HINT: {ncs_text}\n\n" if ncs_text else ""
    matched_str = ", ".join(ontology_matched) if ontology_matched else "(none yet)"
    user_msg = (
        domain_hint_text
        + f"ONTOLOGY_MATCHED: {matched_str}\n"
        + (ontology_ctx + "\n\n" if ontology_ctx else "")
        + f"JOB_TEXT:\n{text[:2000]}\n\n"
        + "Return valid JSON only."
    )

    parsed = None
    approx_tokens = 0
    cost = 0.0

    # ── OpenCode Go ──
    if provider == "opencode-go":
        api_key = os.getenv("OPENCODE_API_KEY")
        if not api_key:
            return None, 0, 0.0
        base_url = os.getenv("OPENCODE_BASE_URL", "https://opencode.ai/zen/go/v1").rstrip("/")
        model = os.getenv("LLM_EXTRACT_MODEL", "deepseek-v4-flash")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            "temperature": 0.0,
            "max_tokens": 512,
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        try:
            resp = requests.post(
                f"{base_url}/chat/completions",
                headers=headers, json=payload, timeout=30,
            )
            resp.raise_for_status()
            j = resp.json()
            content = ""
            try:
                c0_msg = j["choices"][0]["message"]
                content = c0_msg.get("content", "") or ""
                # DeepSeek 모델: reasoning_content에 실제 답변이 있을 수 있음
                if not content and "reasoning_content" in c0_msg:
                    content = c0_msg.get("reasoning_content", "") or ""
            except Exception:
                content = j.get("choices", [{}])[0].get("text", "")
            try:
                parsed = json.loads(content)
            except Exception:
                m = re.search(r"\{[\s\S]*\}", content)
                if m:
                    try:
                        parsed = json.loads(m.group(0))
                    except Exception:
                        pass
            if parsed:
                approx_tokens = int((len(user_msg) + len(content)) / 4)
                cost = (approx_tokens / 1000.0) * float(getattr(config, "ANALYSIS_COST_PER_1K_TOKENS", 0.003))
                return parsed, approx_tokens, cost
            else:
                err_msg = content[:300] if content else "(empty response)"
                # Also log the raw response structure for debugging
                try:
                    resp_summary = {k: type(v).__name__ for k, v in j.items()}
                    if "choices" in j:
                        resp_summary["choices_len"] = len(j["choices"])
                        if j["choices"]:
                            c0 = j["choices"][0]
                            if isinstance(c0, dict):
                                resp_summary["choice0_keys"] = list(c0.keys())
                                if "message" in c0 and isinstance(c0["message"], dict):
                                    resp_summary["message_keys"] = list(c0["message"].keys())
                                    resp_summary["content_type"] = type(c0["message"].get("content")).__name__
                                    if c0["message"].get("content") is not None:
                                        resp_summary["content_len"] = len(str(c0["message"]["content"]))
                                elif "delta" in c0:
                                    resp_summary["has_delta"] = True
                    print(f"[analyzer] LLM parse failed: {err_msg} | resp: {resp_summary}", file=sys.stderr)
                except Exception as log_e:
                    print(f"[analyzer] LLM parse failed: {err_msg}", file=sys.stderr)
            return None, 0, 0.0
        except requests.RequestException as e:
            print(f"[analyzer] LLM HTTP error ({provider}): {e}", file=sys.stderr)
            if hasattr(e, 'response') and e.response is not None:
                print(f"[analyzer] LLM response body: {e.response.text[:300]}", file=sys.stderr)
            return None, 0, 0.0
        except Exception as e:
            print(f"[analyzer] LLM unexpected error ({provider}): {e}", file=sys.stderr)
            return None, 0, 0.0

    # ── NVIDIA Integrate ──
    if provider == "nvidia":
        api_key = os.getenv("NVIDIA_API_KEY") or getattr(config, "NVIDIA_API_KEY", None)
        if not api_key:
            return None, 0, 0.0
        base_url = getattr(config, "NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
        model = getattr(config, "NVIDIA_MODEL", None) or getattr(config, "ANALYSIS_MODEL", None)
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            "temperature": 0.0,
            "top_p": 0.95,
            "max_tokens": 512,
            "extra_body": {"chat_template_kwargs": {"thinking": True, "reasoning_effort": "high"}},
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        timeout = getattr(config, "LLM_TIMEOUT", getattr(config, "NVIDIA_TIMEOUT", 30))
        max_attempts = int(getattr(config, "RETRY_ATTEMPTS", 3) or 3)
        backoff_factor = float(getattr(config, "RETRY_BACKOFF_FACTOR", 1.5) or 1.5)
        last_exc = None
        for attempt in range(1, max_attempts + 1):
            try:
                resp = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=timeout)
                resp.raise_for_status()
                j = resp.json()
                content = ""
                try:
                    content = j["choices"][0]["message"]["content"]
                except Exception:
                    content = j.get("choices", [{}])[0].get("text", "")
                try:
                    parsed = json.loads(content)
                except Exception:
                    m = re.search(r"\{[\s\S]*\}", content)
                    if m:
                        try:
                            parsed = json.loads(m.group(0))
                        except Exception:
                            pass
                approx_tokens = int((len(user_msg) + len(content)) / 4)
                cost = (approx_tokens / 1000.0) * float(getattr(config, "ANALYSIS_COST_PER_1K_TOKENS", 0.003))
                return parsed, approx_tokens, cost
            except requests.RequestException as e:
                last_exc = e
                if attempt >= max_attempts:
                    break
                sleep_for = backoff_factor * (2 ** (attempt - 1)) + random.uniform(0, 1)
                time.sleep(sleep_for)
            except Exception:
                break
        return None, 0, 0.0

    # ── OpenAI ──
    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_TOKEN")
        if not api_key:
            return None, 0, 0.0
        model = getattr(config, "ANALYSIS_MODEL", "gpt-4o-mini")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            "max_tokens": 512,
            "temperature": 0.0,
        }
        try:
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=20,
            )
            resp.raise_for_status()
            j = resp.json()
            content = j.get("choices", [{}])[0].get("message", {}).get("content", "")
            try:
                parsed = json.loads(content)
            except Exception:
                m = re.search(r"\{[\s\S]*\}", content)
                if m:
                    try:
                        parsed = json.loads(m.group(0))
                    except Exception:
                        pass
            approx_tokens = int((len(user_msg) + len(content)) / 4)
            cost = (approx_tokens / 1000.0) * float(getattr(config, "ANALYSIS_COST_PER_1K_TOKENS", 0.003))
            return parsed, approx_tokens, cost
        except Exception:
            return None, 0, 0.0

    # ── Groq ──
    elif provider == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            return None, 0, 0.0
        base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
        primary_model = os.getenv("LLM_EXTRACT_MODEL", "llama-3.3-70b-versatile")
        groq_fallbacks = [
            primary_model,
            "meta-llama/llama-4-scout-17b-16e-instruct",
            "llama-3.1-8b-instant",
            "qwen/qwen3-32b",
            "openai/gpt-oss-20b",
            "openai/gpt-oss-120b",
        ]
        _last_groq_call: float = 0.0
        _groq_min_interval: float = 2.0
        for model_name in groq_fallbacks:
            payload = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
                "max_tokens": 512,
                "temperature": 0.0,
            }
            max_attempts = int(getattr(config, "RETRY_ATTEMPTS", 3) or 3)
            backoff_factor = float(getattr(config, "RETRY_BACKOFF_FACTOR", 1.5) or 1.5)
            for attempt in range(1, max_attempts + 1):
                try:
                    now = time.time()
                    if now - _last_groq_call < _groq_min_interval:
                        time.sleep(_groq_min_interval - (now - _last_groq_call))
                    _last_groq_call = time.time()
                    resp = requests.post(
                        f"{base_url}/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                        json=payload,
                        timeout=30,
                    )
                    if resp.status_code == 429:
                        break
                    resp.raise_for_status()
                    j = resp.json()
                    content = j.get("choices", [{}])[0].get("message", {}).get("content", "")
                    try:
                        parsed = json.loads(content)
                    except Exception:
                        m = re.search(r"\{[\s\S]*\}", content)
                        if m:
                            try:
                                parsed = json.loads(m.group(0))
                            except Exception:
                                pass
                    if model_name != primary_model:
                        print(f"[analyzer] switched to fallback model: {model_name}", file=sys.stderr)
                    approx_tokens = int((len(user_msg) + len(content)) / 4)
                    cost = (approx_tokens / 1000.0) * float(getattr(config, "ANALYSIS_COST_PER_1K_TOKENS", 0.003))
                    return parsed, approx_tokens, cost
                except requests.RequestException as e:
                    if "429" in str(e) or "Too Many Requests" in str(e):
                        break
                    if attempt >= max_attempts:
                        break
                    sleep_for = backoff_factor * (2 ** (attempt - 1)) + random.uniform(0, 1)
                    time.sleep(sleep_for)
                except Exception:
                    break
        return None, 0, 0.0

    return None, 0, 0.0


def analyze_objective_dna(job: dict, trimmed_text: str,
                          alio_id: Optional[str] = None, force_llm: bool = False,
                          base_dir: str = ".", raw_dir: str = "00_Raw") -> Dict:
    """온톨로지 기반 + LLM 추출 하이브리드 분석기.

    Strategy:
    1) Ontology_Map.json에서 키워드 substring 매칭 (무료)
    2) 항상 LLM 호출 (API 키 있으면) — exhaustive keyword extraction
    3) LLM 결과에 ontology-matched + new_keywords 통합
    4) 새 키워드 감지 시 json_archive에 new_keywords 필드 저장
       (wiki_generator가 이를 읽어 Suggested_Keywords.json에 반영)
    """
    _load_ontology()
    trimmed = (trimmed_text or "")
    content_hash = hashlib.sha256(trimmed.encode("utf-8") if isinstance(trimmed, str) else trimmed).hexdigest()

    # cache check
    if alio_id:
        entry = get_index_entry(alio_id, base_dir=base_dir, raw_dir=raw_dir)
        if isinstance(entry, str):
            entry_dict = {"filename": entry}
        else:
            entry_dict = entry or {}
        if entry_dict and entry_dict.get("content_hash") == content_hash and not force_llm:
            archive_path = os.path.join(str(config.BASE_DIR), config.RAW_DIR, config.JSON_ARCHIVE_DIR, f"{alio_id}.json")
            try:
                if os.path.exists(archive_path):
                    with open(archive_path, "r", encoding="utf-8") as fh:
                        archived = json.load(fh)
                    if archived and isinstance(archived, dict) and archived.get("analysis"):
                        cached_schema = archived["analysis"].get("schema_version", 1)
                        if cached_schema >= ANALYSIS_SCHEMA_VERSION:
                            archived["analysis"].setdefault("cached", True)
                            archived["analysis"].setdefault("cached_at", entry.get("last_analyzed_at"))
                            return archived["analysis"]
            except Exception:
                pass

    # 1) Ontology keyword matching (zero-cost)
    ontology_matched = _match_ontology_keywords(trimmed)

    # 2) NCS / domain hint detection
    ncs_text = ""
    try:
        raw_src = job.get("raw") if isinstance(job, dict) else {}
        ncs_text = (raw_src.get("ncsCdNmLst") or raw_src.get("ncsCdLst")
                    or job.get("ncsCdNmLst") or job.get("ncs") or "")
        ncs_text = str(ncs_text)
    except Exception:
        pass

    # 3) LLM extraction (always call when API key present)
    provider = getattr(config, "LLM_PROVIDER", os.getenv("LLM_PROVIDER", "opencode-go")).lower()
    has_api_key = (
        (provider == "opencode-go" and os.getenv("OPENCODE_API_KEY"))
        or (provider == "nvidia" and (os.getenv("NVIDIA_API_KEY") or getattr(config, "NVIDIA_API_KEY", None)))
        or (provider == "openai" and (os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_TOKEN")))
        or (provider == "groq" and os.getenv("GROQ_API_KEY"))
    )
    call_llm = force_llm or has_api_key

    analysis: Dict = {
        "explicit_skills": list(ontology_matched),
        "skills_found": list(ontology_matched),
        "core_logic": None,
        "domain_context": None,
        "latent_skills": [],
        "job_nature": None,
        "complexity": None,
        "skills_additional": [],
        "new_keywords": [],
        "method": "ontology_match",
        "schema_version": ANALYSIS_SCHEMA_VERSION,
        "model": None,
        "tokens": 0,
        "cost": 0.0,
        "analyzed_at": datetime.datetime.utcnow().isoformat() + "Z",
    }

    if call_llm:
        parsed, tokens_used, cost_used = _call_llm_for_dna(trimmed, ontology_matched, ncs_text=ncs_text if ncs_text else None)
        if parsed:
            analysis["core_logic"] = parsed.get("core_logic") or analysis["core_logic"]
            analysis["domain_context"] = parsed.get("domain_context") or ncs_text or ""
            analysis["job_nature"] = parsed.get("job_nature") or "실무/혼합"
            analysis["complexity"] = parsed.get("complexity") or "medium"

            # Combine: ontology-matched + LLM all_keywords (dedup)
            llm_all = parsed.get("all_keywords") or []
            llm_new = parsed.get("new_keywords") or []
            combined = list(dict.fromkeys(list(ontology_matched) + llm_all))
            analysis["explicit_skills"] = list(ontology_matched)
            analysis["skills_found"] = combined
            analysis["skills_additional"] = [kw for kw in llm_all if kw not in ontology_matched]
            analysis["new_keywords"] = llm_new
            analysis["latent_skills"] = llm_new  # new = latent (not yet in ontology)
            analysis["method"] = "ontology+llm"

            if provider == "opencode-go":
                analysis["model"] = os.getenv("LLM_EXTRACT_MODEL", "deepseek-v4-flash")
            elif provider == "nvidia":
                analysis["model"] = getattr(config, "NVIDIA_MODEL", None)
            else:
                analysis["model"] = getattr(config, "ANALYSIS_MODEL", None)
            analysis["tokens"] = tokens_used
            analysis["cost"] = cost_used
        else:
            # LLM failed — fallback: ontology match + minimal heuristic
            h = _heuristic_analysis(trimmed, ontology_matched, ncs_text=ncs_text)
            analysis.update(h)
            analysis["skills_found"] = list(ontology_matched)
            analysis["method"] = "ontology+heuristic"
    else:
        # No API key — ontology match only
        h = _heuristic_analysis(trimmed, ontology_matched, ncs_text=ncs_text)
        analysis.update(h)
        analysis["skills_found"] = list(ontology_matched)
        analysis["method"] = "ontology_only"

    # 4) save analysis into json archive
    try:
        if alio_id:
            job_raw = job.get("raw") if isinstance(job, dict) else None
            if isinstance(job, dict) and job.get("raw") is None:
                job_raw = job
            save_json_archive(job_raw or {}, alio_id, base_dir=base_dir, raw_dir=raw_dir)
            archive_path = os.path.join(str(config.BASE_DIR), config.RAW_DIR, config.JSON_ARCHIVE_DIR, f"{alio_id}.json")
            try:
                if os.path.exists(archive_path):
                    with open(archive_path, "r", encoding="utf-8") as fh:
                        cur = json.load(fh)
                else:
                    cur = {"raw": job_raw or {}}
                cur["analysis"] = analysis
                with open(archive_path, "w", encoding="utf-8") as fh:
                    json.dump(cur, fh, ensure_ascii=False, indent=2)
            except Exception:
                pass
            update_index_entry(alio_id, content_hash=content_hash, last_analyzed_at=analysis.get("analyzed_at"),
                               base_dir=base_dir, raw_dir=raw_dir)
    except Exception:
        pass

    return analysis


# ═══════════════════════════════════════
# Backward compat: extract_skills_and_reasoning
# (used by reanalyze.py and harvester.py — wraps new ontology logic)
# ═══════════════════════════════════════


def extract_skills_and_reasoning(text: str, user_interests: list, top_n: int = 4, ncs: str = "") -> tuple:
    """Backward-compatible wrapper for legacy callers.

    Uses ontology matching + LLM extraction internally.
    Returns (skills_list, reason_string).
    """
    preprocessed = preprocess_text(text)
    onto_matched = _match_ontology_keywords(preprocessed)

    provider = getattr(config, "LLM_PROVIDER", os.getenv("LLM_PROVIDER", "opencode-go")).lower()
    has_key = (
        (provider == "opencode-go" and os.getenv("OPENCODE_API_KEY"))
        or (provider == "nvidia" and (os.getenv("NVIDIA_API_KEY") or getattr(config, "NVIDIA_API_KEY", None)))
        or (provider == "openai" and (os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_TOKEN")))
        or (provider == "groq" and os.getenv("GROQ_API_KEY"))
    )
    if has_key and len(preprocessed) >= 50:
        parsed, _, _ = _call_llm_for_dna(preprocessed, onto_matched, ncs_text=ncs if ncs else None)
        if parsed:
            all_kw = parsed.get("all_keywords", []) or []
            combined = list(dict.fromkeys(onto_matched + all_kw))[:top_n]
            reason = f"ontology+llm: {parsed.get('core_logic', '') or ''}"
            return combined, reason

    if onto_matched:
        return onto_matched[:top_n], f"ontology_match: {len(onto_matched)} keywords found"

    h = _heuristic_analysis(preprocessed, [], ncs_text=ncs)
    return [], f"heuristic_fallback: {h.get('core_logic', '') or ''}"
