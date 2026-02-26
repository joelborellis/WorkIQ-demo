#!/usr/bin/env python3
"""
drafts.py — Simple draft management utility for article-writer sessions.

Usage:
    python3 drafts.py save <slug> <content_file>   # Save a timestamped draft
    python3 drafts.py list [<slug>]                # List drafts (optionally filter by slug)
    python3 drafts.py latest <slug>                # Print path to most recent draft
    python3 drafts.py diff <slug>                  # Show diff between last two drafts
    python3 drafts.py clean <slug> --keep 3        # Keep only N most recent drafts

Examples:
    python3 drafts.py save work-iq-architecture /tmp/draft.md
    python3 drafts.py list
    python3 drafts.py list work-iq-architecture
    python3 drafts.py latest work-iq-architecture
"""

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path


DRAFTS_DIR = Path("artifacts/drafts")


def article_dir(slug: str) -> Path:
    """Return the per-article subfolder, creating it if needed."""
    d = DRAFTS_DIR / slug
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_draft(slug: str, content_file: str):
    source = Path(content_file)
    if not source.exists():
        print(f"[error] File not found: {content_file}", file=sys.stderr)
        sys.exit(1)

    dest_dir = article_dir(slug)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = dest_dir / f"draft-{timestamp}.md"
    dest.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"✅ Draft saved: {dest}")
    return dest


def organize_loose(slug: str, loose_file: str):
    """Move a loose .md file from drafts/ root into the correct article subfolder."""
    source = Path(loose_file)
    if not source.exists():
        print(f"[error] File not found: {loose_file}", file=sys.stderr)
        sys.exit(1)

    dest_dir = article_dir(slug)
    dest = dest_dir / "draft-imported.md"
    source.rename(dest)
    print(f"✅ Organized: {source.name} → {dest}")


def list_drafts(slug: str = None):
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)

    if slug:
        # Show drafts for a specific article
        d = DRAFTS_DIR / slug
        if not d.exists():
            print(f"No article folder found for slug: {slug}")
            return
        files = sorted(d.glob("*.md"))
        if not files:
            print(f"No drafts found in {d}")
            return
        print(f"\n📁 {slug}/")
        print(f"  {'File':<45} {'Words':>6}")
        print("  " + "-" * 53)
        for f in files:
            words = len(f.read_text(encoding="utf-8").split())
            marker = " ← FINAL" if f.name == "FINAL.md" else ""
            print(f"  {f.name:<45} {words:>6}{marker}")
    else:
        # List all articles and their draft counts
        article_dirs = sorted([d for d in DRAFTS_DIR.iterdir() if d.is_dir()])
        loose_files = sorted(DRAFTS_DIR.glob("*.md"))

        if not article_dirs and not loose_files:
            print("No drafts found.")
            return

        if loose_files:
            print(f"\n⚠️  Loose files (not yet organized into an article folder):")
            for f in loose_files:
                words = len(f.read_text(encoding="utf-8").split())
                print(f"  {f.name:<50} {words:>6} words")
            print(f"  → Use: python3 drafts.py organize <slug> <filename>")

        for d in article_dirs:
            files = sorted(d.glob("*.md"))
            if not files:
                continue
            has_final = any(f.name == "FINAL.md" for f in files)
            status = "✅ FINAL" if has_final else f"{len(files)} draft(s)"
            latest = max(files, key=lambda f: f.stat().st_mtime)
            words = len(latest.read_text(encoding="utf-8").split())
            print(f"\n📁 {d.name:<40} [{status}]  ~{words:,} words (latest)")


def latest_draft(slug: str) -> Path:
    d = DRAFTS_DIR / slug
    # Prefer FINAL if it exists
    final = d / "FINAL.md"
    if final.exists():
        print(final)
        return final
    files = sorted([f for f in d.glob("draft-*.md")])
    if not files:
        print(f"[error] No drafts found for slug: {slug}", file=sys.stderr)
        sys.exit(1)
    print(files[-1])
    return files[-1]


def diff_drafts(slug: str):
    d = DRAFTS_DIR / slug
    files = sorted(d.glob("draft-*.md"))
    if len(files) < 2:
        print(f"Need at least 2 draft checkpoints for diff. Found: {len(files)}")
        return
    os.system(f"diff --color=always '{files[-2]}' '{files[-1]}' | head -100")


def clean_drafts(slug: str, keep: int):
    d = DRAFTS_DIR / slug
    files = sorted(d.glob("draft-*.md"))  # only touch timestamped drafts, not FINAL/outline
    to_delete = files[:-keep] if len(files) > keep else []
    for f in to_delete:
        f.unlink()
        print(f"  Deleted: {f.name}")
    print(f"✅ Kept {min(keep, len(files))} most recent drafts for '{slug}'")


def main():
    parser = argparse.ArgumentParser(description="Article draft manager")
    subparsers = parser.add_subparsers(dest="command")

    # save
    p_save = subparsers.add_parser("save", help="Save a timestamped draft checkpoint")
    p_save.add_argument("slug", help="Article slug (e.g. work-iq-architecture)")
    p_save.add_argument("content_file", help="Path to the file to save as draft")

    # organize
    p_org = subparsers.add_parser("organize", help="Move a loose draft file into its article folder")
    p_org.add_argument("slug", help="Article slug to organize under")
    p_org.add_argument("loose_file", help="Path to the loose .md file in drafts/")

    # list
    p_list = subparsers.add_parser("list", help="List all articles or drafts for one article")
    p_list.add_argument("slug", nargs="?", help="Filter by slug")

    # latest
    p_latest = subparsers.add_parser("latest", help="Print path to most recent draft")
    p_latest.add_argument("slug")

    # diff
    p_diff = subparsers.add_parser("diff", help="Diff last two drafts")
    p_diff.add_argument("slug")

    # clean
    p_clean = subparsers.add_parser("clean", help="Remove old draft checkpoints, keep N most recent")
    p_clean.add_argument("slug")
    p_clean.add_argument("--keep", type=int, default=3)

    args = parser.parse_args()

    if args.command == "save":
        save_draft(args.slug, args.content_file)
    elif args.command == "organize":
        organize_loose(args.slug, args.loose_file)
    elif args.command == "list":
        list_drafts(getattr(args, "slug", None))
    elif args.command == "latest":
        latest_draft(args.slug)
    elif args.command == "diff":
        diff_drafts(args.slug)
    elif args.command == "clean":
        clean_drafts(args.slug, args.keep)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
