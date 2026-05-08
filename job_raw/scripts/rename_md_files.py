#!/usr/bin/env python3
# Bulk rename existing markdown files in 00_Raw to the new filename format
# Usage: run from project root (job_raw) or run via `python scripts/rename_md_files.py`

import sys, os, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import json
import hashlib

from utils import filename_from_job
from pathlib import Path

BASE_DIR = str(Path(__file__).resolve().parent.parent)
RAW_DIR = os.path.join(BASE_DIR, "00_Raw")
ARCHIVE_DIR = os.path.join(RAW_DIR, "json_archive")
INDEX_PATH = os.path.join(RAW_DIR, "index.json")

if not os.path.isdir(RAW_DIR):
    print("00_Raw directory not found:", RAW_DIR)
    raise SystemExit(1)

if not os.path.isdir(ARCHIVE_DIR):
    print("json_archive directory not found, nothing to do.")
    raise SystemExit(0)

# load or initialize index
index = {}
if os.path.exists(INDEX_PATH):
    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as fh:
            index = json.load(fh) or {}
    except Exception as e:
        print("Warning: failed to read index.json:", e)
        index = {}

md_files = [f for f in os.listdir(RAW_DIR) if f.lower().endswith('.md')]
renamed = []
skipped = []
errors = []

for fname in sorted(os.listdir(ARCHIVE_DIR)):
    if not fname.lower().endswith('.json'):
        continue
    alio_id = fname[:-5]
    archive_path = os.path.join(ARCHIVE_DIR, fname)
    try:
        with open(archive_path, 'r', encoding='utf-8') as fh:
            data = json.load(fh) or {}
    except Exception as e:
        errors.append((alio_id, f"archive load error: {e}"))
        continue

    job_raw = data.get('raw') or {}
    job = {
        'id': alio_id,
        'title': job_raw.get('recrutPbancTtl') or job_raw.get('title') or job_raw.get('recruitTitle') or job_raw.get('recrutSeNm') or '',
        'company': job_raw.get('instNm') or job_raw.get('company') or job_raw.get('insttNm') or '',
        'posted_date': job_raw.get('pbancBgngYmd') or job_raw.get('posted_date') or job_raw.get('postDate') or '',
        'raw': job_raw,
    }

    try:
        new_name = filename_from_job(job)
    except Exception as e:
        errors.append((alio_id, f"filename_from_job error: {e}"))
        continue

    new_path = os.path.join(RAW_DIR, new_name)

    # find existing md file (prefer index mapping)
    old_name = None
    if alio_id in index:
        entry = index[alio_id]
        if isinstance(entry, str):
            cand = entry
        elif isinstance(entry, dict):
            cand = entry.get('filename')
        else:
            cand = None
        if cand:
            cand_path = os.path.join(RAW_DIR, cand)
            if os.path.exists(cand_path):
                old_name = cand

    # fallback: search by alio_id in filenames
    if not old_name:
        for m in md_files:
            if alio_id in m:
                old_name = m
                break

    # fallback: search by alio_id inside first 4KB of file content
    if not old_name:
        for m in md_files:
            p = os.path.join(RAW_DIR, m)
            try:
                with open(p, 'r', encoding='utf-8') as fh:
                    c = fh.read(4096)
                if alio_id in c:
                    old_name = m
                    break
            except Exception:
                continue

    if not old_name:
        skipped.append(alio_id)
        continue

    old_path = os.path.join(RAW_DIR, old_name)

    # if already correct
    if os.path.abspath(old_path) == os.path.abspath(new_path):
        # ensure index updated
        try:
            with open(old_path, 'rb') as fh:
                ch = hashlib.sha256(fh.read()).hexdigest()
            index[alio_id] = {'filename': new_name, 'content_hash': ch, 'last_analyzed_at': data.get('analysis', {}).get('analyzed_at')}
        except Exception:
            index[alio_id] = {'filename': new_name}
        continue

    # resolve collisions
    dest_path = new_path
    if os.path.exists(dest_path):
        try:
            with open(old_path, 'rb') as fh:
                oldb = fh.read()
            with open(dest_path, 'rb') as fh:
                newb = fh.read()
            if hashlib.sha256(oldb).hexdigest() == hashlib.sha256(newb).hexdigest():
                # duplicate content; remove old file
                os.remove(old_path)
                renamed.append((old_name, os.path.basename(dest_path), 'removed_duplicate'))
                index[alio_id] = {'filename': os.path.basename(dest_path), 'content_hash': hashlib.sha256(newb).hexdigest(), 'last_analyzed_at': data.get('analysis', {}).get('analyzed_at')}
                md_files = [f for f in os.listdir(RAW_DIR) if f.lower().endswith('.md')]
                continue
        except Exception:
            pass
        # otherwise find non-conflicting name
        base, ext = os.path.splitext(dest_path)
        i = 1
        candidate = f"{base}_dup{i}{ext}"
        while os.path.exists(candidate):
            i += 1
            candidate = f"{base}_dup{i}{ext}"
        dest_path = candidate

    try:
        os.rename(old_path, dest_path)
        with open(dest_path, 'rb') as fh:
            ch = hashlib.sha256(fh.read()).hexdigest()
        index[alio_id] = {'filename': os.path.basename(dest_path), 'content_hash': ch, 'last_analyzed_at': data.get('analysis', {}).get('analyzed_at')}
        renamed.append((old_name, os.path.basename(dest_path)))
        md_files = [f for f in os.listdir(RAW_DIR) if f.lower().endswith('.md')]
    except Exception as e:
        errors.append((alio_id, f"rename error: {e}"))

# write updated index.json
try:
    with open(INDEX_PATH, 'w', encoding='utf-8') as fh:
        json.dump(index, fh, ensure_ascii=False, indent=2)
except Exception as e:
    print('Failed to write index.json:', e)

print('--- Summary ---')
print('Renamed:', len(renamed))
for a in renamed:
    if len(a) == 3:
        print(f" - {a[0]} -> {a[1]} ({a[2]})")
    else:
        print(f" - {a[0]} -> {a[1]}")
print('Skipped (no md found):', len(skipped))
if skipped:
    print(', '.join(skipped))
print('Errors:', len(errors))
for e in errors:
    print(' -', e[0], e[1])
