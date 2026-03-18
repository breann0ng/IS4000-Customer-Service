from __future__ import annotations
"""
quality_check.py

Validates the output of the scraping and chunking pipeline before ingestion.
Produces a report highlighting:

- Empty or very short documents
- Duplicate chunks (same text, different IDs)
- Chunks with no metadata
- Token count distribution (too small or too large)
- Coverage per topic area
- Sample content for manual review

Usage:
    python quality_check.py
    python quality_check.py --fix          # auto-remove clearly bad chunks
    python quality_check.py --report-file report.json
"""

import re
import sys
import json
import hashlib
import argparse
import logging
from pathlib import Path
from collections import defaultdict, Counter

import jsonlines

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("quality_check")

CHUNKS_DIR = Path(__file__).parent / "output" / "chunks"
PROCESSED_DIR = Path(__file__).parent / "output" / "processed"
ALL_CHUNKS_FILE = CHUNKS_DIR / "all_chunks.jsonl"

# Thresholds
MIN_CHUNK_TOKENS = 30       # chunks below this are probably nav fragments
MAX_CHUNK_TOKENS = 600      # chunks above this weren't split properly
MIN_CHUNK_CHARS = 80        # character-based floor
NOISE_PATTERNS = [
    r"^skip links?$",
    r"^back to top$",
    r"^footer navigation$",
    r"^main navigation$",
    r"^\d+ results? found$",
    r"^change your domicile",
    r"^© ubs",
    r"^short url:",
]
NOISE_RE = re.compile("|".join(NOISE_PATTERNS), re.IGNORECASE)


def load_chunks(path: Path) -> list[dict]:
    if not path.exists():
        logger.error(f"Chunks file not found: {path}")
        logger.error("Run chunk_all.py first.")
        sys.exit(1)
    with jsonlines.open(path) as reader:
        return list(reader)


def check_chunks(chunks: list[dict]) -> dict:
    """Run all quality checks. Returns a report dict."""
    issues: dict[str, list] = defaultdict(list)
    seen_text_hashes: dict[str, str] = {}  # hash → first chunk id
    topic_counts: Counter = Counter()
    token_counts: list[int] = []
    doc_type_counts: Counter = Counter()

    for chunk in chunks:
        cid = chunk.get("id", "NO_ID")
        text = chunk.get("text", "")
        meta = chunk.get("metadata", {})
        tokens = meta.get("token_count", 0)
        topic = meta.get("topic", "unknown")
        doc_type = meta.get("doc_type", "unknown")

        topic_counts[topic] += 1
        doc_type_counts[doc_type] += 1
        token_counts.append(tokens)

        # --- Check: missing ID
        if not chunk.get("id"):
            issues["missing_id"].append({"chunk": cid, "text_preview": text[:80]})

        # --- Check: empty text
        if not text or len(text.strip()) < MIN_CHUNK_CHARS:
            issues["too_short"].append({
                "id": cid,
                "chars": len(text),
                "text": text[:120],
            })

        # --- Check: noise content (nav/footer fragments)
        first_line = text.strip().split("\n")[0].strip()
        if NOISE_RE.match(first_line):
            issues["noise_content"].append({"id": cid, "text": text[:120]})

        # --- Check: token count too low
        if tokens < MIN_CHUNK_TOKENS:
            issues["low_token_count"].append({
                "id": cid,
                "tokens": tokens,
                "text": text[:120],
            })

        # --- Check: token count too high (chunker didn't split)
        if tokens > MAX_CHUNK_TOKENS:
            issues["high_token_count"].append({
                "id": cid,
                "tokens": tokens,
                "text_preview": text[:120],
            })

        # --- Check: missing metadata fields
        required_fields = ["source_url", "topic", "doc_type", "scraped_at"]
        missing = [f for f in required_fields if not meta.get(f)]
        if missing:
            issues["missing_metadata"].append({"id": cid, "missing_fields": missing})

        # --- Check: duplicate text
        text_hash = hashlib.md5(text.strip().encode()).hexdigest()
        if text_hash in seen_text_hashes:
            issues["duplicate_text"].append({
                "id": cid,
                "duplicate_of": seen_text_hashes[text_hash],
                "text_preview": text[:80],
            })
        else:
            seen_text_hashes[text_hash] = cid

    # --- Compute token stats
    if token_counts:
        sorted_tc = sorted(token_counts)
        p25 = sorted_tc[len(sorted_tc) // 4]
        p50 = sorted_tc[len(sorted_tc) // 2]
        p75 = sorted_tc[3 * len(sorted_tc) // 4]
        p95 = sorted_tc[int(len(sorted_tc) * 0.95)]
        avg = sum(token_counts) / len(token_counts)
    else:
        p25 = p50 = p75 = p95 = avg = 0

    # --- Coverage check: identify missing expected topics
    expected_topics = {
        "creditcard", "debitcard", "account", "payments",
        "e-banking", "mobile-banking", "pension", "mortgages",
        "investments", "digital-banking",
    }
    missing_topics = expected_topics - set(topic_counts.keys())

    return {
        "summary": {
            "total_chunks": len(chunks),
            "unique_chunks": len(seen_text_hashes),
            "duplicates": len(issues["duplicate_text"]),
            "topics_covered": len(topic_counts),
            "doc_types": dict(doc_type_counts),
        },
        "topic_coverage": dict(topic_counts.most_common()),
        "missing_expected_topics": sorted(missing_topics),
        "token_stats": {
            "avg": round(avg, 1),
            "p25": p25,
            "p50": p50,
            "p75": p75,
            "p95": p95,
            "min": min(token_counts) if token_counts else 0,
            "max": max(token_counts) if token_counts else 0,
        },
        "issues": {k: v for k, v in issues.items()},
        "issue_counts": {k: len(v) for k, v in issues.items()},
    }


def print_report(report: dict) -> None:
    """Pretty-print the quality report to stdout."""
    print("\n" + "=" * 60)
    print("UBS Knowledge Base Quality Report")
    print("=" * 60)

    s = report["summary"]
    print(f"\n📊 Summary")
    print(f"  Total chunks     : {s['total_chunks']}")
    print(f"  Unique chunks    : {s['unique_chunks']}")
    print(f"  Duplicates found : {s['duplicates']}")
    print(f"  Topics covered   : {s['topics_covered']}")
    print(f"  Doc types        : {s['doc_types']}")

    ts = report["token_stats"]
    print(f"\n📏 Token Distribution")
    print(f"  Min / Avg / Max  : {ts['min']} / {ts['avg']} / {ts['max']}")
    print(f"  p25 / p50 / p75  : {ts['p25']} / {ts['p50']} / {ts['p75']}")
    print(f"  p95              : {ts['p95']}")

    print(f"\n📁 Topic Coverage")
    for topic, count in sorted(report["topic_coverage"].items(), key=lambda x: -x[1]):
        bar = "█" * min(count // 2, 40)
        print(f"  {topic:<30s} {count:>4d}  {bar}")

    if report["missing_expected_topics"]:
        print(f"\n⚠️  Missing Expected Topics")
        for t in report["missing_expected_topics"]:
            print(f"  ✗ {t}")
    else:
        print(f"\n✅  All expected topics have coverage")

    print(f"\n🔍 Issues Found")
    ic = report["issue_counts"]
    if not any(ic.values()):
        print("  ✅ No issues found!")
    else:
        for issue_type, count in ic.items():
            status = "✅" if count == 0 else "⚠️ "
            print(f"  {status} {issue_type:<25s}: {count}")

    # Show samples of worst issues
    issues = report["issues"]
    for issue_type in ["noise_content", "too_short", "high_token_count"]:
        samples = issues.get(issue_type, [])[:3]
        if samples:
            print(f"\n  Sample {issue_type}:")
            for s in samples:
                print(f"    ID: {s.get('id', '?')}")
                print(f"    Text: {s.get('text', s.get('text_preview', ''))[:100]!r}")


def remove_bad_chunks(chunks: list[dict], report: dict) -> tuple[list[dict], int]:
    """Remove chunks flagged as noise or too short. Returns (clean_chunks, removed_count)."""
    bad_ids: set[str] = set()
    issues = report["issues"]

    for issue_type in ["noise_content", "too_short", "missing_id"]:
        for item in issues.get(issue_type, []):
            bad_ids.add(item.get("id", ""))

    clean = [c for c in chunks if c.get("id") not in bad_ids]
    removed = len(chunks) - len(clean)
    logger.info(f"Removed {removed} bad chunks. {len(clean)} clean chunks remain.")
    return clean, removed


def run_quality_check(
    chunks_file: Path = ALL_CHUNKS_FILE,
    fix: bool = False,
    report_file: Path | None = None,
) -> dict:
    logger.info(f"Loading chunks from {chunks_file}")
    chunks = load_chunks(chunks_file)
    logger.info(f"Loaded {len(chunks)} chunks")

    report = check_chunks(chunks)
    print_report(report)

    if report_file:
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2)
        logger.info(f"Report saved to {report_file}")

    if fix:
        clean_chunks, removed = remove_bad_chunks(chunks, report)
        if removed > 0:
            # Overwrite the all_chunks file with cleaned version
            with jsonlines.open(chunks_file, mode="w") as writer:
                writer.write_all(clean_chunks)
            logger.info(f"✅ Wrote {len(clean_chunks)} clean chunks back to {chunks_file}")
        else:
            logger.info("No chunks to remove.")

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Quality check the UBS knowledge base chunks")
    parser.add_argument("--chunks-file", type=Path, default=ALL_CHUNKS_FILE)
    parser.add_argument("--fix", action="store_true", help="Auto-remove bad chunks")
    parser.add_argument("--report-file", type=Path, default=None)
    args = parser.parse_args()

    run_quality_check(
        chunks_file=args.chunks_file,
        fix=args.fix,
        report_file=args.report_file,
    )
