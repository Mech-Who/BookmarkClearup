"""BookmarkClearup 命令行入口。"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

from src.bookmark_io import clean_backups, list_backups, load_chromium_file, merge_documents, output_documents, write_bookmark_file
from src.chromium import discover_profiles, profile_bookmarks_path
from src.entity import BookmarkFolder
from src.functional import visit

logger = logging.getLogger(__name__)


def _parser() -> argparse.ArgumentParser:
    """构造命令行参数解析器。"""
    parser = argparse.ArgumentParser(description="Merge Chromium bookmark JSON files safely.")
    parser.add_argument("--base")
    parser.add_argument("--source", nargs="+")
    parser.add_argument("--base-browser", choices=["chrome", "edge"])
    parser.add_argument("--base-profile")
    parser.add_argument("--source-browser", choices=["chrome", "edge"])
    parser.add_argument("--source-profile", nargs="+")
    parser.add_argument("--list-profiles", choices=["chrome", "edge"])
    parser.add_argument("--strategy", choices=["exact-url"], default="exact-url")
    parser.add_argument("--output")
    parser.add_argument("--output-dir")
    parser.add_argument("--in-place", action="store_true")
    parser.add_argument("--yes", action="store_true")
    parser.add_argument("--clean-backups", metavar="DIRECTORY")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="WARNING")
    return parser


def _configure_logging(level: str) -> None:
    """配置项目日志文件。"""
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=getattr(logging, level), filename=log_dir / "bookmarkclearup.log")


def _parse_time(value: str | None) -> datetime | None:
    """解析备份清理时间参数。"""
    return datetime.strptime(value, "%Y%m%d_%H%M%S") if value else None


def _resolve_input_paths(args: argparse.Namespace, parser: argparse.ArgumentParser) -> tuple[str, list[str]]:
    """校验输入模式并解析显式路径或浏览器 Profile 路径。"""
    path_mode = bool(args.base or args.source)
    profile_mode = bool(args.base_browser or args.base_profile or args.source_browser or args.source_profile)
    if path_mode and profile_mode:
        parser.error("explicit paths and browser/profile options are mutually exclusive")
    if profile_mode:
        if not (args.base_browser and args.base_profile and args.source_browser and args.source_profile):
            parser.error("browser mode requires base/source browser and profile")
        base_path = profile_bookmarks_path(args.base_browser, args.base_profile)
        source_paths = [profile_bookmarks_path(args.source_browser, profile) for profile in args.source_profile]
        return str(base_path), [str(path) for path in source_paths]
    if not args.base or not args.source:
        parser.error("--base and --source are required for merge")
    return args.base, args.source


def _count_pages(roots: dict[str, BookmarkFolder]) -> int:
    """统计多个根节点中的页面数量。"""
    return sum(sum(1 for _ in visit(root)) for root in roots.values())


def _write_independent_outputs(output_dir: Path, documents: list[dict], base_path: str) -> None:
    """写出独立结果，并仅回滚仍属于本次调用的文件。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    names = [Path(base_path).stem + "_merged.json"]
    names.extend(f"source_{index}_merged.json" for index in range(1, len(documents)))
    targets = [output_dir / name for name in names]
    if any(target.exists() for target in targets):
        raise FileExistsError("one or more independent output files already exist")
    created: dict[Path, tuple[int, int, int, int]] = {}
    try:
        for target, document in zip(targets, documents):
            # 1. 每次写入后记录 identity，避免回滚误删外部替换文件。
            write_bookmark_file(target, document, output=True)
            stat = target.stat()
            created[target] = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
    except Exception:
        original_error = sys.exc_info()[1]
        # 2. 只删除 identity 未变化的本次文件，清理失败不覆盖原始异常。
        for target, identity in created.items():
            try:
                stat = target.stat()
                current = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
                if current == identity:
                    target.unlink()
            except OSError as cleanup_error:
                logger.warning("cannot roll back independent output %s: %s", target, cleanup_error)
        raise original_error


def _merge_options(args: argparse.Namespace) -> tuple[object, ...]:
    """返回所有合并模式参数，供互斥校验复用。"""
    return (args.base, args.source, args.base_browser, args.base_profile,
            args.source_browser, args.source_profile, args.output, args.output_dir,
            args.in_place)

def _handle_cleanup(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int | None:
    """执行备份清理模式，非清理命令返回 None。"""
    if (args.start or args.end) and not args.clean_backups:
        parser.error("--start/--end require --clean-backups")
    if not args.clean_backups:
        return None
    if any(_merge_options(args)) or args.list_profiles:
        parser.error("--clean-backups cannot be combined with other options")
    try:
        start = _parse_time(args.start)
        end = _parse_time(args.end)
        backups = list_backups(args.clean_backups, start, end)
        for path in backups:
            print(path)
        if args.yes:
            clean_backups(args.clean_backups, start=start, end=end, dry_run=False, confirm=True)
        return 0
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    """执行安全合并或备份清理；默认只预览，不写文件。"""
    parser = _parser()
    args = parser.parse_args(argv)
    if args.yes and not args.in_place and not args.clean_backups:
        parser.error("--yes requires --in-place or --clean-backups")
    cleanup_result = _handle_cleanup(args, parser)
    if cleanup_result is not None:
        return cleanup_result
    if args.list_profiles:
        if any(_merge_options(args)):
            parser.error("--list-profiles cannot be combined with merge options")
        try:
            print("\n".join(discover_profiles(args.list_profiles)))
            return 0
        except (OSError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    if sum(bool(value) for value in (args.output, args.output_dir, args.in_place)) > 1:
        parser.error("--output, --output-dir and --in-place are mutually exclusive")
    _configure_logging(args.log_level)
    try:
        base_path, source_paths = _resolve_input_paths(args, parser)
        inputs = [load_chromium_file(base_path)]
        inputs.extend(load_chromium_file(path) for path in source_paths)
        merged_roots = merge_documents(*(roots for _, roots in inputs))
        base_count = _count_pages(inputs[0][1])
        source_count = sum(_count_pages(roots) for _, roots in inputs[1:])
        result_count = _count_pages(merged_roots)
        print(f"base={base_count} sources={source_count} new={result_count - base_count} result={result_count}")
        documents = output_documents(inputs, merged_roots)
        if args.output:
            write_bookmark_file(args.output, documents[0], output=True)
        elif args.output_dir:
            _write_independent_outputs(Path(args.output_dir), documents, base_path)
        elif args.in_place:
            if not args.yes:
                answer = input(f"Replace {base_path}? Type 'yes' to continue: ")
                if answer.strip().lower() != "yes":
                    print("cancelled: explicit confirmation required", file=sys.stderr)
                    return 2
            _, backup = write_bookmark_file(base_path, documents[0], in_place=True)
            print(f"backup={backup}")
        return 0
    except (OSError, ValueError, TypeError, FileExistsError) as exc:
        logger.error("bookmark merge failed: %s", exc)
        print(f"error: {exc}", file=sys.stderr)
        return 1