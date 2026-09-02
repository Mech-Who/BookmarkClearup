"""BookmarkClearup 命令行入口。"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from src.bookmark_io import clean_backups, document_with_root, list_backups, load_bookmark_file, write_bookmark_file
from src.functional import merge, visit

logger = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Merge Chromium bookmark JSON files safely.")
    parser.add_argument("--base")
    parser.add_argument("--source", nargs="+")
    parser.add_argument("--strategy", choices=["exact-url"], default="exact-url")
    parser.add_argument("--output")
    parser.add_argument("--in-place", action="store_true")
    parser.add_argument("--yes", action="store_true", help="explicitly confirm a destructive operation")
    parser.add_argument("--clean-backups", metavar="DIRECTORY")
    parser.add_argument("--start", help="backup time lower bound: YYYYMMDD_HHMMSS")
    parser.add_argument("--end", help="backup time upper bound: YYYYMMDD_HHMMSS")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="WARNING")
    return parser


def _configure_logging(level: str) -> None:
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=getattr(logging, level), filename=log_dir / "bookmarkclearup.log")


def _parse_time(value: str | None) -> datetime | None:
    return datetime.strptime(value, "%Y%m%d_%H%M%S") if value else None


def main(argv: list[str] | None = None) -> int:
    """执行安全合并或备份清理；默认只预览，不写文件。"""
    parser = _parser()
    args = parser.parse_args(argv)
    if args.yes and not args.in_place and not args.clean_backups:
        parser.error("--yes requires --in-place or --clean-backups")
    if (args.start or args.end) and not args.clean_backups:
        parser.error("--start/--end require --clean-backups")
    if args.clean_backups and (args.base or args.source or args.output or args.in_place):
        parser.error("--clean-backups cannot be combined with merge options")
    if args.clean_backups:
        try:
            backups = list_backups(args.clean_backups, _parse_time(args.start), _parse_time(args.end))
            for path in backups:
                print(path)
            if args.yes:
                clean_backups(args.clean_backups, start=_parse_time(args.start), end=_parse_time(args.end), dry_run=False, confirm=True)
            return 0
        except (OSError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    if not args.base or not args.source:
        parser.error("--base and --source are required for merge")
    if args.output and args.in_place:
        parser.error("--output and --in-place are mutually exclusive")
    _configure_logging(args.log_level)
    try:
        base_document, base = load_bookmark_file(args.base)
        sources = [load_bookmark_file(source) for source in args.source]
        merged = merge(base, *(tree for _, tree in sources))
        base_count = sum(1 for _ in visit(base))
        source_count = sum(sum(1 for _ in visit(tree)) for _, tree in sources)
        result_count = sum(1 for _ in visit(merged))
        print(f"base={base_count} sources={source_count} new={result_count - base_count} result={result_count}")
        if args.output:
            write_bookmark_file(args.output, document_with_root(base_document, merged), output=True)
        elif args.in_place:
            if not args.yes:
                answer = input(f"Replace {args.base}? Type 'yes' to continue: ")
                if answer.strip().lower() != "yes":
                    print("cancelled: explicit confirmation required", file=sys.stderr)
                    return 2
            _, backup = write_bookmark_file(args.base, document_with_root(base_document, merged), in_place=True)
            print(f"backup={backup}")
        return 0
    except (OSError, ValueError, TypeError, FileExistsError) as exc:
        logger.error("bookmark merge failed: %s", exc)
        print(f"error: {exc}", file=sys.stderr)
        return 1