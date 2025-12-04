"""
Utility entry point to run the full scrape + crop + OCR pipeline on a schedule
and push filtered results to Telegram.

Example:
    python telegram_runner.py --site lidl --conf 0.75 --filters Fettarme --run-at 07:30 --send-csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
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


def _site_from_meta(run_dir: Path) -> str | None:
    meta_path = run_dir / "meta.json"
    if not meta_path.exists():
        return None
    try:
        data = json.loads(meta_path.read_text("utf-8"))
        return data.get("site")
    except Exception:
        return None


def _read_total_crops(run_dir: Path) -> int | None:
    """Read the total number of crops from meta.json."""
    meta_path = run_dir / "meta.json"
    if not meta_path.exists():
        return None
    try:
        data = json.loads(meta_path.read_text("utf-8"))
        return data.get("count")
    except Exception:
        return None


_PAGE_PATTERN = re.compile(r"p(\d+)", re.IGNORECASE)


def _extract_page_number(filename: str | None) -> int | None:
    if not filename:
        return None
    match = _PAGE_PATTERN.search(filename)
    if not match:
        return None
    digits = match.group(1).lstrip("0")
    try:
        return int(digits or "0")
    except ValueError:
        return None


def _page_caption(row: dict) -> str:
    page_num = _extract_page_number(row.get("filename"))
    page_label = f"Page {page_num}" if page_num is not None else "Page ?"
    name = row.get("name") or "(no name)"
    price = row.get("price") or "?"
    return f"{page_label} - {name} - {price}"


def _send_results(
    notifier: TelegramNotifier,
    run_infos: list[dict],
    filters: list[str],
    max_results: int | None,
    send_csv: bool,
) -> None:
    if not run_infos:
        notifier.send_message("No OCR results available.")
        return

    for info in run_infos:
        rows = info["results"]
        filtered = _filter_results(rows, filters)
        matched = len(filtered)
        effective = filtered if max_results is None else filtered[:max_results]
        
        # Get total crops from meta.json, fallback to OCR results count
        total_crops = _read_total_crops(info["run_dir"])
        if total_crops is None:
            total_crops = len(rows)

        csv_caption = (
            f"Finished run for {info['site']}. Matches {matched}/{total_crops}. "
            "Results attached."
        )
        csv_path = info["run_dir"] / "ocr_results.csv"
        if send_csv and csv_path.exists():
            notifier.send_document(csv_path, caption=csv_caption)
        else:
            notifier.send_message(csv_caption)

        crops_dir = info["run_dir"] / "crops"
        if not effective:
            notifier.send_message(f"{info['site']}: No matching crops to display.")
            continue

        for idx in range(0, len(effective), 10):
            chunk = effective[idx : idx + 10]
            media_items: list[tuple[Path, str]] = []
            for row in chunk:
                crop_path = _find_crop(crops_dir, row.get("filename", ""))
                caption = _page_caption(row)
                if crop_path and crop_path.exists():
                    media_items.append((crop_path, caption))
                else:
                    notifier.send_message(f"{info['site']}: {caption} (image missing)")
            if media_items:
                notifier.send_media_group(media_items)


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
    if args.reuse_run and args.sites:
        notifier.send_message("Cannot combine --reuse-run with --sites.")
        return

    filters = _parse_filters(args.filters, args.filter_file)
    run_infos: list[dict] = []

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

        try:
            results = _read_ocr_results(run_dir / "ocr_results.csv")
        except FileNotFoundError as exc:
            notifier.send_message(f"OCR results missing: {exc}")
            return
        site_name = (_site_from_meta(run_dir) or args.site or "unknown").title()
        run_infos.append({
            "site": site_name,
            "run_dir": run_dir,
            "results": results,
        })
    else:
        sites = args.sites if args.sites else [args.site]
        for site in sites:
            meta = scrape_crop_ocr(site=site, conf=args.conf)
            if "error" in meta:
                notifier.send_message(f"Pipeline failed for {site}: {meta['error']}")
                return
            run_dir = RUNS_DIR / meta["run_id"]
            try:
                results = _read_ocr_results(run_dir / "ocr_results.csv")
            except FileNotFoundError as exc:
                notifier.send_message(f"OCR results missing for {site}: {exc}")
                return
            site_name = (meta.get("site") or _site_from_meta(run_dir) or site).title()
            run_infos.append({
                "site": site_name,
                "run_dir": run_dir,
                "results": results,
            })

    _send_results(
        notifier=notifier,
        run_infos=run_infos,
        filters=filters,
        max_results=args.max_results,
        send_csv=args.send_csv,
    )


def main() -> int:
    load_dotenv()

    env_filter_file = os.getenv("TELEGRAM_FILTER_FILE")
    default_filter_file = Path(env_filter_file) if env_filter_file else Path("configs/keywords.txt")

    parser = argparse.ArgumentParser(description="Schedule scraper pipeline and push results to Telegram")
    parser.add_argument("--site", default="lidl", help="Site identifier to scrape")
    parser.add_argument(
        "--sites",
        nargs="+",
        help="List of site identifiers to process sequentially and merge into one notification",
    )
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
        help="Path to newline separated filter list (defaults to configs/keywords.txt or TELEGRAM_FILTER_FILE env).",
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
