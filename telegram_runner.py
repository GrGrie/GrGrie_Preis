"""
Utility entry point to run the full scrape + crop + OCR pipeline on a schedule
and push filtered results to Telegram.

Example:
    python telegram_runner.py --site lidl --conf 0.75 --filters Fettarme --run-at 07:30 --send-csv
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from datetime import datetime, timedelta, time as dtime
from pathlib import Path
from typing import Iterable, List, Sequence

from dotenv import load_dotenv

from app.pipeline import RUNS_DIR, scrape_crop_ocr
from app.telegram_notifier import TelegramNotifier


def _seconds_until(target_time: dtime) -> float:
    """Return seconds until the next occurrence of target_time."""
    now = datetime.now()
    run_at = datetime.combine(now.date(), target_time)
    if run_at <= now:
        run_at += timedelta(days=1)
    return (run_at - now).total_seconds()


def _read_ocr_results(csv_path: Path) -> List[dict]:
    if not csv_path.exists():
        raise FileNotFoundError(f"OCR results CSV not found at {csv_path}")

    with csv_path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return [row for row in reader]


def _filter_results(results: Iterable[dict], filters: list[str]) -> List[dict]:
    if not filters:
        return list(results)

    normalized_filters = [f.lower() for f in filters if f]
    filtered: List[dict] = []
    for row in results:
        name = (row.get("name") or "").lower()
        if any(token in name for token in normalized_filters):
            filtered.append(row)
    return filtered


def _find_crop(crops_dir: Path, filename_stem: str) -> Path | None:
    for ext in (".jpg", ".jpeg", ".png", ".bmp"):
        candidate = crops_dir / f"{filename_stem}{ext}"
        if candidate.exists():
            return candidate
    return None


def _send_results(
    notifier: TelegramNotifier,
    run_dir: Path,
    results: list[dict],
    filters: list[str],
    max_results: int | None,
    send_csv: bool,
) -> None:
    filtered_results = _filter_results(results, filters)
    total = len(results)
    matched = len(filtered_results)
    if max_results is not None:
        filtered_results = filtered_results[:max_results]

    filter_text = ", ".join(filters) if filters else "no filters"
    summary = (
        "Groceries pipeline finished\n"
        f"Run folder: {run_dir.name}\n"
        f"Matched {matched} / {total} products for {filter_text}."
    )
    notifier.send_message(summary)

    crops_dir = run_dir / "crops"
    batch: list[tuple[Path, str]] = []

    for idx, row in enumerate(filtered_results, start=1):
        crop_path = _find_crop(crops_dir, row.get("filename", ""))
        caption = f"{row.get('name','(no name)')}\nPrice: {row.get('price','?') or '?'}"
        if crop_path and crop_path.exists():
            batch.append((crop_path, caption))
            if len(batch) == 10:
                notifier.send_media_group(batch)
                batch.clear()
        else:
            notifier.send_message(caption)

    if batch:
        notifier.send_media_group(batch)

    if send_csv:
        csv_path = run_dir / "ocr_results.csv"
        if csv_path.exists():
            notifier.send_document(csv_path, caption="Full OCR CSV")


def _latest_run_dir() -> Path | None:
    if not RUNS_DIR.exists():
        return None
    run_dirs = [p for p in RUNS_DIR.iterdir() if p.is_dir()]
    if not run_dirs:
        return None
    return max(run_dirs, key=lambda p: p.stat().st_mtime)


def _load_filters_from_file(file_path: Path | None) -> list[str]:
    if not file_path:
        return []
    file_path = Path(file_path)
    if not file_path.exists():
        return []
    filters: list[str] = []
    with file_path.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            entry = raw_line.strip()
            if entry and not entry.startswith("#"):
                filters.append(entry)
    return filters


def _parse_filters(cli_filters: Sequence[str] | None, file_path: Path | None) -> list[str]:
    if cli_filters:
        return cli_filters
    env_filters = os.getenv("TELEGRAM_FILTERS")
    if env_filters:
        return [f.strip() for f in env_filters.split(",") if f.strip()]
    return _load_filters_from_file(file_path)


def run_once(args, notifier: TelegramNotifier) -> None:
    run_dir = None

    if args.reuse_run:
        if args.reuse_run.lower() == "latest":
            run_dir = _latest_run_dir()
            if run_dir is None:
                notifier.send_message("Cannot find any previous runs to reuse.")
                return
        else:
            candidate = RUNS_DIR / args.reuse_run
            if not candidate.exists():
                notifier.send_message(f"Run '{args.reuse_run}' was not found in {RUNS_DIR}")
                return
            run_dir = candidate
    else:
        meta = scrape_crop_ocr(site=args.site, conf=args.conf)
        if "error" in meta:
            notifier.send_message(f"Pipeline failed: {meta['error']}")
            return
        run_dir = RUNS_DIR / meta["run_id"]

    ocr_csv = run_dir / "ocr_results.csv"
    try:
        results = _read_ocr_results(ocr_csv)
    except FileNotFoundError as exc:
        notifier.send_message(f"OCR results missing: {exc}")
        return
    filters = _parse_filters(args.filters, args.filter_file)
    _send_results(
        notifier=notifier,
        run_dir=run_dir,
        results=results,
        filters=filters,
        max_results=args.max_results,
        send_csv=args.send_csv,
    )


def main() -> int:
    load_dotenv()

    env_filter_file = os.getenv("TELEGRAM_FILTER_FILE")
    default_filter_file = Path(env_filter_file) if env_filter_file else Path("filters/keywords.txt")

    parser = argparse.ArgumentParser(description="Schedule scraper pipeline and push results to Telegram")
    parser.add_argument("--site", default="lidl", help="Site identifier to scrape")
    parser.add_argument("--conf", type=float, default=0.75, help="Confidence threshold for cropping")
    parser.add_argument(
        "--filters",
        nargs="+",
        help="Product name filters (substring match). Defaults to TELEGRAM_FILTERS env if omitted.",
    )
    parser.add_argument(
        "--filter-file",
        type=Path,
        default=default_filter_file,
        help="Path to newline separated filter list (defaults to filters/keywords.txt or TELEGRAM_FILTER_FILE env).",
    )
    parser.add_argument(
        "--reuse-run",
        help="Skip scraping/OCR and reuse an existing run folder (pass 'latest' to use the newest run).",
    )
    parser.add_argument(
        "--run-at",
        help="Run every day at HH:MM (24h). If omitted, run immediately once.",
    )
    parser.add_argument("--send-csv", action="store_true", help="Send the OCR CSV file as a document")
    parser.add_argument(
        "--max-results",
        type=int,
        default=None,
        help="Limit the number of matching products sent per run",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("TELEGRAM_BOT_TOKEN"),
        help="Telegram bot token (or TELEGRAM_BOT_TOKEN env)",
    )
    parser.add_argument(
        "--chat-id",
        default=os.getenv("TELEGRAM_CHAT_ID"),
        help="Telegram chat id (or TELEGRAM_CHAT_ID env)",
    )

    args = parser.parse_args()
    if not args.token or not args.chat_id:
        print("Telegram bot token and chat id are required (args or environment).", file=sys.stderr)
        return 1

    notifier = TelegramNotifier(args.token, args.chat_id)

    if not args.run_at:
        run_once(args, notifier)
        return 0

    try:
        target_time = datetime.strptime(args.run_at, "%H:%M").time()
    except ValueError:
        print("Invalid --run-at time, expected HH:MM (24h).", file=sys.stderr)
        return 1

    print(f"Scheduler armed. Next run at {args.run_at} local time.")
    while True:
        seconds = _seconds_until(target_time)
        if seconds > 0:
            time.sleep(seconds)
        run_once(args, notifier)


if __name__ == "__main__":
    raise SystemExit(main())
