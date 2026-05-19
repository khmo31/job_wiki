#!/usr/bin/env python3
"""job_raw Harvester — 순수 수집.

job_raw는 더 이상 분석(LLM/Ontology)을 수행하지 않습니다.
ALIO API에서 공고를 가져와 원본 그대로 저장합니다.
분석은 job_core/에서 별도 실행됩니다.
"""
import sys, os, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import argparse
import json
import datetime
from typing import Dict

import config
from fetcher import fetch_recent_jobs, fetch_detail_by_id, _parse_date, trim_for_analysis
from formatter import render_markdown
from writer import ensure_dirs, save_markdown, save_json_archive, exists_for_id
from utils import filename_from_job, extract_alio_id


def _save_raw_archive(job: Dict, alio_id: str) -> None:
    """Save raw job data to json_archive."""
    job_raw = job.get("raw") if isinstance(job, dict) else None
    save_json_archive(job_raw or job, alio_id,
                      base_dir=str(config.BASE_DIR), raw_dir=config.RAW_DIR)


def main(mock: bool = True, dry_run: bool = False, count: int | None = None,
         days: int = 7, max_pages: int | None = None) -> Dict:
    jobs = fetch_recent_jobs(api_key=config.ALIO_API_KEY, days=days, mock=mock,
                             max_pages=max_pages)

    if count:
        jobs = jobs[:count]

    stats = {"attempted": 0, "saved": 0, "skipped": 0, "errors": 0,
             "saved_files": [], "detail_calls": 0}
    detail_calls = 0

    for job in jobs:
        stats["attempted"] += 1
        try:
            alio_id = extract_alio_id(job)

            # Decide whether to fetch detail
            need_detail = False
            posted_raw = job.get("posted_date") or ""
            posted_date = _parse_date(posted_raw)
            if posted_date:
                cutoff = datetime.date.today() - datetime.timedelta(days=config.DETAIL_FETCH_WINDOW_DAYS)
                if posted_date >= cutoff:
                    need_detail = True

            if config.DETAIL_MAX_DETAIL_CALLS is not None and detail_calls >= config.DETAIL_MAX_DETAIL_CALLS:
                need_detail = False

            # Skip if already exists
            if alio_id and exists_for_id(alio_id, base_dir=str(config.BASE_DIR), raw_dir=config.RAW_DIR):
                stats["skipped"] += 1
                continue

            # Fetch detail if needed
            if need_detail and alio_id:
                detail = fetch_detail_by_id(alio_id, api_key=config.ALIO_API_KEY, mock=mock)
                if detail:
                    detail_calls += 1
                    stats["detail_calls"] = detail_calls
                    job["description"] = detail.get("description") or job.get("description")
                    job["requirements"] = detail.get("requirements") or job.get("requirements")
                    job["ncs_nm"] = job.get("ncs_nm") or detail.get("ncs_nm")
                    job_raw_list = job.get("raw") or {}
                    job["raw"] = {"list": job_raw_list, "detail": detail.get("raw")}

            # ── Save raw archive + markdown (NO analysis) ──
            _save_raw_archive(job, alio_id)
            md = render_markdown(job)
            filename = filename_from_job(job)

            if dry_run:
                print(f"[DRY RUN] would write: {os.path.join(config.RAW_DIR, filename)} "
                      f"(ALIO_ID={alio_id})", file=sys.stderr)
            else:
                path = save_markdown(md, base_dir=str(config.BASE_DIR), filename=filename,
                                     alio_id=alio_id, job_raw=job.get("raw"))
                if path:
                    stats["saved"] += 1
                    stats["saved_files"].append(path)
                else:
                    stats["skipped"] += 1

        except Exception as e:
            stats["errors"] += 1
            print(f"[harvester] error on job #{stats['attempted']}: {e}", file=sys.stderr)

    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="job_raw Harvester — 순수 수집")
    parser.add_argument("--no-mock", dest="mock", action="store_false",
                        help="disable mock data", default=True)
    parser.add_argument("--dry-run", action="store_true",
                        help="do not write files", default=False)
    parser.add_argument("--count", type=int, default=None,
                        help="max jobs to process")
    parser.add_argument("--days", type=int, default=7,
                        help="fetch postings from the last N days")
    parser.add_argument("--pages", type=int, default=None,
                        help="max API pages (default: 1, each page = 50 items)")
    args = parser.parse_args()

    summary = main(mock=args.mock, dry_run=args.dry_run, count=args.count,
                   days=args.days, max_pages=args.pages)

    attempted = summary.get("attempted", 0)
    saved = summary.get("saved", 0)
    skipped = summary.get("skipped", 0)
    errors = summary.get("errors", 0)
    detail = summary.get("detail_calls", 0)

    print("--- Report ---")
    print(f"Attempted: {attempted}")
    print(f"New saved: {saved}")
    print(f"Skipped (dup): {skipped}")
    print(f"Errors: {errors}")
    print(f"Detail calls: {detail}")
