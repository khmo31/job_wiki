#!/usr/bin/env python3
import sys, os, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import json
import time
import datetime
import hashlib

import config
from fetcher import fetch_recent_jobs, trim_for_analysis
from analyzer import analyze_objective_dna
from formatter import render_markdown
from writer import save_json_archive, update_index_entry, ensure_dirs
from utils import filename_from_job, extract_alio_id, slugify_segment


def main(target: int | None = None, page_size: int = 100, max_pages: int = 5):
    base_dir = str(config.BASE_DIR)
    raw_dir = config.RAW_DIR
    out_dir = os.path.join(base_dir, raw_dir)
    ensure_dirs(base_dir=base_dir, raw_dir=raw_dir)

    # Resolve target from argument -> config -> environment -> default 20
    if target is None:
        try:
            target = int(os.getenv("REANALYZE_TARGET", getattr(config, "REANALYZE_TARGET", 20)))
        except Exception:
            target = getattr(config, "REANALYZE_TARGET", 20)

    print('ALIO_API_KEY present?', bool(os.getenv('ALIO_API_KEY')))
    print('NVIDIA_API_KEY present?', bool(os.getenv('NVIDIA_API_KEY')))
    print('NVIDIA_BASE_URL:', os.getenv('NVIDIA_BASE_URL') or config.NVIDIA_BASE_URL)
    print('NVIDIA_MODEL:', os.getenv('NVIDIA_MODEL') or config.NVIDIA_MODEL)
    print('LLM_TIMEOUT used:', config.LLM_TIMEOUT)

    try:
        jobs = fetch_recent_jobs(api_key=config.ALIO_API_KEY, days=7, mock=False, page_size=page_size, max_pages=max_pages)
        print('Fetched', len(jobs), 'candidate jobs from ALIO')
    except Exception as e:
        print('Error fetching jobs:', e)
        return

    processed = 0
    report_entries = []

    for job in jobs:
        if processed >= target:
            break
        aid = extract_alio_id(job) or f'force-{processed+1}'
        trimmed = trim_for_analysis(job)
        print(f'Processing {aid} trimmed_len={len(trimmed)}')
        try:
            analysis = analyze_objective_dna(job, trimmed, alio_id=aid, force_llm=True, base_dir=base_dir, raw_dir=raw_dir)
            skills = analysis.get('skills_found') or []
            reasoning = {s: '공고에서 명시적 또는 추론적으로 관찰됨' for s in skills}
            md = render_markdown(job, skills, reasoning, analysis=analysis)
            filename = filename_from_job(job)
            # ensure filename includes alio id (aid may be forced when extract_alio_id returns empty)
            try:
                aid_clean = slugify_segment(aid) if aid else ""
            except Exception:
                aid_clean = ""
            if aid_clean and aid_clean not in filename:
                filename = filename.replace('.md', f'_{aid_clean}.md')
            path = os.path.join(out_dir, filename)
            with open(path, 'w', encoding='utf-8') as fh:
                fh.write(md)

            # save raw/archive and update index
            save_json_archive(job.get('raw') or job, aid, base_dir=base_dir, raw_dir=raw_dir)
            content_hash = hashlib.sha256((trimmed or '').encode('utf-8')).hexdigest()
            update_index_entry(aid, filename=filename, content_hash=content_hash, last_analyzed_at=analysis.get('analyzed_at'), base_dir=base_dir, raw_dir=raw_dir)

            report_entries.append({'alio_id': aid, 'title': job.get('title'), 'core_logic': analysis.get('core_logic'), 'tokens': analysis.get('tokens', 0), 'cost': analysis.get('cost', 0.0), 'method': analysis.get('method')})
            processed += 1
            print('  saved:', path, 'core_logic:', analysis.get('core_logic'))
        except Exception as e:
            print('  error on', aid, e)

    # Save run report
    fname = os.path.join(out_dir, 'analysis_run_nvidia_20_v2.json')
    report = {
        'timestamp': datetime.datetime.utcnow().isoformat() + 'Z',
        'provider': 'nvidia',
        'model': os.getenv('NVIDIA_MODEL'),
        'processed': processed,
        'entries': report_entries,
    }
    with open(fname, 'w', encoding='utf-8') as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    # compute distribution
    from collections import Counter

    cores = [e.get('core_logic') or 'NONE' for e in report_entries]
    dist = Counter(cores)
    print('\nProcessed', processed, 'entries')
    print('Distribution:')
    for k, v in dist.items():
        print(' -', k, v)
    print('\nSaved run report to', fname)


if __name__ == '__main__':
    main()
