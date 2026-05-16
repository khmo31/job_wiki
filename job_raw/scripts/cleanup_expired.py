#!/usr/bin/env python3
"""기한이 지난 채용공고 자동 정리

GitHub Actions에서 수집 Step 이전에 실행.
index.json + json_archive에서 pbancEndYmd 확인 후 만료된 항목 정리:
- 00_Raw/ 마크다운 파일 삭제
- json_archive/ 삭제
- index.json에서 제거
- 10_Wiki/Analysis/ 분석 페이지 삭제
- Wiki_Index.json에서 제거
- Company 프로필에서 링크 제거
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_ROOT = PROJECT_ROOT / "job_raw" / "00_Raw"
RAW_INDEX_PATH = RAW_ROOT / "index.json"
JSON_ARCHIVE_DIR = RAW_ROOT / "json_archive"
WIKI_ANALYSIS_DIR = PROJECT_ROOT / "job_wiki" / "10_Wiki" / "Analysis"
WIKI_COMPANIES_DIR = PROJECT_ROOT / "job_wiki" / "10_Wiki" / "Entities" / "Companies"
WIKI_META_DIR = PROJECT_ROOT / "job_wiki" / "20_Meta"
WIKI_INDEX_PATH = WIKI_META_DIR / "Wiki_Index.json"


def _log(msg: str) -> None:
    print(f"[cleanup_expired] {msg}", file=sys.stderr)


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        _log(f"failed to load {path.name}: {e}")
        return None


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _parse_date_str(date_str: str) -> date | None:
    """Parse YYYYMMDD or YYYY-MM-DD format date."""
    if not date_str:
        return None
    cleaned = date_str.strip().replace("-", "")
    if len(cleaned) != 8 or not cleaned.isdigit():
        return None
    try:
        return date(int(cleaned[:4]), int(cleaned[4:6]), int(cleaned[6:8]))
    except (ValueError, IndexError):
        return None


def _read_archive(alio_id: str) -> dict | None:
    """Read json_archive entry for an alio_id."""
    archive_path = JSON_ARCHIVE_DIR / f"{alio_id}.json"
    return _load_json(archive_path)


def _get_recrut_pblnt_sn(archive: dict) -> str | None:
    """Extract recrutPblntSn from archive raw data."""
    raw = archive.get("raw", {}) if archive else {}
    if not isinstance(raw, dict):
        return None
    sn = raw.get("recrutPblntSn") or raw.get("recrutPblntSn", "")
    if sn:
        return str(sn)
    return None


def _get_close_date(archive: dict) -> date | None:
    """Extract pbancEndYmd (closing date) from archive raw data."""
    raw = archive.get("raw", {}) if archive else {}
    if not isinstance(raw, dict):
        return None
    end_ymd = raw.get("pbancEndYmd", "")
    return _parse_date_str(end_ymd)


def _get_company_name(archive: dict) -> str:
    raw = archive.get("raw", {}) if archive else {}
    if isinstance(raw, dict):
        return raw.get("instNm", raw.get("company", "")) or ""
    return ""


def _find_wiki_analysis_file(recrut_sn: str) -> str | None:
    """Find the wiki analysis filename by recrutPblntSn.

    Search in Wiki_Index.json entries for the matching SN.
    """
    wiki_index = _load_json(WIKI_INDEX_PATH)
    if not wiki_index or not isinstance(wiki_index, dict):
        return None
    entries = wiki_index.get("entries", {})
    if not isinstance(entries, dict):
        return None

    for filename, entry_data in entries.items():
        # Check if filename contains the SN
        if recrut_sn in filename:
            return filename
        # Also check in entry data fields
        if isinstance(entry_data, dict):
            title = str(entry_data.get("title", ""))
            if recrut_sn in title:
                return filename
    return None


def _find_wiki_files_by_alio_id(alio_id: str, company: str) -> list[str]:
    """Find wiki analysis files by matching alio_id from the analysis frontmatter.

    Falls back to searching Wiki_Index or scanning analysis directory.
    """
    # First try: search in analysis file frontmatter for ALIO_{sn}
    recrut_sn = None
    archive = _read_archive(alio_id)
    if archive:
        recrut_sn = _get_recrut_pblnt_sn(archive)

    if recrut_sn:
        file_match = _find_wiki_analysis_file(recrut_sn)
        if file_match:
            return [file_match]

    # Second try: scan Analysis directory for files containing company name + alio_id components
    results = []
    company_clean = re.sub(r"[^가-힣A-Za-z0-9]", "", company) if company else ""
    alio_slug = alio_id.replace("-", "_")

    if WIKI_ANALYSIS_DIR.exists():
        for f in WIKI_ANALYSIS_DIR.iterdir():
            if f.is_file() and f.suffix == ".md":
                if company_clean and company_clean in f.stem:
                    results.append(f.name)
                elif alio_slug and alio_slug in f.stem:
                    results.append(f.name)

    return results


def _remove_from_company_profile(analysis_filename: str) -> None:
    """Remove a specific analysis file reference from company profiles."""
    if not WIKI_COMPANIES_DIR.exists():
        return

    link_pattern = re.compile(
        r'\[\[10_Wiki/Analysis/' + re.escape(analysis_filename) + r'\]\]'
    )

    for company_file in WIKI_COMPANIES_DIR.iterdir():
        if not company_file.is_file() or company_file.suffix != ".md":
            continue

        try:
            content = company_file.read_text(encoding="utf-8")
            if not link_pattern.search(content):
                continue

            # Remove the specific wiki link
            new_content = link_pattern.sub("", content)

            # Clean up: remove empty list contexts or trailing commas
            # Pattern: "관련 공고: ..." line cleanup
            new_content = re.sub(
                r'(관련 공고|참조 Analysis|관련 분석):\s*,?\s*\n',
                '', new_content
            )
            # Remove orphaned comma-space sequences from remaining lists
            new_content = re.sub(r',\s*,', ',', new_content)
            new_content = re.sub(r',\s*\n', '\n', new_content)
            new_content = re.sub(r'^\s*-\s*\n', '', new_content, flags=re.MULTILINE)

            # If company file is now empty (or only has header), remove it
            stripped = new_content.strip()
            if not stripped or len(stripped) < 20:
                company_file.unlink()
                _log(f"removed empty company profile: {company_file.name}")
            else:
                company_file.write_text(new_content, encoding="utf-8")
                _log(f"updated company profile: {company_file.name} (removed {analysis_filename})")

        except Exception as e:
            _log(f"error updating company profile {company_file.name}: {e}")


def cleanup_single(alio_id: str, index_entry: dict[str, Any]) -> dict[str, Any]:
    """Clean up a single expired job posting. Returns result stats."""
    result = {
        "alio_id": alio_id,
        "removed_raw": False,
        "removed_archive": False,
        "marked_expired_in_index": False,
        "removed_wiki": False,
        "removed_from_wiki_index": False,
        "removed_from_company": False,
        "errors": [],
    }

    filename = index_entry.get("filename", "") if isinstance(index_entry, dict) else str(index_entry) if isinstance(index_entry, str) else ""

    # 1. Delete raw markdown file
    if filename:
        raw_path = RAW_ROOT / filename
        try:
            if raw_path.exists():
                raw_path.unlink()
                result["removed_raw"] = True
                _log(f"deleted: 00_Raw/{filename}")
        except Exception as e:
            result["errors"].append(f"raw file: {e}")

    # 2. Delete json_archive
    archive_path = JSON_ARCHIVE_DIR / f"{alio_id}.json"
    try:
        if archive_path.exists():
            archive_path.unlink()
            result["removed_archive"] = True
            _log(f"deleted: json_archive/{alio_id}.json")
    except Exception as e:
        result["errors"].append(f"archive: {e}")

    # 3. Mark as expired in index (keep entry to prevent re-import)
    try:
        index = _load_json(RAW_INDEX_PATH)
        if index and isinstance(index, dict) and alio_id in index:
            entry = index[alio_id]
            if isinstance(entry, dict):
                entry["expired"] = True
            else:
                index[alio_id] = {"filename": entry if isinstance(entry, str) else "", "expired": True}
            _save_json(RAW_INDEX_PATH, index)
            result["marked_expired_in_index"] = True
    except Exception as e:
        result["errors"].append(f"index: {e}")

    # 4. Find and delete wiki analysis files
    company = ""
    archive_data = _read_archive(alio_id)
    if archive_data:
        company = _get_company_name(archive_data)

    wiki_files = _find_wiki_files_by_alio_id(alio_id, company)
    for wf in wiki_files:
        try:
            wf_path = WIKI_ANALYSIS_DIR / wf
            if wf_path.exists():
                wf_path.unlink()
                result["removed_wiki"] = True
                result["_removed_wiki_file"] = wf
                _log(f"deleted: wiki Analysis/{wf}")
        except Exception as e:
            result["errors"].append(f"wiki file {wf}: {e}")

        # 5. Remove from Wiki_Index.json
        try:
            wiki_index = _load_json(WIKI_INDEX_PATH)
            if wiki_index and isinstance(wiki_index, dict):
                entries = wiki_index.get("entries", {})
                if isinstance(entries, dict) and wf in entries:
                    del entries[wf]
                    wiki_index["entries"] = entries
                    _save_json(WIKI_INDEX_PATH, wiki_index)
                    result["removed_from_wiki_index"] = True
        except Exception as e:
            result["errors"].append(f"wiki index: {e}")

        # 6. Remove link from company profile
        try:
            _remove_from_company_profile(wf)
            result["removed_from_company"] = True
        except Exception as e:
            result["errors"].append(f"company profile: {e}")

    return result


def main() -> int:
    today = date.today()
    _log(f"cleanup run: today={today.isoformat()}")

    # Load index
    index = _load_json(RAW_INDEX_PATH)
    if not index or not isinstance(index, dict):
        _log("no index.json found or empty — nothing to clean")
        return 0

    total = 0
    expired = 0
    errors = 0
    expired_ids: list[str] = []

    # First pass: identify expired entries
    for alio_id, entry in index.items():
        total += 1
        archive = _read_archive(alio_id)
        close_date = _get_close_date(archive) if archive else None

        if close_date is None:
            # No close date — skip (can't determine expiry)
            continue

        if close_date < today:
            expired_ids.append(alio_id)
            _log(f"expired: {alio_id} (closed: {close_date.isoformat()})")

    # Second pass: clean up expired entries
    for alio_id in expired_ids:
        entry = index.get(alio_id, {})
        if isinstance(entry, str):
            entry = {"filename": entry}
        result = cleanup_single(alio_id, entry)
        expired += 1
        if result["errors"]:
            errors += 1
            for err in result["errors"]:
                _log(f"  error [{alio_id}]: {err}")

    _log(f"cleanup complete: {total} checked, {expired} expired, {errors} errors")
    return 0


if __name__ == "__main__":
    sys.exit(main())
