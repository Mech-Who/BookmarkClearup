"""BookmarkClearup 命令行入口。"""

import argparse
import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from src.bookmark_io import clean_backups, list_backups, load_chromium_file, merge_documents, output_documents, write_bookmark_file
from src.chromium import discover_profiles, profile_bookmarks_path
from src.entity import BookmarkFolder
from src.html_io import parse_html, write_html_file
from src.functional import dump_json_folder, visit

logger = logging.getLogger(__name__)



@dataclass
class InputDocument:
    """Normalized input description used by the merge pipeline."""
    path: Path
    format: str
    shell: dict | None
    roots: dict[str, BookmarkFolder]


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
    parser.add_argument("--output-format", choices=["json", "html"])
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


def _merge_options(args: argparse.Namespace) -> tuple[object, ...]:
    """返回所有合并模式参数，供互斥校验复用。"""
    return (args.base, args.source, args.base_browser, args.base_profile,
            args.source_browser, args.source_profile, args.output, args.output_dir,
            args.in_place, args.output_format)


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


def _path_format(path: Path) -> str | None:
    """Return format inferred from a supported file extension."""
    suffix = path.suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix in (".html", ".htm"):
        return "html"
    return None


def _load_input(path: str | Path) -> InputDocument:
    """Load one JSON or Netscape HTML input description."""
    target = Path(path)
    fmt = _path_format(target)
    if fmt == "html":
        return InputDocument(target, fmt, None, {"bookmark_bar": parse_html(target)})
    document, roots = load_chromium_file(target)
    return InputDocument(target, "json", document, roots)


def _json_document(item: InputDocument, merged: dict[str, BookmarkFolder]) -> dict:
    """Build the input shell or a minimal Chromium shell for HTML."""
    if item.shell is None:
        return {"version": "1", "roots": {"bookmark_bar": dump_json_folder(merged["bookmark_bar"])}}
    return output_documents([(item.shell, item.roots)], merged)[0]


def _write_one(target: Path, fmt: str, item: InputDocument, merged: dict[str, BookmarkFolder], *, output: bool, in_place: bool = False, confirm: bool = False) -> tuple[Path, Path | None]:
    """Serialize one merged result using an explicit format."""
    if fmt == "html":
        root = merged.get("bookmark_bar")
        if root is None:
            raise ValueError("HTML output requires bookmark_bar root")
        return write_html_file(target, root, output=output, in_place=in_place, confirm=confirm)
    return write_bookmark_file(target, _json_document(item, merged), output=output, in_place=in_place, confirm=confirm)


def _write_independent_outputs(plans: list[tuple[Path, str, InputDocument]], merged: dict[str, BookmarkFolder]) -> None:
    """Write all independent outputs with identity-checked rollback."""
    created: dict[Path, tuple[int, int, int, int]] = {}
    try:
        # 1. Write each target and record its identity after commit.
        for target, fmt, item in plans:
            _write_one(target, fmt, item, merged, output=True)
            stat = target.stat()
            created[target] = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
    except Exception:
        original = sys.exc_info()[1]
        # 2. Remove only unchanged files and preserve cleanup errors as warnings.
        for target, identity in created.items():
            try:
                stat = target.stat()
                current = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
                if current == identity:
                    target.unlink()
            except OSError as cleanup_error:
                logger.warning("cannot roll back independent output %s: %s", target, cleanup_error)
        raise original
def main(argv: list[str] | None = None) -> int:
    """Execute one unified JSON/HTML merge pipeline."""
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
        paths = [base_path, *source_paths]
        # 1. Load every input into the same path/format/shell/roots description.
        inputs = [_load_input(path) for path in paths]
        # 2. 合并所有输入并计算结果统计。
        base_format = inputs[0].format
        if args.in_place and args.output_format and args.output_format != base_format:
            parser.error("--in-place output format must match the base input")
        merged = merge_documents(*(item.roots for item in inputs))
        count = [_count_pages(item.roots) for item in inputs]
        print(f"base={count[0]} sources={sum(count[1:])} new={_count_pages(merged) - count[0]} result={_count_pages(merged)}")
        # 3. 按 dry-run、独立输出或原地覆盖模式分发结果。
        if not args.output and not args.output_dir and not args.in_place:
            return 0
        if args.output:
            target = Path(args.output)
            fmt = args.output_format or _path_format(target) or base_format
            _write_one(target, fmt, inputs[0], merged, output=True)
            return 0
        if args.output_dir:
            output_dir = Path(args.output_dir)
            plans = []
            for index, item in enumerate(inputs):
                fmt = args.output_format or item.format
                suffix = ".html" if fmt == "html" else ".json"
                stem = item.path.stem if index == 0 else f"source_{index}"
                plans.append((output_dir / f"{stem}_merged{suffix}", fmt, item))
            if any(target.exists() for target, _, _ in plans):
                raise FileExistsError("one or more independent output files already exist")
            _write_independent_outputs(plans, merged)
            return 0
        if not args.yes:
            answer = input(f"Replace {base_path}? Type 'yes' to continue: ")
            if answer.strip().lower() != "yes":
                print("cancelled: explicit confirmation required", file=sys.stderr)
                return 2
        target, backup = _write_one(Path(base_path), base_format, inputs[0], merged, output=False, in_place=True, confirm=True)
        print(f"backup={backup}")
        return 0
    except (OSError, ValueError, TypeError, FileExistsError, PermissionError) as exc:
        logger.error("bookmark merge failed: %s", exc)
        print(f"error: {exc}", file=sys.stderr)
        return 1
