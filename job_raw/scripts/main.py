#!/usr/bin/env python3
"""job_raw CLI — 순수 수집만 실행."""
import sys, os, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import argparse
from harvester import main as run_harvester


def cli():
    parser = argparse.ArgumentParser(description="job_raw Harvester — 순수 수집")
    parser.add_argument("--no-mock", dest="mock", action="store_false",
                        help="disable mock data", default=True)
    parser.add_argument("--dry-run", action="store_true",
                        help="do not write files", default=False)
    parser.add_argument("--count", type=int, default=None,
                        help="max jobs to process")
    parser.add_argument("--days", type=int, default=3,
                        help="recent N days for incremental mode")
    parser.add_argument("--pages", type=int, default=None,
                        help="max API pages (default: 1, each page = 50 items)")
    args = parser.parse_args()
    summary = run_harvester(mock=args.mock, dry_run=args.dry_run,
                            count=args.count, days=args.days,
                            max_pages=args.pages)
    print("--- Report ---")
    print(f"Attempted: {summary.get('attempted', 0)}")
    print(f"New saved: {summary.get('saved', 0)}")
    print(f"Skipped (dup): {summary.get('skipped', 0)}")
    print(f"Errors: {summary.get('errors', 0)}")
    print(f"Detail calls: {summary.get('detail_calls', 0)}")


if __name__ == "__main__":
    cli()
