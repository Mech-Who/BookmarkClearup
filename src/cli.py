"""BookmarkClearup 命令行入口。"""

import argparse
import logging
import sys
from pathlib import Path

from src.bookmark_io import document_with_root, load_bookmark_file, write_bookmark_file
from src.functional import merge, visit

logger = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Merge Chromium bookmark JSON files safely.")
    parser.add_argument("--base", required=True)
    parser.add_argument("--source", nargs="+", required=True)
    parser.add_argument("--strategy", choices=["exact-url"], default="exact-url")
    parser.add_argument("--output")
    parser.add_argument("--in-place", action="store_true")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="WARNING")
    return parser


def _configure_logging(level: str) -> None:
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=getattr(logging, level), filename=log_dir / "bookmarkclearup.log")


def main(argv: list[str] | None = None) -> int:
    """执行安全合并；默认只显示统计，不写文件。"""
    parser = _parser()
    args = parser.parse_args(argv)
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
            _, backup = write_bookmark_file(args.base, document_with_root(base_document, merged), in_place=True)
            print(f"backup={backup}")
        return 0
    except (OSError, ValueError, TypeError, FileExistsError) as exc:
        logger.error("bookmark merge failed: %s", exc)
        print(f"error: {exc}", file=sys.stderr)
        return 1
