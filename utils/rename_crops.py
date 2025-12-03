#!/usr/bin/env python3
"""
Rename crop files to ensure a continuous sequence (crop0001, crop0002...).
- Deletes images that don't have a corresponding .txt file.
- Renames new files to continue the sequence.
- Fills gaps in the existing sequence (e.g. if crop0002 is deleted, crop0003 becomes crop0002).
"""

import argparse
import sys
import re
from pathlib import Path
from typing import List, Dict, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CROP_DIR = REPO_ROOT / "data" / "ocr" / "crops"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize crop filenames: delete orphans, fill gaps, rename new files."
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=str(DEFAULT_CROP_DIR),
        help="Directory containing crop files.",
    )
    parser.add_argument(
        "--prefix",
        default="crop",
        help='Filename prefix (default: "crop").',
    )
    return parser.parse_args()


def collect_groups(directory: Path) -> Dict[str, List[Path]]:
    """
    Group files by stem.
    Excludes classes.txt.
    """
    groups: Dict[str, List[Path]] = {}
    for path in directory.iterdir():
        if not path.is_file():
            continue
        if path.name == "classes.txt":
            continue
        
        stem = path.stem
        if stem not in groups:
            groups[stem] = []
        groups[stem].append(path)
    return groups


def process_groups(
    groups: Dict[str, List[Path]], 
    prefix: str
) -> Tuple[List[List[Path]], List[List[Path]]]:
    """
    Filters groups.
    - Deletes groups with image but no txt.
    - Deletes groups with txt but no image (to prevent collisions).
    - Returns tuple: (existing_crop_groups, new_file_groups)
      where each item is a list of files for that stem.
    """
    existing_crops = [] # (number, files)
    new_files = []      # (stem, files)
    
    # Regex to identify existing numbered crops
    crop_pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    
    # Image extensions to check for
    img_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff'}

    for stem, files in groups.items():
        has_img = any(f.suffix.lower() in img_exts for f in files)
        has_txt = any(f.suffix.lower() == '.txt' for f in files)
        
        # Logic:
        # 1. Image exists, Txt missing -> DELETE (User request)
        # 2. Txt exists, Image missing -> DELETE (Implicit safety for re-indexing)
        # 3. Both exist -> KEEP
        
        is_valid_pair = has_img and has_txt
        
        if is_valid_pair:
            match = crop_pattern.match(stem)
            if match:
                try:
                    num = int(match.group(1))
                    existing_crops.append((num, files))
                except ValueError:
                    new_files.append((stem, files))
            else:
                new_files.append((stem, files))
        else:
            # Handle invalid/orphaned files
            # Only delete if it looks like it was SUPPOSED to be a pair (has one of them)
            if has_img or has_txt:
                print(f"Deleting incomplete pair: {stem} (Files: {[f.name for f in files]})")
                for f in files:
                    try:
                        f.unlink()
                    except OSError as e:
                        print(f"Error deleting {f}: {e}")

    # Sort existing by number
    existing_crops.sort(key=lambda x: x[0])
    
    # Sort new by stem
    new_files.sort(key=lambda x: x[0])
    
    return [x[1] for x in existing_crops], [x[1] for x in new_files]


def rename_sequence(
    existing_groups: List[List[Path]],
    new_groups: List[List[Path]],
    directory: Path,
    prefix: str
) -> None:
    
    all_groups = existing_groups + new_groups
    current_idx = 1
    
    print(f"Processing {len(all_groups)} valid groups...")
    
    for files in all_groups:
        target_stem = f"{prefix}{current_idx:04d}"
        
        # Determine if we need to rename
        # Check the stem of the first file (all have same stem)
        current_stem = files[0].stem
        
        if current_stem == target_stem:
            # Already correct
            current_idx += 1
            continue
            
        # Rename files in group
        for f in files:
            new_name = f"{target_stem}{f.suffix}"
            target_path = directory / new_name
            
            # On Windows, rename raises FileExistsError if target exists.
            # If target exists here, it means it's a file we didn't track in our "valid groups"
            # (e.g. an orphan we failed to delete, or some other file).
            # We'll try to delete it to make way.
            if target_path.exists() and target_path not in files:
                print(f"Warning: Target {target_path.name} exists. Overwriting.")
                try:
                    target_path.unlink()
                except OSError:
                    pass

            try:
                f.rename(target_path)
                print(f"Renamed {f.name} -> {new_name}")
            except OSError as e:
                print(f"Error renaming {f.name} to {new_name}: {e}")
                
        current_idx += 1
    
    print("Done.")


def main() -> int:
    args = parse_args()
    directory = Path(args.directory).expanduser().resolve()

    if not directory.exists() or not directory.is_dir():
        print(f"Directory does not exist: {directory}", file=sys.stderr)
        return 1

    groups = collect_groups(directory)
    existing, new = process_groups(groups, args.prefix)
    rename_sequence(existing, new, directory, args.prefix)

    return 0


if __name__ == "__main__":
    sys.exit(main())
