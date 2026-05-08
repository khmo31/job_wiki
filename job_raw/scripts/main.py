#!/usr/bin/env python3
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
    parser = argparse.ArgumentParser(description="Batch runner for P-Reinforce Harvester")
    parser.add_argument("--no-mock", dest="mock", action="store_false", help="disable mock data", default=True)
    parser.add_argument("--dry-run", action="store_true", help="do not write files", default=False)
    parser.add_argument("--count", type=int, default=None)
    parser.add_argument("--days", type=int, default=3, help="recent N days for incremental mode")
    args = parser.parse_args()
    summary = run_harvester(mock=args.mock, dry_run=args.dry_run, count=args.count, days=args.days)
    attempted = summary.get("attempted", 0)
    saved = summary.get("saved", 0)
    skipped = summary.get("skipped", 0)
    errors = summary.get("errors", 0)
    tokens = summary.get("tokens", 0)
    cost = summary.get("cost", 0.0)
    llm_analyzed = summary.get("llm_analyzed", 0)
    density = (llm_analyzed / attempted * 100.0) if attempted else 0.0
    print("--- Report ---")
    print(f"Attempted: {attempted}")
    print(f"New saved: {saved}")
    print(f"Skipped (dup): {skipped}")
    print(f"Errors: {errors}")
    print(f"LLM-analyzed: {llm_analyzed} ({density:.1f}% of attempted)")
    print(f"Estimated tokens used: {tokens}, estimated cost USD: ${cost:.4f}")


if __name__ == "__main__":
    cli()
