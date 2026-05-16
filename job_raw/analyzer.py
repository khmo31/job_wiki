import re
import os
import json
import time
import hashlib
import datetime
from typing import List, Tuple, Dict, Optional
import html
import requests
import random

import config
from writer import get_index_entry, save_json_archive, update_index_entry

# 경량 패턴 사전: 필요하면 확장하세요
SKILL_PATTERNS: Dict[str, List[str]] = {
    "아두이노": [r"아두이노", r"arduino"],
    "시리얼 통신": [r"시리얼", r"Serial", r"UART"],
    "PLC": [r"PLC"],
    "자동화 알고리즘": [r"자동화 알고리즘", r"자동화 로직", r"제어 알고리즘", r"제어 로직", r"최적화"],
    "C/C++": [r"C\+\+", r"\bC\b"],
    "Python": [r"Python", r"파이썬"],
    "센서": [r"센서", r"sensor"],
    "데이터 로깅": [r"데이터 로깅", r"로깅", r"데이터 수집"],
    "ROS": [r"ROS"],
    "임베디드": [r"임베디드", r"embedded"],
    # factory-simulation / logistics / production keywords
    "자원 배분": [r"자원 배분", r"자원배분", r"resource allocation"],
    "물류": [r"물류", r"로지스틱", r"물류 최적화", r"물류관리"],
    "재고 관리": [r"재고", r"재고 관리", r"inventory"],
    "생산계획": [r"생산계획", r"스케줄링", r"스케줄", r"생산 스케줄"],
    "병목 분석": [r"병목", r"bottleneck", r"throughput", r"takt"],
    "시뮬레이션": [r"시뮬레이션", r"디지털 트윈", r"시뮬레이터"],
    "MES": [r"MES", r"생산관리시스템"],
}


# Simple heuristics for whether an occurrence seems to be a "responsibility/requirement" sentence
BOOST_CONTEXT_WORDS = ["주요", "담당", "필수", "필요", "요구", "우대", "자격", "경력", "경험", "책임", "역할"]


def preprocess_text(text: str) -> str:
    if not text:
        return ""
    # remove HTML tags and unescape entities
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    # normalize whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _regex_extract_skills(text: str) -> List[str]:
    """Run lightweight regex dictionary matching to get explicitly mentioned skills (zero-cost)."""
    text = preprocess_text(text)
    found = []
    for skill, patterns in SKILL_PATTERNS.items():
        for p in patterns:
            if re.search(p, text, flags=re.I):
                if skill not in found:
                    found.append(skill)
                break
    return found


def _heuristic_analysis(text: str, explicit_skills: List[str]) -> Dict:
    """Fallback deterministic analysis when LLM is unavailable or unnecessary."""
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

    # complexity: simple heuristic by number of explicit skills
    k = len(explicit_skills)
    if k >= 6:
        complexity = "high"
    elif k >= 3:
        complexity = "medium"
    else:
        complexity = "low"

    # latent skills: try to infer from keywords not explicitly in patterns
    latent = []
    if re.search(r"시리얼|UART|SPI|I2C", text, flags=re.I) and "시리얼 통신" not in explicit_skills:
        latent.append("시리얼 통신")
    if re.search(r"데이터\s*로깅|데이터 수집|로깅", text, flags=re.I) and "데이터 로깅" not in explicit_skills:
        latent.append("데이터 로깅")
    if re.search(r"PLC|플라스틱로직컨트롤러|PLC", text, flags=re.I) and "PLC" not in explicit_skills:
        latent.append("PLC")

    # core logic and domain context simple extraction
    core_logic = "; ".join(re.findall(r"(모니터링|스케줄링|스케줄|제어|최적화|시뮬레이션|검증|테스트)", text, flags=re.I)[:3]) or "주요 업무 로직이 공고에 명시되어있음"
    domain_context = "제조/공장/임베디드 관련" if re.search(r"제조|생산|공장|임베디드|로봇", text, flags=re.I) else "일반 소프트웨어/IT"

    return {
        "core_logic": core_logic,
        "domain_context": domain_context,
        "latent_skills": latent,
        "job_nature": job_nature,
        "complexity": complexity,
        "skills_additional": [],
    }


def _call_llm_for_dna(text: str, explicit_skills: List[str], domain_hint: Optional[str] = None) -> Tuple[Optional[dict], int, float]:
    """Call external LLM (supports OpenAI or NVIDIA Integrate). Returns (parsed_json, tokens_estimate, cost_estimate).

    If provider key not present or a call fails, returns (None, 0, 0.0).
    """
    provider = getattr(config, "LLM_PROVIDER", os.getenv("LLM_PROVIDER", "nvidia")).lower()

    system = (
        "You are a pragmatic job-analysis assistant. Given a job posting excerpt and an optional domain hint,"
        " produce a concise JSON summary describing the role's core logic.\n"
        "Output only valid JSON with keys: core_logic (short string), domain_context (short string), latent_skills (array of short strings),"
        " job_nature (one of: 연구/개발, 운영/관리, 설계, 실무/혼합), complexity (low/medium/high), skills_additional (array).\n"
        "GUIDELINES:\n"
        "- Extract the primary operational or technical purpose directly from the input text; base your answer only on evidence present in the input.\n"
        "- Do not invent specific certifications, qualifications, vendor names, or technical terms that are not explicitly present in the input.\n"
        "- If the input lacks granular technical detail, summarize at a higher-level category rather than fabricating specifics.\n"
        "- Prefer concise phrasing. When feasible, format `core_logic` as '[domain] / [target]에 대한 [동사]적 행위', but do not force precise labels without evidence.\n"
        "Return only valid JSON; do not include extraneous commentary."
    )

    # include explicit domain hint (NCS or raw category) in the user message to reduce domain confusion
    domain_hint_text = f"DOMAIN_HINT: {domain_hint}\n\n" if domain_hint else ""
    user_msg = (
        domain_hint_text + f"EXPLICIT_SKILLS: {json.dumps(explicit_skills, ensure_ascii=False)}\n\nTEXT:\n{text}\n\nReturn valid JSON only."
    )

    # Default values
    parsed = None
    approx_tokens = 0
    cost = 0.0

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
            "max_tokens": 256,
            "extra_body": {"chat_template_kwargs": {"thinking": True, "reasoning_effort": "high"}},
        }
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        # respect global LLM timeout and retry settings
        timeout = getattr(config, "LLM_TIMEOUT", getattr(config, "NVIDIA_TIMEOUT", 20))
        max_attempts = int(getattr(config, "RETRY_ATTEMPTS", 3) or 3)
        backoff_factor = float(getattr(config, "RETRY_BACKOFF_FACTOR", 1.5) or 1.5)

        last_exc = None
        for attempt in range(1, max_attempts + 1):
            try:
                resp = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=timeout)
                resp.raise_for_status()
                j = resp.json()
                # try common locations for content
                content = ""
                try:
                    content = j["choices"][0]["message"]["content"]
                except Exception:
                    content = j.get("choices", [{}])[0].get("text", "")

                # parse JSON
                try:
                    parsed = json.loads(content)
                except Exception:
                    m = re.search(r"\{[\s\S]*\}", content)
                    if m:
                        try:
                            parsed = json.loads(m.group(0))
                        except Exception:
                            parsed = None

                approx_tokens = int((len(user_msg) + len(content)) / 4)
                cost = (approx_tokens / 1000.0) * float(getattr(config, "ANALYSIS_COST_PER_1K_TOKENS", 0.003))
                return parsed, approx_tokens, cost
            except requests.RequestException as e:
                last_exc = e
                # retry on network/HTTP errors with exponential backoff + jitter
                if attempt >= max_attempts:
                    break
                sleep_for = backoff_factor * (2 ** (attempt - 1)) + random.uniform(0, 1)
                time.sleep(sleep_for)
                continue
            except Exception as e:
                # non-network error — do not retry
                last_exc = e
                break

        return None, 0, 0.0

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
            "max_tokens": 256,
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
                        parsed = None

            approx_tokens = int((len(user_msg) + len(content)) / 4)
            cost = (approx_tokens / 1000.0) * float(getattr(config, "ANALYSIS_COST_PER_1K_TOKENS", 0.003))
            return parsed, approx_tokens, cost
        except Exception:
            return None, 0, 0.0

    elif provider == "groq":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            return None, 0, 0.0
        base_url = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
        model = os.getenv("LLM_EXTRACT_MODEL", "llama-3.1-8b-instant")
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            "max_tokens": 256,
            "temperature": 0.0,
        }
        max_attempts = int(getattr(config, "RETRY_ATTEMPTS", 3) or 3)
        backoff_factor = float(getattr(config, "RETRY_BACKOFF_FACTOR", 1.5) or 1.5)
        last_exc = None
        for attempt in range(1, max_attempts + 1):
            try:
                resp = requests.post(
                    f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                    json=payload,
                    timeout=30,
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
                            parsed = None
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

    # unsupported provider
    return None, 0, 0.0


def _find_sentence_with_pattern(text: str, pattern: str) -> Optional[str]:
    # split into sentences by punctuation
    for sent in re.split(r"(?<=[\.\?\!\n])\s+", text):
        if re.search(pattern, sent, flags=re.I):
            return sent.strip()
    return None


def extract_skills_and_reasoning(
    text: str,
    user_interests: List[str],
    top_n: int = 4,
    ncs: Optional[str] = None,
) -> Tuple[List[str], Dict[str, str]]:
    text = preprocess_text(text)
    scores: Dict[str, Dict] = {}
    for skill, patterns in SKILL_PATTERNS.items():
        score = 0
        evidence = None
        for p in patterns:
            hits = re.findall(p, text, flags=re.I)
            if hits:
                score += len(hits)
                if not evidence:
                    evidence = _find_sentence_with_pattern(text, p)
        # boost if appears in context words
        if evidence:
            if any(w in evidence for w in BOOST_CONTEXT_WORDS):
                score += 2
        scores[skill] = {"score": score, "evidence": evidence}

    # interest-based boost
    INTEREST_MAP = {
        "아두이노": ["아두이노", "임베디드", "시리얼 통신"],
        "공장 게임": ["자원 배분", "물류", "재고 관리", "생산계획", "병목 분석", "시뮬레이션", "PLC", "데이터 로깅", "센서"],
        "자동화 로직": ["자동화 알고리즘", "PLC", "임베디드", "C/C++", "MES"],
    }

    for interest in user_interests:
        related = INTEREST_MAP.get(interest, [])
        for r in related:
            if r in scores:
                scores[r]["score"] += 3

    # extra boost if interest keywords appear directly in text
    for interest in user_interests:
        if re.search(re.escape(interest), text, flags=re.I):
            related = INTEREST_MAP.get(interest, [])
            for r in related:
                if r in scores:
                    scores[r]["score"] += 5

    # if NCS info provided, boost skills that map to that NCS category
    try:
        if ncs:
            ncs_norm = ncs or ""
            for ncs_key, synonyms in config.NCS_MAP.items():
                if any(syn.lower() in ncs_norm.lower() for syn in synonyms + [ncs_key]):
                    # boost skills that are semantically related to this NCS key
                    for skill_name, pattern_list in SKILL_PATTERNS.items():
                        # simple heuristic: if skill name contains ncs_key or synonyms, boost
                        if ncs_key.lower() in skill_name.lower():
                            scores.setdefault(skill_name, {"score": 0, "evidence": None})
                            scores[skill_name]["score"] += 4
                    # also add small boost to all interest-related skills
                    for interest in user_interests:
                        related = INTEREST_MAP.get(interest, [])
                        for r in related:
                            if r in scores:
                                scores[r]["score"] += 2
    except Exception:
        pass

    items = sorted(scores.items(), key=lambda kv: kv[1]["score"], reverse=True)
    selected = [k for k, v in items if v["score"] > 0][:top_n]
    if not selected:
        selected = [k for k, _ in items][:top_n]

    reasoning: Dict[str, str] = {}
    for s in selected:
        ev = scores[s].get("evidence") or "공고에서 관련 표현이 발견됨"
        # find best matching interest for the skill
        best_interest = next((i for i in user_interests if s in INTEREST_MAP.get(i, [])), (user_interests[0] if user_interests else "관심사"))

        # richer template depending on interest/skill
        if best_interest == "공장 게임":
            insight = (
                f"{s}: 공고 문구 '{ev}'이(가) 관찰되어, 이는 생산/물류 흐름의 '설계' 관점—예: 자원 배분·스케줄링·재고 최적화와 직결됩니다. 당신의 '공장 게임' 성향(시스템 설계·자원흐름 최적화)과 실무 연결 가능성이 높습니다."
            )
        elif best_interest == "아두이노":
            insight = (
                f"{s}: 공고 문구 '{ev}'이(가) 관찰되어, 이는 하드웨어-펌웨어 통합(임베디드/시리얼 통신) 역량과 직접 연결됩니다. 간단한 프로토타입부터 신뢰성 있는 제어까지 확장 가능한 기술입니다."
            )
        else:
            insight = (
                f"{s}: 공고 문구 '{ev}'이(가) 관찰되어, 이는 당신의 '{best_interest}' 관심사와 실무 기술이 연결된다는 직관적 비약입니다."
            )

        # NCS hints
        ncs_hint = ""
        try:
            if ncs:
                for ncs_key, synonyms in config.NCS_MAP.items():
                    if any(syn.lower() in (ncs or "").lower() for syn in synonyms + [ncs_key]):
                        ncs_hint = f"(NCS: {ncs_key} 관련 역량으로 분류될 가능성이 높음)"
                        break
        except Exception:
            pass

        reasoning[s] = insight + (" " + ncs_hint if ncs_hint else "")

    return selected, reasoning


def analyze_objective_dna(job: dict, trimmed_text: str, alio_id: Optional[str] = None, force_llm: bool = False, base_dir: str = ".", raw_dir: str = "00_Raw") -> Dict:
    """Hybrid analyzer that returns an 'objective DNA' dict for the job posting.

    Strategy:
    1) cheap regex dictionary match to get explicit skills
    2) if necessary and available, call a low-cost LLM to distill core_logic, domain_context, latent_skills, job_nature, complexity
    3) cache results in json_archive and update index with last_analyzed_at and content_hash
    """
    trimmed = (trimmed_text or "")
    content_hash = hashlib.sha256(trimmed.encode("utf-8") if isinstance(trimmed, str) else trimmed).hexdigest()

    # check cache
    if alio_id:
        entry = get_index_entry(alio_id, base_dir=base_dir, raw_dir=raw_dir)
        # support legacy index entries that may be a filename string
        if isinstance(entry, str):
            entry_dict = {"filename": entry}
        else:
            entry_dict = entry or {}
        if entry_dict and entry_dict.get("content_hash") == content_hash and not force_llm:
            # try to return existing analysis from json archive
            archive_path = os.path.join(str(config.BASE_DIR), config.RAW_DIR, config.JSON_ARCHIVE_DIR, f"{alio_id}.json")
            try:
                if os.path.exists(archive_path):
                    with open(archive_path, "r", encoding="utf-8") as fh:
                        archived = json.load(fh)
                    if archived and isinstance(archived, dict) and archived.get("analysis"):
                        archived["analysis"].setdefault("cached", True)
                        archived["analysis"].setdefault("cached_at", entry.get("last_analyzed_at"))
                        return archived["analysis"]
            except Exception:
                pass

    explicit = _regex_extract_skills(trimmed)

    # detect NCS / domain hint text for later use (do NOT short-circuit here)
    ncs_text = ""
    ncs_nontechnical = False
    try:
        raw_src = job.get("raw") if isinstance(job, dict) else {}
        ncs_text = (raw_src.get("ncsCdNmLst") or raw_src.get("ncsCdLst") or job.get("ncsCdNmLst") or job.get("ncs") or "")
        ncs_text = str(ncs_text).lower()
        non_technical_terms = [
            "보건",
            "의료",
            "간호",
            "교육",
            "복지",
            "사회복지",
            "예술",
            "행정",
            "사무",
        ]
        for term in non_technical_terms:
            if term in ncs_text:
                ncs_nontechnical = True
                break
    except Exception:
        ncs_nontechnical = False

    # decide whether to call LLM (provider-aware)
    provider = getattr(config, "LLM_PROVIDER", os.getenv("LLM_PROVIDER", "nvidia")).lower()
    call_llm = False
    if force_llm:
        call_llm = True
    else:
        if len(trimmed) >= getattr(config, "ANALYSIS_MIN_CHARS_TO_CALL_LLM", 80):
            if provider == "nvidia" and (os.getenv("NVIDIA_API_KEY") or getattr(config, "NVIDIA_API_KEY", None)):
                call_llm = True
            elif provider == "openai" and (os.getenv("OPENAI_API_KEY") or os.getenv("OPENAI_API_TOKEN")):
                call_llm = True
            elif provider == "groq" and os.getenv("GROQ_API_KEY"):
                call_llm = True

    # Apply NCS filter mode (configurable). Default is 'off' (no short-circuit).
    ncs_filter_mode = getattr(config, "NCS_FILTER_MODE", os.getenv("NCS_FILTER_MODE", "off")).lower()
    force_override = getattr(config, "FORCE_LLM_OVERRIDE", False) or str(os.getenv("FORCE_LLM_OVERRIDE", "0")).lower() in ("1", "true", "yes")

    filtered_due_to_ncs = False
    if not force_llm and not force_override and ncs_nontechnical:
        if ncs_filter_mode == "hard":
            call_llm = False
            filtered_due_to_ncs = True
        elif ncs_filter_mode == "soft":
            # sample a small fraction to call LLM for audit; others are filtered
            sample_rate = float(getattr(config, "SAMPLE_FILTERED_RATE", os.getenv("SAMPLE_FILTERED_RATE", 0.1)))
            if random.random() < sample_rate:
                call_llm = True
            else:
                call_llm = False
                filtered_due_to_ncs = True
        # if mode == 'off', do nothing (allow LLM if other conditions permit)

    analysis: Dict = {
        "explicit_skills": explicit,
        "skills_found": list(explicit),
        "core_logic": None,
        "domain_context": None,
        "latent_skills": [],
        "job_nature": None,
        "complexity": None,
        "skills_additional": [],
        "method": "regex",
        "model": None,
        "tokens": 0,
        "cost": 0.0,
        "analyzed_at": datetime.datetime.utcnow().isoformat() + "Z",
    }

    if call_llm:
        parsed, tokens_used, cost = _call_llm_for_dna(trimmed, explicit, domain_hint=ncs_text if ncs_text else None)
        if parsed:
            # merge parsed fields
            analysis["core_logic"] = parsed.get("core_logic")
            analysis["domain_context"] = parsed.get("domain_context")
            analysis["latent_skills"] = parsed.get("latent_skills") or []
            analysis["job_nature"] = parsed.get("job_nature")
            analysis["complexity"] = parsed.get("complexity")
            analysis["skills_additional"] = parsed.get("skills_additional") or []
            # merge skills
            combined = list(dict.fromkeys(list(explicit) + list(analysis["skills_additional"]) + list(analysis["latent_skills"])))
            analysis["skills_found"] = combined
            analysis["method"] = "regex+llm"
            analysis["model"] = parsed.get("model") if isinstance(parsed, dict) and parsed.get("model") else (getattr(config, "NVIDIA_MODEL", None) if provider == "nvidia" else getattr(config, "ANALYSIS_MODEL", None))
            analysis["tokens"] = tokens_used
            analysis["cost"] = cost
        else:
            # fallback heuristic
            h = _heuristic_analysis(trimmed, explicit)
            analysis.update(h)
            analysis["method"] = "regex+heuristic"
    else:
        h = _heuristic_analysis(trimmed, explicit)
        analysis.update(h)
        analysis["method"] = "regex+heuristic"

    # If this job was filtered by NCS rules (hard or sampled-soft), set safe defaults
    if filtered_due_to_ncs:
        analysis["core_logic"] = "일반 직무"
        analysis["domain_context"] = ncs_text or analysis.get("domain_context")
        analysis["latent_skills"] = []
        analysis["skills_additional"] = []
        analysis["method"] = "filtered_ncs"
        analysis["complexity"] = analysis.get("complexity") or "low"
        if not analysis.get("job_nature"):
            analysis["job_nature"] = "실무/혼합"

    # save analysis into json archive if alio_id provided
    try:
        if alio_id:
            # try to save the full job raw if present in job param
            job_raw = job.get("raw") if isinstance(job, dict) else None
            # if job is a full job dict, include it
            if isinstance(job, dict) and job.get("raw") is None:
                job_raw = job
            save_json_archive(job_raw or {}, alio_id, base_dir=base_dir, raw_dir=raw_dir)
            # now write analysis inside archive file
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
            # update index
            update_index_entry(alio_id, content_hash=content_hash, last_analyzed_at=analysis.get("analyzed_at"), base_dir=base_dir, raw_dir=raw_dir)
    except Exception:
        pass

    return analysis


if __name__ == "__main__":
    sample = "<p>아두이노 및 센서 연동, 시리얼 통신, PLC 인터페이스 요구</p>"
    print(extract_skills_and_reasoning(sample, ["아두이노", "공장 게임", "자동화 로직"]))
