"""安全读取和写回 Chromium 书签 JSON 文件。"""

import json
import os
import re
import shutil
import tempfile
from copy import deepcopy
from datetime import datetime
from pathlib import Path

from src.entity import BookmarkFolder
from src.safe_file import atomic_write
from src.functional import dump_json_folder, merge, parse_json_item

SUPPORTED_ROOTS = ("bookmark_bar", "other", "synced")


def load_chromium_file(path: Path | str) -> tuple[dict, dict[str, BookmarkFolder]]:
    """读取 Chromium 文档，解析存在的受支持根节点并保留其余字段。"""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"bookmark file does not exist: {path}")
    try:
        with path.open("r", encoding="utf-8") as stream:
            document = json.load(stream)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in bookmark file: {path}") from exc
    roots = document.get("roots") if isinstance(document, dict) else None
    if not isinstance(roots, dict):
        raise ValueError(f"bookmark file roots must be an object: {path}")
    parsed = {}
    for name in SUPPORTED_ROOTS:
        if name not in roots:
            continue
        if not isinstance(roots[name], dict):
            raise ValueError(f"roots.{name} must be an object: {path}")
        try:
            root_data = deepcopy(roots[name])
            root_data.setdefault("date_modified", "0")
            root_data.setdefault("date_added", "0")
            root_data.setdefault("date_last_used", "0")
            parsed[name] = parse_json_item(root_data)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid roots.{name} in {path}: {exc}") from exc
    if not parsed:
        raise ValueError(f"bookmark file must contain at least one supported root: {path}")
    return document, parsed


def merge_documents(*root_sets: dict[str, BookmarkFolder]) -> dict[str, BookmarkFolder]:
    """按根节点名称独立合并多个文档中的书签树。"""
    names = []
    for roots in root_sets:
        for name in SUPPORTED_ROOTS:
            if name in roots and name not in names:
                names.append(name)
    return {name: merge(*(roots[name] for roots in root_sets if name in roots)) for name in names}


def output_documents(inputs: list[tuple[dict, dict[str, BookmarkFolder]]], merged: dict[str, BookmarkFolder]) -> list[dict]:
    """为每个输入重建独立文档外壳，并写入一致的受支持根节点。"""
    results = []
    for document, _ in inputs:
        result = deepcopy(document)
        roots = result.setdefault("roots", {})
        for name, root in merged.items():
            roots[name] = dump_json_folder(root)
        results.append(result)
    return results
def write_bookmark_file(path: Path | str, document: dict, *, output: bool = False, in_place: bool = False, confirm: bool = False) -> tuple[Path, Path | None]:
    """Safely write JSON using the shared atomic writer."""
    target = Path(path)
    def validate(candidate: Path) -> None:
        load_chromium_file(candidate)
    data = json.dumps(document, ensure_ascii=False, indent=4)
    backup = atomic_write(target, data, validate, output=output, in_place=in_place, confirm=confirm)
    return target, backup

_BACKUP_RE = re.compile(r"^.+\.\d{8}_\d{6}_bookmark_backup(?:_\d+)?\.bak$")


def list_backups(directory: Path | str, start: datetime | None = None, end: datetime | None = None) -> list[Path]:
    """列出目录中符合本工具命名规则且在时间范围内的备份。"""
    directory = Path(directory)
    if not directory.is_dir():
        raise NotADirectoryError(f"backup directory does not exist: {directory}")
    result = []
    for path in directory.iterdir():
        if not path.is_file() or not _BACKUP_RE.match(path.name):
            continue
        match = re.search(r"\.(\d{8}_\d{6})_bookmark_backup", path.name)
        if match is None:
            continue
        try:
            stamp = datetime.strptime(match.group(1), "%Y%m%d_%H%M%S")
        except ValueError:
            continue
        if start is not None and stamp < start:
            continue
        if end is not None and stamp > end:
            continue
        result.append(path)
    return sorted(result)


def clean_backups(directory: Path | str, *, start: datetime | None = None, end: datetime | None = None, dry_run: bool = True, confirm: bool = False) -> list[Path]:
    """按时间范围清理本工具备份；默认 dry-run，删除必须显式确认。"""
    backups = list_backups(directory, start, end)
    if not dry_run and confirm:
        for path in backups:
            path.unlink()
    return backups