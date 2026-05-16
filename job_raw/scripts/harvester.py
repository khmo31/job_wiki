#!/usr/bin/env python3
import sys, os, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import argparse
import os
from typing import List, Dict, Optional
import datetime

import config
from fetcher import fetch_recent_jobs, fetch_detail_by_id, _parse_date, trim_for_analysis
from analyzer import extract_skills_and_reasoning, preprocess_text, analyze_objective_dna
from formatter import render_markdown
from writer import save_markdown, save_json_archive, exists_for_id
from utils import filename_from_job, extract_alio_id


def main(mock: bool = True, dry_run: bool = False, count: int | None = None, days: int = 7) -> Dict:
    jobs = fetch_recent_jobs(api_key=config.ALIO_API_KEY, days=days, mock=mock)
    if count:
        jobs = jobs[:count]

    stats = {"attempted": 0, "saved": 0, "skipped": 0, "errors": 0, "saved_files": [], "detail_calls": 0}
    stats["llm_analyzed"] = 0
    detail_calls = 0
    for job in jobs:
        stats["attempted"] += 1
        try:
            # Decide whether to fetch detail for this item
            alio_id = extract_alio_id(job)
            need_detail = False
            # recent window
            posted_raw = job.get("posted_date") or ""
            posted_date = _parse_date(posted_raw)
            if posted_date:
                cutoff = datetime.date.today() - datetime.timedelta(days=config.DETAIL_FETCH_WINDOW_DAYS)
                if posted_date >= cutoff:
                    need_detail = True
            # NCS or keywords
            if not need_detail:
                ncs = job.get("ncs_nm") or ""
                if ncs and any(k in ncs for k in config.NCS_MAP.keys()):
                    need_detail = True
            if not need_detail:
                # check title/description keywords
                text_for_kw = ((job.get("title", "") or "") + " \n " + (job.get("description", "") or "")).lower()
                if any(kw.lower() in text_for_kw for kw in config.DETAIL_KEYWORDS):
                    need_detail = True

            # enforce max detail calls
            if config.DETAIL_MAX_DETAIL_CALLS is not None and detail_calls >= config.DETAIL_MAX_DETAIL_CALLS:
                need_detail = False

            # === SKIP if already exists (BEFORE any analysis!) ===
            if alio_id and exists_for_id(alio_id, base_dir=str(config.BASE_DIR), raw_dir=config.RAW_DIR):
                stats["skipped"] += 1
                continue

            # fetch and merge detail if needed
            if need_detail and alio_id:
                detail = fetch_detail_by_id(alio_id, api_key=config.ALIO_API_KEY, mock=mock)
                if detail:
                    detail_calls += 1
                    stats["detail_calls"] = detail_calls
                    # merge critical fields
                    job["description"] = detail.get("description") or job.get("description")
                    job["requirements"] = detail.get("requirements") or job.get("requirements")
                    job["ncs_nm"] = job.get("ncs_nm") or detail.get("ncs_nm")
                    job_raw_list = job.get("raw") or {}
                    job["raw"] = {"list": job_raw_list, "detail": detail.get("raw")}

            # trim the job text to relevant sections for analysis (cost shield)
            trimmed = trim_for_analysis(job)
            # perform hybrid analysis (regex + optional LLM). This will update json archive and index.
            analysis = analyze_objective_dna(job, trimmed, alio_id=alio_id, base_dir=str(config.BASE_DIR), raw_dir=config.RAW_DIR)
            skills = analysis.get("skills_found") or []
            # build lightweight reasoning map (backwards-compatible)
            reasoning = {s: "공고에서 명시적 또는 추론적으로 관찰됨" for s in skills}
            md = render_markdown(job, skills, reasoning, analysis=analysis, interests=config.USER_INTERESTS)
            filename = filename_from_job(job)
            if dry_run:
                print(f"[DRY RUN] would write: {os.path.join(config.RAW_DIR, filename)} (ALIO_ID={alio_id})")
                print(repr(md[:200]))
                stats["saved" if False else "skipped"] += 0
            else:
                path = save_markdown(md, base_dir=str(config.BASE_DIR), filename=filename, alio_id=alio_id, job_raw=job.get("raw"))
                if path:
                    stats["saved"] += 1
                    stats["saved_files"].append(path)
                else:
                    stats["skipped"] += 1
            # track analysis cost (if produced)
            try:
                tok = int(analysis.get("tokens", 0)) if isinstance(analysis, dict) else 0
                cost = float(analysis.get("cost", 0.0)) if isinstance(analysis, dict) else 0.0
                stats.setdefault("tokens", 0)
                stats.setdefault("cost", 0.0)
                stats["tokens"] += tok
                stats["cost"] += cost
                if isinstance(analysis, dict) and analysis.get("method") == "regex+llm":
                    stats["llm_analyzed"] += 1
            except Exception:
                pass
        except Exception:
            stats["errors"] += 1
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="P-Reinforce Harvester batch runner")
    parser.add_argument("--no-mock", dest="mock", action="store_false", help="disable mock data", default=True)
    parser.add_argument("--dry-run", action="store_true", help="do not write files", default=False)
    parser.add_argument("--count", type=int, default=None)
    parser.add_argument("--days", type=int, default=7, help="fetch postings from the last N days")
    args = parser.parse_args()
    summary = main(mock=args.mock, dry_run=args.dry_run, count=args.count, days=args.days)
    attempted = summary.get("attempted", 0)
    saved = summary.get("saved", 0)
    skipped = summary.get("skipped", 0)
    errors = summary.get("errors", 0)
    print(f"Summary: attempted={attempted}, saved={saved}, skipped={skipped}, errors={errors}")
