import os
import json
from typing import Optional
import config
import datetime
import hashlib


def ensure_dirs(base_dir: str = ".", raw_dir: str = "00_Raw") -> str:
    path = os.path.join(base_dir, raw_dir)
    os.makedirs(path, exist_ok=True)
    json_dir = os.path.join(path, config.JSON_ARCHIVE_DIR)
    os.makedirs(json_dir, exist_ok=True)
    # ensure index file exists
    index_path = os.path.join(path, config.INDEX_FILE)
    if not os.path.exists(index_path):
        with open(index_path, "w", encoding="utf-8") as fh:
            json.dump({}, fh, ensure_ascii=False, indent=2)
    return path


def _index_path(base_dir: str = ".", raw_dir: str = "00_Raw") -> str:
    return os.path.join(base_dir, raw_dir, config.INDEX_FILE)


def load_index(base_dir: str = ".", raw_dir: str = "00_Raw") -> dict:
    ensure_dirs(base_dir=base_dir, raw_dir=raw_dir)
    p = _index_path(base_dir, raw_dir)
    try:
        with open(p, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def save_index(index: dict, base_dir: str = ".", raw_dir: str = "00_Raw") -> None:
    p = _index_path(base_dir, raw_dir)
    with open(p, "w", encoding="utf-8") as fh:
        json.dump(index, fh, ensure_ascii=False, indent=2)


def exists_for_id(alio_id: str, base_dir: str = ".", raw_dir: str = "00_Raw") -> bool:
    if not alio_id:
        return False
    idx = load_index(base_dir, raw_dir)
    return alio_id in idx


def save_json_archive(job_raw: dict, alio_id: str, base_dir: str = ".", raw_dir: str = "00_Raw") -> str:
    ensure_dirs(base_dir=base_dir, raw_dir=raw_dir)
    path = os.path.join(base_dir, raw_dir, config.JSON_ARCHIVE_DIR, f"{alio_id}.json")
    try:
        # allow job_raw to be merged with existing archive if any
        content = {"raw": job_raw}
        # if existing file contains analysis, preserve it unless job_raw contains analysis
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as fh:
                    old = json.load(fh)
                # merge old analysis if present and job_raw does not provide it
                if "analysis" in old and "analysis" not in job_raw:
                    content["analysis"] = old.get("analysis")
        except Exception:
            pass

        # if job_raw already contains 'analysis' key, include it
        if isinstance(job_raw, dict) and "analysis" in job_raw:
            content["analysis"] = job_raw.get("analysis")

        # write merged archive
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(content, fh, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return path


def update_index_entry(alio_id: str, filename: Optional[str] = None, content_hash: Optional[str] = None, last_analyzed_at: Optional[str] = None, base_dir: str = ".", raw_dir: str = "00_Raw") -> None:
    """Create or update index entry for a given ALIO id.

    The index entry will be a dict like:
      { filename: str, content_hash: str, last_analyzed_at: isoformat }
    Older code that expects a filename string will still work since we keep the 'filename' key.
    """
    idx = load_index(base_dir=base_dir, raw_dir=raw_dir)
    entry = idx.get(alio_id)
    if isinstance(entry, str) or entry is None:
        entry = {"filename": entry if isinstance(entry, str) else (filename or "")}
    # update provided fields
    if filename:
        entry["filename"] = filename
    if content_hash:
        entry["content_hash"] = content_hash
    if last_analyzed_at:
        entry["last_analyzed_at"] = last_analyzed_at
    idx[alio_id] = entry
    save_index(idx, base_dir=base_dir, raw_dir=raw_dir)


def get_index_entry(alio_id: str, base_dir: str = ".", raw_dir: str = "00_Raw") -> Optional[dict]:
    idx = load_index(base_dir=base_dir, raw_dir=raw_dir)
    return idx.get(alio_id)


def save_markdown(content: str, base_dir: str = ".", filename: str = "untitled.md", alio_id: Optional[str] = None, job_raw: Optional[dict] = None) -> Optional[str]:
    raw_dir = ensure_dirs(base_dir=base_dir)
    path = os.path.join(raw_dir, filename)
    # Skip if the actual file already exists on disk (dedup by filename, not by index)
    if os.path.exists(path):
        return None

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    # save raw json archive and update index (filename + content_hash)
    if alio_id and job_raw is not None:
        save_json_archive(job_raw, alio_id, base_dir, raw_dir)
        update_index_entry(alio_id, filename=filename, base_dir=base_dir, raw_dir=raw_dir)

    return path
