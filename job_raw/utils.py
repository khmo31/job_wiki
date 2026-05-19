import re
import unicodedata
import hashlib
from datetime import datetime


def slugify_segment(text: str) -> str:
    if not text:
        return ""
    # Normalize and remove problematic filename characters
    text = text.strip()
    # Remove control chars and forbidden Windows chars <>:"/\|?*
    text = re.sub(r'[<>:"/\\|?*]+', '', text)
    text = re.sub(r"\s+", "_", text)
    return text


def _raw_list(raw: dict | None) -> dict:
    """Extract the list sub-dict from a raw dict (supports nested raw.list format)."""
    if raw and isinstance(raw, dict):
        lst = raw.get("list")
        if isinstance(lst, dict):
            return lst
    return {}


def filename_from_job(job: dict) -> str:
    # Prefer posted_date or date fields, otherwise use today
    date = job.get("posted_date") or job.get("date") or None
    # If nested raw contains pbancBgngYmd, prefer that
    raw = job.get("raw") if isinstance(job, dict) else None
    raw_list = _raw_list(raw)
    if not date and raw:
        date = raw_list.get("pbancBgngYmd") or raw.get("pbancBgngYmd")
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")
    date_key = str(date).replace("-", "")

    # Prefer institution name from raw (instNm) then fallback to company/title fields
    company = "unknown"
    try:
        if raw_list and raw_list.get("instNm"):
            company = raw_list.get("instNm")
        elif raw and raw.get("instNm"):
            company = raw.get("instNm")
        else:
            company = job.get("company") or job.get("instNm") or "unknown"
    except Exception:
        company = job.get("company") or "unknown"

    # Prefer recruitment publication title if present
    title = "untitled"
    try:
        if raw_list and raw_list.get("recrutPbancTtl"):
            title = raw_list.get("recrutPbancTtl")
        elif raw and raw.get("recrutPbancTtl"):
            title = raw.get("recrutPbancTtl")
        else:
            title = job.get("title") or job.get("recrutPbancTtl") or "untitled"
    except Exception:
        title = job.get("title") or "untitled"

    company = slugify_segment(company)
    title = slugify_segment(title)

    # include ALIO id (or deterministic fallback) to ensure uniqueness
    try:
        alio_id = extract_alio_id(job) or ""
    except Exception:
        alio_id = ""
    if not alio_id:
        # deterministic short id from company+title+date to avoid collisions
        source = f"{company}_{title}_{date_key}"
        alio_id = hashlib.sha256(source.encode("utf-8")).hexdigest()[:8]
    alio_id = slugify_segment(alio_id)
    filename = f"{date_key}_{alio_id}_{company}_{title}.md"
    return filename


def extract_alio_id(job: dict) -> str:
    # Prefer explicit id field
    if job.get("id"):
        return str(job.get("id"))
    raw = job.get("raw") or {}
    if isinstance(raw, dict):
        # Check raw.list first (ALIO API nested format)
        raw_list_src = raw.get("list", {})
        if isinstance(raw_list_src, dict):
            for k in ("recrutPblntSn", "id", "idx", "postNo", "noticeNo", "jobId", "recruitmentNo", "postId"):
                if k in raw_list_src and raw_list_src[k]:
                    return str(raw_list_src[k])
        # Fallback to raw top-level
        for k in ("id", "idx", "postNo", "noticeNo", "jobId", "recruitmentNo", "postId"):
            if k in raw and raw[k]:
                return str(raw[k])
    return ""


def shorten(text: str, n: int = 300) -> str:
    if not text:
        return ""
    return text if len(text) <= n else text[:n].rstrip() + "..."
