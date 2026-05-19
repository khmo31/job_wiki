import sys
import time
import json
from typing import List, Dict, Optional
import datetime
import xml.etree.ElementTree as ET

import requests
import config


def _parse_xml_items(text: str) -> List[Dict]:
    items: List[Dict] = []
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return items
    # find all item elements (common in public APIs)
    for item in root.findall('.//item'):
        d: Dict = {}
        for child in item:
            d[child.tag] = child.text or ""
        items.append(d)
    return items


def _extract_items_from_json(obj: Dict) -> List[Dict]:
    # Try common wrapping patterns: response->body->items->item or response->items
    if not isinstance(obj, dict):
        return []
    candidates = []
    # search recursively for lists of dicts
    def walk(o):
        if isinstance(o, list) and o and isinstance(o[0], dict):
            candidates.append(o)
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)

    walk(obj)
    return candidates[0] if candidates else []


def _tag_value(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts = []
        for item in value:
            text = _tag_value(item)
            if text:
                parts.append(text)
        return ",".join(parts)
    if isinstance(value, dict):
        if not value:
            return ""
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        except Exception:
            return str(value)
    return str(value).strip()


def _extract_raw_tags(item: Dict) -> Dict[str, str]:
    tags: Dict[str, str] = {}
    for key, value in item.items():
        if key == "raw_tags":
            continue
        tag_value = _tag_value(value)
        if tag_value:
            tags[key] = tag_value
    return tags


def _normalize_item(item: Dict) -> Dict:
    # Map common possible keys to our schema
    def pick(*keys):
        for k in keys:
            if k in item and item[k]:
                return item[k]
        return ""

    title = pick("title", "post_title", "jobTitle", "recruitmentPostTitle", "recrutPbancTtl", "recrutSeNm", "recrutSj", "recruitTitle")
    company = pick("company", "insttNm", "corpNm", "agency", "insttNmKor", "orgNm", "instNm")
    posted = pick("posted_date", "postDate", "regDate", "recruitDate", "startDate", "postDt", "pbancBgngYmd")
    # ALIO API: aplyQlfcCn=응시자격, prefCondCn=우대사항, scrnprcdrMthdExpln=전형방법
    description = pick("description", "jobCont", "recruitmentContent", "jobContents", "mainDuty", "recruitCont", "cont", "aplyQlfcCn", "scrnprcdrMthdExpln")
    requirements = pick("requirements", "qualification", "req", "privilege", "preferentialTreatment", "requirements", "prefCondCn", "prefCn")
    hireTypeNmLst = pick("hireTypeNmLst")
    recrutSeNm = pick("recrutSeNm")
    acbgCondNmLst = pick("acbgCondNmLst")
    workRgnNmLst = pick("workRgnNmLst")
    prefCondCn = pick("prefCondCn")
    ncsCdNmLst = pick("ncsCdNmLst", "ncs_nm", "ncsNm", "ncs_name", "ncs")
    ncsCdLst = pick("ncsCdLst", "ncsCd", "ncsCode", "ncs_code")
    ncs_nm = ncsCdNmLst or ncsCdLst
    # use provided id or attempt common fields (v1 uses 'idx')
    alio_id = pick("id", "idx", "recruitmentNo", "postNo", "jobId", "num", "noticeNo", "recrutPblntSn")

    raw_tags = _extract_raw_tags(item)
    item["raw_tags"] = raw_tags

    return {
        "id": str(alio_id) if alio_id is not None else "",
        "title": title,
        "company": company,
        "posted_date": posted,
        "description": description,
        "requirements": requirements,
        "hireTypeNmLst": hireTypeNmLst,
        "recrutSeNm": recrutSeNm,
        "acbgCondNmLst": acbgCondNmLst,
        "workRgnNmLst": workRgnNmLst,
        "prefCondCn": prefCondCn,
        "ncs_nm": ncs_nm,
        "ncsCdNmLst": ncsCdNmLst,
        "ncsCdLst": ncsCdLst,
        "raw_tags": raw_tags,
        "raw": item,
    }


def _parse_date(text: str) -> Optional[datetime.date]:
    if not text:
        return None
    text = text.strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y.%m.%d", "%Y/%m/%d"):
        try:
            return datetime.datetime.strptime(text[:10], fmt).date()
        except Exception:
            continue
    # last resort: try to extract 8-digit
    import re

    m = re.search(r"(20\d{2})(\D?)(\d{1,2})\2(\d{1,2})", text)
    if m:
        try:
            y, mth, d = int(m.group(1)), int(m.group(3)), int(m.group(4))
            return datetime.date(y, mth, d)
        except Exception:
            return None
    return None


def fetch_recent_jobs(api_key: Optional[str] = None, days: int = 7, mock: bool = True, page_size: int | None = None, max_pages: int | None = None) -> List[Dict]:
    """Fetch recent job postings from ALIO (or return mock). Returns list of standardized job dicts.

    If `mock` is True, returns sample data. For real API calls, set config.ALIO_ENDPOINT and ALIO_API_KEY.
    """
    if mock:
        today = datetime.date.today()
        sample = [
            {
                "id": "ALIO-2026-0001",
                "title": "스마트팩토리 자동화 연구원(아두이노/임베디드)",
                "company": "국립자동화연구소",
                "posted_date": (today).strftime("%Y-%m-%d"),
                "description": "생산 라인 제어 및 센서 연동(아두이노). PLC 인터페이스, 시리얼 통신, 데이터 로깅, 자동화 알고리즘 설계 경험 우대.",
                "requirements": "C/C++, 아두이노, 시리얼 통신, 센서 신호 처리, Python 스크립트",
                "ncs_nm": "전기.전자",
                "ncsCdNmLst": "전기.전자",
                "raw": {"mock": True},
            },
            {
                "id": "ALIO-2026-0002",
                "title": "제조로봇 개발자(임베디드/제어)",
                "company": "한국산업기술원",
                "posted_date": (today - datetime.timedelta(days=1)).strftime("%Y-%m-%d"),
                "description": "로봇 제어, 센서 퓨전, 임베디드 소프트웨어(임베디드 C/C++), 자동화 로직 최적화, ROS 경험 우대.",
                "requirements": "임베디드 C, ROS, 제어이론, 센서퓨전",
                "ncs_nm": "정보통신",
                "ncsCdNmLst": "정보통신",
                "raw": {"mock": True},
            },
        ]
        # filter by days
        if days is not None:
            cutoff = datetime.date.today() - datetime.timedelta(days=days)
            filtered = []
            for j in sample:
                d = _parse_date(j.get("posted_date", ""))
                if not d or d >= cutoff:
                    filtered.append(j)
            return filtered
        return sample

    # Real API mode
    api_key = api_key or config.ALIO_API_KEY
    endpoint = config.ALIO_ENDPOINT
    if not api_key or not endpoint:
        raise RuntimeError("ALIO API mode requires ALIO_API_KEY and ALIO_ENDPOINT set in config or .env")

    page_size = page_size or config.ALIO_PAGE_SIZE
    max_pages = max_pages or config.ALIO_MAX_PAGES

    results: List[Dict] = []
    session = requests.Session()
    # apply default headers from config (User-Agent, Referer, Content-Type)
    headers = getattr(config, "ALIO_REQUEST_HEADERS", None) or {}
    if headers:
        session.headers.update(headers)
    for page in range(1, max_pages + 1):
        # try multiple API key parameter names if provided (some ALIO endpoints expect 'serviceKey')
        key_names = getattr(config, "ALIO_API_KEY_PARAM_NAMES", ["apikey", "serviceKey", "ServiceKey", "service_key"]) or ["apikey"]
        found_for_page = False
        for key_name in key_names:
            data = {key_name: api_key, "numOfRows": page_size, "pageNo": page}
            attempts = 0
            while attempts < config.RETRY_ATTEMPTS:
                print(f"[fetcher] page={page}/{max_pages} key={key_name} attempt={attempts+1}", file=sys.stderr)
                try:
                    mode = getattr(config, "ALIO_REQUEST_BODY_MODE", "data") or "data"
                    if mode == "json":
                        r = session.post(endpoint, json=data, timeout=15)
                    elif mode == "params":
                        r = session.post(endpoint, params=data, timeout=15)
                    else:
                        r = session.post(endpoint, data=data, timeout=15)

                    if r.status_code != 200:
                        attempts += 1
                        time.sleep((2 ** attempts) * config.RETRY_BACKOFF_FACTOR)
                        continue

                    # encoding fallback: let requests detect apparent encoding to avoid 한글 깨짐
                    try:
                        r.encoding = r.apparent_encoding or r.encoding
                    except Exception:
                        pass

                    # try JSON first (v1 returns JSON with 'list')
                    items = []
                    try:
                        obj = r.json()
                        if isinstance(obj, dict) and "list" in obj and isinstance(obj["list"], list):
                            items = obj["list"]
                        else:
                            items = _extract_items_from_json(obj)
                    except Exception:
                        items = _parse_xml_items(r.text)

                    if items:
                        for it in items:
                            results.append(_normalize_item(it))
                        found_for_page = True
                        print(f"[fetcher] page={page} OK ({len(items)} items, total={len(results)})", file=sys.stderr)

                        # if fewer items than page_size, finished
                        if len(items) < page_size:
                            print(f"[fetcher] last page reached ({len(items)} < {page_size}), stopping", file=sys.stderr)
                            return results
                        break
                    else:
                        print(f"[fetcher] page={page} key={key_name} got 200 but no items", file=sys.stderr)
                        # got 200 but no items -> try next key_name
                        break
                except requests.RequestException as e:
                    attempts += 1
                    print(f"[fetcher] page={page} key={key_name} attempt {attempts} failed: {e}", file=sys.stderr)
                    time.sleep((2 ** attempts) * config.RETRY_BACKOFF_FACTOR)
            if found_for_page:
                break
        if not found_for_page:
            # no key_name returned items for this page -> assume no more data or blocked
            return results

    return results


def fetch_detail_by_id(alio_id: str, api_key: Optional[str] = None, mock: bool = True, param_names: List[str] | None = None) -> Optional[Dict]:
    """Fetch detailed job info by ALIO posting id. Returns a normalized job dict or None.

    Tries multiple possible parameter names if provided or configured in `config.ALIO_DETAIL_PARAM_NAMES`.
    """
    if not alio_id:
        return None

    if mock:
        # simple mock detail
        today = datetime.date.today()
        detail = {
            "id": alio_id,
            "title": f"상세 {alio_id} 직무(예시)",
            "company": "모의기관",
            "posted_date": today.strftime("%Y-%m-%d"),
            "description": "상세 직무 기술서: 센서 연동, 제어 알고리즘, 시험 및 검증 포함.",
            "requirements": "상세 요구사항: 아두이노, C/C++, 시리얼 통신, 센서 데이터 처리",
            "ncs_nm": "전기.전자",
            "ncsCdNmLst": "전기.전자",
            "raw": {"mock_detail": True},
        }
        detail["raw_tags"] = _extract_raw_tags(detail)
        return detail

    api_key = api_key or config.ALIO_API_KEY
    endpoint = config.ALIO_DETAIL_ENDPOINT
    if not api_key or not endpoint:
        return None

    session = requests.Session()
    candidates = param_names or getattr(config, "ALIO_DETAIL_PARAM_NAMES", ["idx", "noticeNo", "recruitmentNo"]) or []
    # apply default headers for detail requests too
    headers = getattr(config, "ALIO_REQUEST_HEADERS", None) or {}
    if headers:
        session.headers.update(headers)
    for param in candidates:
        attempts = 0
        while attempts < config.RETRY_ATTEMPTS:
            try:
                # try multiple API key param names for detail as well
                key_names = getattr(config, "ALIO_API_KEY_PARAM_NAMES", ["apikey", "serviceKey", "ServiceKey", "service_key"]) or ["apikey"]
                for key_name in key_names:
                    data = {key_name: api_key, param: alio_id}
                    mode = getattr(config, "ALIO_REQUEST_BODY_MODE", "data") or "data"
                    if mode == "json":
                        r = session.post(endpoint, json=data, timeout=15)
                    elif mode == "params":
                        r = session.post(endpoint, params=data, timeout=15)
                    else:
                        r = session.post(endpoint, data=data, timeout=15)
                    if r.status_code != 200:
                        continue

                    # encoding fallback: set encoding from apparent_encoding to avoid 한글 깨짐
                    try:
                        r.encoding = r.apparent_encoding or r.encoding
                    except Exception:
                        pass

                    # try parse JSON
                    try:
                        obj = r.json()
                    except Exception:
                        obj = None

                    items = []
                    if isinstance(obj, dict):
                        # common patterns: detail may be top-level dict or under 'data'/'detail'/'list'
                        if "list" in obj and isinstance(obj["list"], list):
                            items = obj["list"]
                        elif "detail" in obj:
                            d = obj["detail"]
                            if isinstance(d, list):
                                items = d
                            elif isinstance(d, dict):
                                items = [d]
                        elif any(k in obj for k in ("data", "item", "result")):
                            for k in ("data", "item", "result"):
                                if k in obj:
                                    v = obj[k]
                                    if isinstance(v, list):
                                        items = v
                                    elif isinstance(v, dict):
                                        items = [v]
                                    break
                        else:
                            # maybe the obj itself is the detail dict
                            items = [obj]
                    else:
                        items = _parse_xml_items(r.text)

                    if items:
                        return _normalize_item(items[0])
                # tried all key_names for this param -> move to next candidate id param
                break
            except requests.RequestException:
                attempts += 1
                time.sleep((2 ** attempts) * config.RETRY_BACKOFF_FACTOR)
        # try next candidate param name
    return None


def trim_for_analysis(job: Dict, max_chars: int | None = None, force_compose: bool | None = None) -> str:
    """Extract the most relevant sections for LLM analysis: prioritize '직무수행내용' / '업무내용' and '우대사항' / '우대' from description/requirements.

    Returns a cleaned, truncated string suitable for sending to a low-cost LLM.
    """
    try:
        text_parts = []
        desc = (job.get("description") or "")
        req = (job.get("requirements") or "")
        combined = "\n".join([desc, req]).strip()

        # search for headings and capture following paragraph until next heading
        headings = [r"직무수행내용", r"주요업무", r"업무내용", r"직무내용", r"주요 업무", r"업무 및 역할"]
        prefer = []
        for h in headings:
            m = re.search(r"(?ms)" + re.escape(h) + r"\s*[:\-\n]+(.*?)(?=\n\s*(?:" + "|".join([re.escape(x) for x in headings + ["우대사항", "우대", "자격요건", "요구사항"]]) + r")\s*[:\-\n]+|\Z)", combined)
            if m:
                prefer.append(m.group(1).strip())

        # 우대사항 / 우대
        prefer2 = []
        m2 = re.search(r"(?ms)(우대사항|우대|우대 조건|우대요건)\s*[:\-\n]+(.*?)(?=\n\s*(?:" + "|".join([re.escape(x) for x in headings + ["자격요건", "요구사항", "모집요강"]]) + r")\s*[:\-\n]+|\Z)", combined)
        if m2:
            prefer2.append(m2.group(2).strip())

        # fallback: if prefer empty, try to extract sentences containing 흔한 키워드
        if not prefer and not prefer2:
            # try to capture sentences containing '주요', '담당', '우대', '요구', '필수'
            sents = re.split(r"(?<=[\.!?\n])\s+", combined)
            for s in sents:
                if re.search(r"\b(주요|담당|우대|요구|필수|경력|경험|책임)\b", s):
                    prefer.append(s.strip())

        pieces = []
        if prefer:
            pieces.extend(prefer)
        if prefer2:
            pieces.append("우대사항:\n" + "\n".join(prefer2))

        if not pieces:
            pieces = [combined]

        out = "\n\n".join([p for p in pieces if p])
        # remove common salutations or long non-informational blocks
        out = re.sub(r"(?is)(\b유의사항\b.*|\b안내\b.*|\b모집요강\b.*)", "", out)
        maxc = max_chars or getattr(config, "ANALYSIS_MAX_INPUT_CHARS", None) or 4000
        if len(out) > maxc:
            out = out[:maxc]
        # normalize whitespace
        out = re.sub(r"\s+", " ", out).strip()

        # Safety fallback / forced composition: always compose minimal context unless explicitly disabled.
        # This ensures the LLM always receives Title+기관+NCS+응시자격+우대사항 as context.
        min_chars = int(getattr(config, "ANALYSIS_MIN_INPUT_CHARS", 800))
        effective_force = force_compose if force_compose is not None else getattr(config, "FORCE_COMPOSE_CONTEXT", True)
        if effective_force or not out or len(out) < min_chars:
            title = (job.get("title") or "").strip()
            company = (job.get("company") or "").strip()
            ncs = (job.get("ncs_nm") or "").strip()
            # collect additional raw fields commonly present in ALIO payloads
            raw = job.get("raw") or {}
            aply = raw.get("aplyQlfcCn") or job.get("aplyQlfcCn") or ""
            prefcond = raw.get("prefCondCn") or raw.get("prefCn") or job.get("prefCondCn") or job.get("prefCn") or ""

            # Forced minimal composition: Title + Institution + NCS + 응시자격 + 우대사항
            inst = raw.get("instNm") or job.get("company") or ""
            composed_parts = []
            if title:
                composed_parts.append(f"공고제목: {title}")
            if inst:
                composed_parts.append(f"기관명: {inst}")
            if ncs:
                composed_parts.append(f"NCS: {ncs}")
            if aply:
                composed_parts.append(f"응시자격: {aply}")
            if prefcond:
                composed_parts.append(f"우대사항: {prefcond}")

            composed = "\n".join(composed_parts)

            # If we still have description/requirements, append them after the forced block
            if desc:
                composed = composed + "\n\nDescription: " + desc
            if req:
                composed = composed + "\n\nRequirements: " + req

            # prefer original extracted out if present and force_compose not requested; otherwise use composed
            if out and not force_compose:
                out = (out + "\n\nFallback Context:\n" + composed)[:maxc]
            else:
                out = composed[:maxc]

        return out
    except Exception:
        return (job.get("description") or "")[: (max_chars or getattr(config, "ANALYSIS_MAX_INPUT_CHARS", 4000))]

