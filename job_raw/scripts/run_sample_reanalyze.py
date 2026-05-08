#!/usr/bin/env python3
import sys, os, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import json
import datetime
import config
from fetcher import trim_for_analysis
from analyzer import analyze_objective_dna

BASE_DIR = str(config.BASE_DIR)
RAW_DIR = os.path.join(BASE_DIR, config.RAW_DIR)
ARCHIVE_DIR = os.path.join(RAW_DIR, 'json_archive')

alio_ids = ['force-1', 'force-2', 'force-16']
report = {'timestamp': datetime.datetime.utcnow().isoformat() + 'Z', 'entries': []}

for aid in alio_ids:
    path = os.path.join(ARCHIVE_DIR, f"{aid}.json")
    if not os.path.exists(path):
        print('Missing archive for', aid)
        continue
    with open(path, 'r', encoding='utf-8') as fh:
        data = json.load(fh) or {}
    job_raw = data.get('raw') or {}
    job = {
        'id': aid,
        'title': job_raw.get('recrutPbancTtl') or job_raw.get('title') or job_raw.get('recrutSeNm') or '',
        'company': job_raw.get('instNm') or job_raw.get('company') or '',
        'posted_date': job_raw.get('pbancBgngYmd') or job_raw.get('posted_date') or '',
        'raw': job_raw,
    }

    # Force compose contextual payload (Title+기관+NCS+응시자격+우대사항)
    trimmed = trim_for_analysis(job, force_compose=True)
    print(f"\n--- Analyzing {aid} (trimmed_len={len(trimmed)}) ---")

    analysis = analyze_objective_dna(job, trimmed, alio_id=aid, force_llm=True, base_dir=BASE_DIR, raw_dir=config.RAW_DIR)
    report['entries'].append({'alio_id': aid, 'trimmed_len': len(trimmed), 'analysis': analysis})
    print(json.dumps(analysis, ensure_ascii=False, indent=2))

# save report
out = os.path.join(RAW_DIR, 'sample_analysis_3.json')
with open(out, 'w', encoding='utf-8') as fh:
    json.dump(report, fh, ensure_ascii=False, indent=2)
print('\nSaved sample report to', out)
