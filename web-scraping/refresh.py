from __future__ import annotations
"""
refresh.py

Incremental refresh of the UBS knowledge base.
Re-scrapes pages that are older than --max-age-days (default: 30).
Only re-chunks and re-ingests changed documents.

Usage:
    python refresh.py                    # refresh pages older than 30 days
    python refresh.py --max-age-days 7   # refresh weekly
    python refresh.py --dry-run          # show what would be refreshed
"""

import sys
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("refresh")

PROCESSED_DIR = Path(__file__).parent / "output" / "processed"
RAW_DIR = Path(__file__).parent / "output" / "raw"


def get_stale_urls(max_age_days: int) -> list[tuple[str, str, float]]:
    """
    Return list of (url, processed_file_path, age_days) for documents
    older than max_age_days.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)
    stale: list[tuple[str, str, float]] = []

    for fpath in PROCESSED_DIR.glob("*.json"):
        try:
            with open(fpath) as f:
                doc = json.load(f)
        except Exception:
            continue

        scraped_at_str = doc.get("scraped_at")
        if not scraped_at_str:
            # No timestamp → treat as stale
            stale.append((doc.get("url", ""), str(fpath), float("inf")))
            continue

        try:
            scraped_at = datetime.fromisoformat(scraped_at_str)
        except ValueError:
            stale.append((doc.get("url", ""), str(fpath), float("inf")))
            continue

        if scraped_at < cutoff:
            age_days = (datetime.now(timezone.utc) - scraped_at).days
            stale.append((doc["url"], str(fpath), age_days))

    return sorted(stale, key=lambda x: -x[2])  # oldest first


def delete_stale_files(stale: list[tuple[str, str, float]]) -> None:
    """Delete processed (and raw) files for stale URLs so scrapers re-fetch them."""
    for url, fpath, age in stale:
        processed = Path(fpath)
        if processed.exists():
            processed.unlink()

        # Also delete raw HTML so it gets re-fetched
        raw_name = processed.stem + ".html"
        raw = RAW_DIR / raw_name
        if raw.exists():
            raw.unlink()

        logger.info(f"Deleted stale ({age:.0f}d old): {url}")


def run_refresh(max_age_days: int = 30, dry_run: bool = False) -> None:
    logger.info(f"Checking for documents older than {max_age_days} days")

    stale = get_stale_urls(max_age_days)
    logger.info(f"Found {len(stale)} stale documents")

    if not stale:
        logger.info("Knowledge base is up to date. Nothing to refresh.")
        return

    for url, fpath, age in stale[:10]:  # show first 10
        logger.info(f"  STALE ({age:.0f}d): {url}")
    if len(stale) > 10:
        logger.info(f"  ... and {len(stale) - 10} more")

    if dry_run:
        logger.info("DRY RUN — no files deleted, no scraping performed.")
        return

    # Delete stale files so scrapers will re-fetch
    delete_stale_files(stale)
    logger.info(f"Deleted {len(stale)} stale files")

    # Re-run the full pipeline (scrape → chunk → ingest)
    # Only re-scrapes deleted files (others are already cached)
    logger.info("Re-running pipeline for stale documents...")
    from run_all import main as run_pipeline
    sys.argv = ["run_all.py"]  # reset argv for run_all argparse
    run_pipeline()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Refresh stale UBS knowledge base documents")
    parser.add_argument("--max-age-days", type=int, default=30,
                        help="Re-scrape documents older than this many days")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be refreshed without making changes")
    args = parser.parse_args()

    run_refresh(max_age_days=args.max_age_days, dry_run=args.dry_run)
