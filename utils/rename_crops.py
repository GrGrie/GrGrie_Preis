#!/usr/bin/env python3
"""Rename crop files in order (crop0001, crop0002, ...)."""

import argparse
import sys
import uuid
from pathlib import Path
from typing import List, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CROP_DIR = REPO_ROOT / "data" / "ocr" / "crops"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Rename files in a directory to sequential cropXXXX names. "
            "Defaults to data/ocr/crops."
        )
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=str(DEFAULT_CROP_DIR),
        help="Directory containing crop files (default: data/ocr/crops).",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=1,
        help="Starting index for numbering (default: 1).",
    )
    parser.add_argument(
        "--prefix",
        default="crop",
        help='Filename prefix (default: "crop").',
    )
    return parser.parse_args()


def collect_files(directory: Path) -> List[Path]:
    files = [path for path in directory.iterdir() if path.is_file()]
    return sorted(files, key=lambda p: p.name)


def rename_files(
    files: List[Path],
    directory: Path,
    prefix: str,
    start_index: int,
) -> None:
    if not files:
        print(f"No files found in {directory}")
        return

    width = max(4, len(str(start_index + len(files) - 1)))
    tmp_marker = f"__renametmp_{uuid.uuid4().hex}__"
    staged: List[Tuple[Path, str, int]] = []

    for offset, file_path in enumerate(files):
        suffix = file_path.suffix
        tmp_name = f"{file_path.stem}{tmp_marker}{suffix}"
        tmp_path = file_path.with_name(tmp_name)
        file_path.rename(tmp_path)
        staged.append((tmp_path, suffix, start_index + offset))

    for tmp_path, suffix, number in staged:
        new_name = f"{prefix}{number:0{width}d}{suffix}"
        target = directory / new_name
        if target == tmp_path:
            continue
        if target.exists():
            raise FileExistsError(f"Target file already exists: {target}")
        tmp_path.rename(target)

    print(f"Renamed {len(files)} files in {directory}")


def main() -> int:
    args = parse_args()
    directory = Path(args.directory).expanduser().resolve()

    if not directory.exists() or not directory.is_dir():
        print(f"Directory does not exist: {directory}", file=sys.stderr)
        return 1
    if args.start < 0:
        print("--start must be >= 0", file=sys.stderr)
        return 1

    files = collect_files(directory)
    rename_files(files, directory, args.prefix, args.start)
    return 0


if __name__ == "__main__":
    sys.exit(main())
